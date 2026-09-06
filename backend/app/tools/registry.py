"""Tool Registry thực thi đúng sáu cổng kiểm soát.

Thứ tự cố ý rõ ràng để phục vụ học tập và audit:
1) nhận diện tool, 2) tạo audit event, 3) validate schema + authentication,
4) permission + OAuth scope, 5) rate limit, 6) execute có timeout/retry chọn lọc.
"""

import asyncio
import json
import random
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError

from app.auth.permissions import permissions_for_role
from app.core.security import redact
from app.db.models import AuditEvent, AuditStatus
from app.tools.contracts import (
    ToolAccessDeniedError,
    ToolContext,
    ToolDefinition,
    ToolError,
    ToolNotFoundError,
    ToolRateLimitError,
)


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

    async def execute(
        self, name: str, arguments: dict[str, Any], context: ToolContext
    ) -> BaseModel:
        definition = self.get(name)

        # Tạo audit trước các cổng để cả payload sai, thiếu quyền và rate limit đều có dấu vết.
        # Arguments được redact đệ quy trước khi ghi xuống SQLite.
        audit = AuditEvent(
            request_id=context.request_id,
            user_id=getattr(context.user, "id", None),
            user_email=getattr(context.user, "email", None),
            role=getattr(context.user, "role", None),
            tool_name=definition.name,
            arguments_json=json.dumps(redact(arguments), ensure_ascii=False),
            status=AuditStatus.STARTED.value,
        )
        context.db.add(audit)
        await context.db.commit()

        started = time.perf_counter()
        timeout = definition.timeout_seconds or context.settings.tool_timeout_seconds

        try:
            # Schema sai bị chặn trước khi chạm API ngoài nhưng vẫn được audit.
            try:
                payload = definition.input_model.model_validate(arguments)
            except ValidationError as exc:
                raise ToolError(str(exc), code="invalid_arguments") from exc

            if not context.user or not context.user.is_active:
                raise ToolAccessDeniedError(
                    "Người dùng chưa được xác thực hoặc đã bị vô hiệu hóa."
                )

            granted_permissions = permissions_for_role(context.user.role)
            missing_permissions = definition.required_permissions - granted_permissions
            if missing_permissions:
                raise ToolAccessDeniedError(
                    f"Thiếu quyền ứng dụng: {', '.join(sorted(missing_permissions))}"
                )

            user_scopes = set(json.loads(context.user.oauth_scopes_json or "[]"))
            missing_scopes = definition.required_oauth_scopes - user_scopes
            if missing_scopes:
                raise ToolAccessDeniedError(
                    "Google chưa cấp scope cần thiết: " + ", ".join(sorted(missing_scopes))
                )

            # Tách rate limit theo (user, tool), tránh một user làm cạn quota người khác.
            await self._limiter.check(
                context.user.id, definition.name, definition.rate_limit_per_minute
            )

            # Chỉ lỗi transient mới retry; lỗi 400/401/403/404 phải trả về ngay.
            result = await self._execute_with_retry(definition, payload, context, timeout)
            audit.status = AuditStatus.SUCCESS.value
            audit.result_json = json.dumps(
                redact(result.model_dump(mode="json")), ensure_ascii=False
            )
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
            audit.error_message = str(exc)[:2000]
            raise
        finally:
            audit.latency_ms = round((time.perf_counter() - started) * 1000)
            audit.completed_at = datetime.now(UTC)
            await context.db.commit()

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
                last_error = ToolError(str(exc), code="connection_error", retryable=True)

            if attempt < definition.max_attempts:
                # Exponential backoff có jitter để các request không retry cùng một thời điểm.
                await asyncio.sleep((2 ** (attempt - 1)) * 0.25 + random.uniform(0, 0.15))

        assert last_error is not None
        raise last_error
