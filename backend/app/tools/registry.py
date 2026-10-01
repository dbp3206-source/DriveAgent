"""Tool Registry thực thi đúng sáu cổng kiểm soát.

Thứ tự cố ý rõ ràng để phục vụ học tập và audit:
1) nhận diện tool, 2) tạo audit event, 3) validate schema + authentication,
4) permission + OAuth scope, 5) rate limit, 6) execute có timeout/retry chọn lọc.
"""

import asyncio
import json
import logging
import random
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError

from app.auth.permissions import permissions_for_role
from app.db.models import AuditEvent, AuditStatus
from app.tools.contracts import (
    ToolAccessDeniedError,
    ToolContext,
    ToolDefinition,
    ToolError,
    ToolNotFoundError,
    ToolRateLimitError,
)

logger = logging.getLogger(__name__)
SAFE_TOOL_FAILURE_MESSAGE = "Tool không hoàn tất; xem mã lỗi và request ID."


class SlidingWindowLimiter:
    """Rate limiter local theo (user, tool), phù hợp tiến trình chạy một máy."""

    def __init__(self) -> None:
        self._calls: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, user_id: str, tool_name: str, limit: int) -> None:
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=1)
        key = (user_id, tool_name)
        async with self._lock:
            calls = self._calls[key]
            while calls and calls[0] < cutoff:
                calls.popleft()
            if len(calls) >= limit:
                raise ToolRateLimitError(
                    f"Tool {tool_name} đã vượt {limit} lần/phút. Hãy thử lại sau."
                )
            calls.append(now)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._limiter = SlidingWindowLimiter()

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool đã được đăng ký: {definition.name}")
        self._tools[definition.name] = definition

    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    @staticmethod
    def _is_oauth_scope_satisfied(required_scope: str, user_scopes: set[str]) -> bool:
        if required_scope in user_scopes:
            return True
        if "https://mail.google.com/" in user_scopes and "gmail" in required_scope:
            return True
        if "https://www.googleapis.com/auth/gmail.modify" in user_scopes and (
            required_scope
            in {
                "https://www.googleapis.com/auth/gmail.compose",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
            }
        ):
            return True
        # Google defines gmail.compose as permission to manage drafts and send
        # email. It therefore satisfies gmail.send, but not mailbox read access.
        if (
            "https://www.googleapis.com/auth/gmail.compose" in user_scopes
            and required_scope == "https://www.googleapis.com/auth/gmail.send"
        ):
            return True
        if "https://www.googleapis.com/auth/drive" in user_scopes and "drive" in required_scope:
            return True
        return False

    async def execute(
        self, name: str, arguments: dict[str, Any], context: ToolContext
    ) -> BaseModel:
        definition = self.get(name)
        progress_user_id = getattr(context.user, "id", "")

        # Record only shape metadata, including for invalid input. Redacting
        # credential-looking strings is insufficient: a valid document body,
        # search query or email address is still private user content.
        audit = AuditEvent(
            request_id=context.request_id,
            user_id=getattr(context.user, "id", None),
            user_email=getattr(context.user, "email", None),
            role=getattr(context.user, "role", None),
            tool_name=definition.name,
            arguments_json=json.dumps({"argument_count": len(arguments)}),
            status=AuditStatus.STARTED.value,
        )
        context.db.add(audit)
        await context.db.commit()
        from app.services.run_progress import publish_progress

        publish_progress(
            progress_user_id,
            context.request_id,
            {"stage": "tool", "tool": name, "status": "running"},
        )

        started = time.perf_counter()
        timeout = definition.timeout_seconds or context.settings.tool_timeout_seconds

        try:
            # Schema sai bị chặn trước khi chạm API ngoài nhưng vẫn được audit.
            try:
                payload = definition.input_model.model_validate(arguments)
            except ValidationError as exc:
                raise ToolError(str(exc), code="invalid_arguments") from exc

            if not context.user or not context.user.is_active:
                raise ToolAccessDeniedError("Người dùng chưa được xác thực hoặc đã bị vô hiệu hóa.")

            if (
                definition.external_write
                and context.settings.environment.casefold() not in {"local", "development"}
                and not context.settings.beta_allow_external_writes
            ):
                raise ToolAccessDeniedError(
                    "Closed beta hiện chỉ đọc và xem trước; thao tác ghi Google chưa được bật."
                )

            granted_permissions = permissions_for_role(context.user.role)
            if definition.requires_user_action and context.source != "api":
                raise ToolAccessDeniedError(
                    "Thao tác này cần người dùng chủ động chọn trên giao diện."
                )
            missing_permissions = definition.required_permissions - granted_permissions
            if missing_permissions:
                raise ToolAccessDeniedError(
                    f"Thiếu quyền ứng dụng: {', '.join(sorted(missing_permissions))}"
                )

            user_scopes = set(json.loads(context.user.oauth_scopes_json or "[]"))
            missing_scopes = {
                scope
                for scope in definition.required_oauth_scopes
                if not self._is_oauth_scope_satisfied(scope, user_scopes)
            }
            if missing_scopes:
                raise ToolAccessDeniedError(
                    "Google chưa cấp quyền cần thiết cho thao tác này. "
                    "Hãy dùng nút cấp quyền bên dưới rồi thử lại."
                )

            # Tách rate limit theo (user, tool), tránh một user làm cạn quota người khác.
            await self._limiter.check(
                context.user.id, definition.name, definition.rate_limit_per_minute
            )

            # Chỉ lỗi transient mới retry; lỗi 400/401/403/404 phải trả về ngay.
            from app.services.operational_tracing import tracer

            with tracer().start_as_current_span(
                "veridra.tool", record_exception=False, set_status_on_exception=False
            ) as span:
                span.set_attribute("request_id", context.request_id)
                span.set_attribute("tool", definition.name)
                result = await self._execute_with_retry(definition, payload, context, timeout)
                span.set_attribute("outcome", "success")
            audit.status = AuditStatus.SUCCESS.value
            audit_result = result.model_dump(mode="json")
            # The operational audit is metadata-only for every tool. Provider
            # output, Drive document text, file names and generated content do
            # not belong in AgentOps/audit storage.
            audit_summary: dict[str, object] = {
                "output_type": type(result).__name__,
                "field_count": len(audit_result),
            }
            if definition.name == "gmail_read_thread":
                messages = audit_result.get("messages", [])
                audit_summary["message_count"] = len(messages)
                audit_summary["attachment_count"] = sum(
                    len(item.get("attachments", [])) for item in messages
                )
            elif definition.name == "gmail_read_matching_messages":
                audit_summary["message_count"] = len(audit_result.get("messages", []))
                audit_summary["examined_count"] = audit_result.get("examined_count", 0)
                audit_summary["unreadable_body_count"] = audit_result.get(
                    "unreadable_body_count", 0
                )
            elif definition.name == "gmail_get_attachment":
                data = str(audit_result.get("data_base64", ""))
                audit_summary["size_bytes_approx"] = len(data) * 3 // 4
            elif definition.name == "gmail_summarize_thread":
                audit_summary["bullet_count"] = len(audit_result.get("bullets", []))
            audit.result_json = json.dumps(audit_summary)
            return result
        except Exception as exc:
            # Bỏ mọi thay đổi nghiệp vụ chưa commit trước khi cập nhật audit. Nếu không,
            # commit audit ở finally có thể vô tình ghi một nửa kết quả của tool lỗi.
            await context.db.rollback()
            audit.status = (
                AuditStatus.DENIED.value
                if isinstance(exc, ToolAccessDeniedError)
                else AuditStatus.ERROR.value
            )
            audit.error_type = getattr(exc, "code", type(exc).__name__)
            # Exception text may include document content or provider payloads.
            # The typed error code and request ID remain available for triage.
            audit.error_message = SAFE_TOOL_FAILURE_MESSAGE
            raise
        finally:
            audit.latency_ms = round((time.perf_counter() - started) * 1000)
            audit.completed_at = datetime.now(UTC)
            await context.db.commit()
            publish_progress(
                progress_user_id,
                context.request_id,
                {
                    "stage": "tool",
                    "tool": name,
                    "status": audit.status,
                    "latency_ms": audit.latency_ms,
                },
            )

    async def _execute_with_retry(
        self,
        definition: ToolDefinition,
        payload: BaseModel,
        context: ToolContext,
        timeout: float,
    ) -> BaseModel:
        last_error: Exception | None = None
        for attempt in range(1, definition.max_attempts + 1):
            try:
                async with asyncio.timeout(timeout):
                    result = await definition.handler(payload, context)
                return definition.output_model.model_validate(result)
            except TimeoutError:
                last_error = ToolError("Tool hết thời gian chờ.", code="timeout", retryable=True)
            except ToolError as exc:
                last_error = exc
                if not exc.retryable:
                    raise
            except (ConnectionError, OSError) as exc:
                # Exception text can contain URLs, tokens or private paths. Log
                # only diagnostic identifiers; a socket error does not establish
                # that another local runner caused the failure.
                logger.warning(
                    "Tool transport failed; tool=%s attempt=%s type=%s request_id=%s",
                    definition.name,
                    attempt,
                    type(exc).__name__,
                    context.request_id,
                )
                last_error = ToolError(
                    "Không thể kết nối dịch vụ bên ngoài lúc này. "
                    "Hãy kiểm tra kết nối mạng rồi thử lại. "
                    "Nếu lỗi tiếp diễn, dùng mã yêu cầu để kiểm tra nhật ký.",
                    code="connection_error",
                    retryable=True,
                )

            if attempt < definition.max_attempts:
                # Exponential backoff có jitter để các request không retry cùng một thời điểm.
                await asyncio.sleep((2 ** (attempt - 1)) * 0.25 + random.uniform(0, 0.15))

        assert last_error is not None
        raise last_error
