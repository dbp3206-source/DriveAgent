"""Chat history and inert creation proposals, scoped to the authenticated user."""

import asyncio
import json
import logging
import re
import time
from datetime import UTC
from urllib.parse import urlsplit

import httpx
from aiohttp import ClientError as AiohttpClientError
from fastapi import APIRouter, HTTPException, Query, Request
from google.genai.errors import APIError
from pydantic import ValidationError
from sqlalchemy import and_, or_, select

from app.agent.creation import CreationAnswer, preserve_explicit_literals
from app.agent.orchestrator import AgentNotConfiguredError, AgentOrchestrator
from app.agent.routing import Route
from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    MessagePage,
    MessageResponse,
    SessionPage,
    SessionResponse,
    SessionUpdateRequest,
)
from app.core.cursor import decode_cursor, encode_cursor
from app.core.json_utils import json_list, json_object
from app.db.models import AuditEvent, AuditStatus, ChatSession, CreationProposalRecord, Message
from app.tools.contracts import ToolError

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.get("/progress/{request_id}")
async def execution_progress(request_id: str, user: CurrentUser):
    from app.services.run_progress import read_progress

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
        raise HTTPException(status_code=422, detail="Invalid request identifier")
    from fastapi.responses import JSONResponse

    return JSONResponse(
        {"events": read_progress(user.id, request_id)},
        headers={"Cache-Control": "no-store"},
    )


_GMAIL_FOLLOWUP_INTENT = re.compile(
    r"\b(?:giải thích|đào sâu|phân tích|làm rõ|mở rộng|đi sâu|"
    r"ghi rõ (?:mốc )?thời gian|mốc thời gian|thời gian|khi nào|"
    r"first principles|framework)\b",
    re.I,
)
_GMAIL_FOLLOWUP_REFERENCE = re.compile(
    r"(?:nội dung\s+(?:(?:được|đc)\s+)?(?:đề cập|nhắc đến)|nội dung\s+(?:đó|trên|vừa rồi)|"
    r"(?:email|mail|thư|bài viết|chủ đề)\s+(?:gần nhất|mới nhất|đó|này|vừa rồi)|"
    r"(?:tài liệu|nguồn)\s+(?:là|chính là)\s+(?:email|mail|thư)|"
    r"email\s+gần nhất\s+đó)",
    re.I,
)
_DRIVE_FOLLOWUP_INTENT = re.compile(
    r"\b(?:giải thích|đào sâu|phân tích|làm rõ|mở rộng|đi sâu|tiếp tục|nói thêm|"
    r"chi tiết hơn|first principles|framework)\b",
    re.I,
)
_DRIVE_IMPLICIT_CONTINUATION = re.compile(
    r"\b(?:sâu hơn|chi tiết hơn|phân tích tiếp|đào sâu thêm|mở rộng thêm|nói thêm|"
    r"tiếp tục(?:\s+(?:phân tích|giải thích|đào sâu))?)\b",
    re.I,
)
_DRIVE_FOLLOWUP_REFERENCE = re.compile(
    r"(?:\b(?:file|tệp|tài liệu|nội dung|đoạn|phần|nguồn)\s+"
    r"(?:đó|đấy|này|trên|vừa rồi|ở trên)\b|"
    r"\b(?:ý|điểm|phần)\s+(?:thứ\s*)?\d+\b|"
    r"\b(?:file|tệp|tài liệu)\s+gần nhất(?:\s+đó)?\b|"
    r"\b(?:nội dung|phần|đoạn)\b.{0,32}\b(?:hơn|thêm|nữa)\b)",
    re.I,
)


def _failed_task_diagnostic(exc: BaseException, status: str) -> tuple[str, dict]:
    """Return only fixed, content-free cause labels for the local audit log."""

    if status == "cancelled":
        return "Người dùng đã dừng yêu cầu.", {"failure_category": "user_cancelled"}
    if isinstance(exc, APIError):
        code = exc.code if type(exc.code) is int else None
        categories = {
            429: (
                "provider_limited",
                "Gemini đang giới hạn tốc độ hoặc quota; chưa phân biệt được nguyên nhân.",
            ),
            503: (
                "provider_unavailable",
                "Gemini tạm thời không khả dụng; không suy ra Drive hoặc Gmail bị lỗi.",
            ),
            504: (
                "provider_timeout",
                "Gemini quá thời hạn phản hồi; chưa có bằng chứng đã hết quota.",
            ),
            400: (
                "provider_configuration",
                "Gemini từ chối định dạng yêu cầu (400 Bad Request / Lỗi cấu hình).",
            ),
        }
        category, message = categories.get(
            code, ("provider_rejected", "Gemini từ chối yêu cầu; xem mã trạng thái nhà cung cấp.")
        )
        result = {"failure_category": category}
        if code is not None:
            result["provider_code"] = code
        return message, result
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "Quá thời gian chờ xử lý (Timeout quá 60s); Gemini chưa phản hồi.", {
            "failure_category": "provider_timeout"
        }
    if isinstance(exc, (httpx.TransportError, AiohttpClientError, OSError)):
        return "Không kết nối được Gemini; kiểm tra mạng hoặc proxy.", {
            "failure_category": "provider_transport"
        }
    if isinstance(exc, AgentNotConfiguredError):
        return "Chưa cấu hình model để xử lý yêu cầu.", {"failure_category": "model_configuration"}
    if isinstance(exc, ToolError):
        result = {"failure_category": "application_guard"}
        if isinstance(exc.code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", exc.code):
            result["error_code"] = exc.code
        return "Yêu cầu bị dừng bởi kiểm tra đầu vào, quyền hoặc công cụ.", result
    return "Agent không hoàn tất; xem request ID và log cục bộ.", {
        "failure_category": "unclassified"
    }


def _gmail_thread_ids_from_citations(citations_json: str) -> list[str]:
    """Return distinct, validated Gmail thread IDs from this assistant turn."""
    thread_ids: list[str] = []
    for citation in json_list(citations_json):
        if not isinstance(citation, dict):
            continue
        link = str(citation.get("web_view_link") or "")
        parsed = urlsplit(link)
        if parsed.scheme != "https" or parsed.hostname != "mail.google.com":
            continue
        if not parsed.path.startswith("/mail/"):
            continue
        fragment = parsed.fragment.strip("/")
        candidate = fragment.split("/")[-1] if fragment else ""
        if re.fullmatch(r"[A-Za-z0-9_-]{5,200}", candidate) and candidate not in thread_ids:
            thread_ids.append(candidate)
    return thread_ids


def _gmail_followup_route(message: str, prior_messages: list[Message]) -> Route | None:
    """Pin a follow-up to the latest relevant Gmail source in this session.

    Failed assistant turns may sit between the original summary and the next
    follow-up. Keep looking through those turns, but stop at an unrelated user
    request so an old email is never silently reused for a new topic.
    """

    latest_assistant_index = next(
        (index for index, row in enumerate(prior_messages) if row.role == "assistant"),
        None,
    )
    has_followup_intent = bool(_GMAIL_FOLLOWUP_INTENT.search(message))
    asks_for_all_times = bool(
        re.search(
            r"\b(?:mốc thời gian|ghi rõ thời gian|thời gian (?:của|nhận)|khi nào)\b",
            message,
            re.I,
        )
    )
    explicit_latest_email = bool(
        re.search(r"\b(?:email|mail|thư)\s+(?:gần nhất|mới nhất)\s+đó\b", message, re.I)
    )

    # In normal conversation, a recent cited source remains the implicit referent
    # across failed/uncited assistant turns, as long as the user has not changed
    # topics in between.
    if has_followup_intent:
        for row in prior_messages:
            if row.role == "assistant":
                thread_ids = _gmail_thread_ids_from_citations(row.citations_json)
                if len(thread_ids) == 1:
                    return Route("gmail_read_thread", {"thread_id": thread_ids[0]})
                if len(thread_ids) > 1:
                    if asks_for_all_times:
                        return Route(
                            sources=tuple(
                                Route("gmail_read_thread", {"thread_id": thread_id})
                                for thread_id in thread_ids[:10]
                            )
                        )
                    return Route(
                        direct=True,
                        clarification=(
                            "Câu trả lời trước dựa trên nhiều email khác nhau. Bạn muốn đào sâu "
                            "email nào? Hãy nêu tiêu đề hoặc người gửi để tôi mở đúng thư."
                        ),
                        required_sources=("gmail",),
                    )
                if getattr(row, "status", None) == "failed":
                    continue
                break
            if row.role == "user":
                prior_request = str(row.content or "")
                continues_gmail_topic = bool(
                    _GMAIL_FOLLOWUP_REFERENCE.search(prior_request)
                    or re.search(r"\b(?:email|mail|thư)\b", prior_request, re.I)
                )
                if not continues_gmail_topic and prior_request.strip():
                    break

    if not (_GMAIL_FOLLOWUP_REFERENCE.search(message) or explicit_latest_email):
        return None
    if not has_followup_intent and not explicit_latest_email:
        return None
    for index, row in enumerate(prior_messages):
        if row.role != "assistant":
            continue
        thread_ids = _gmail_thread_ids_from_citations(row.citations_json)
        if not thread_ids:
            continue
        # If another assistant answer intervened, only accept an explicit
        # clarification that names the same recent email. This avoids carrying
        # an old inbox source into an unrelated later topic.
        if latest_assistant_index not in {None, index} and not explicit_latest_email:
            return None
        if len(thread_ids) > 1:
            if asks_for_all_times:
                return Route(
                    sources=tuple(
                        Route("gmail_read_thread", {"thread_id": thread_id})
                        for thread_id in thread_ids[:10]
                    )
                )
            return Route(
                direct=True,
                clarification=(
                    "Câu trả lời trước dựa trên nhiều email khác nhau. Bạn muốn đào sâu "
                    "email nào? Hãy nêu tiêu đề hoặc người gửi để tôi mở đúng thư."
                ),
                required_sources=("gmail",),
            )
        return Route("gmail_read_thread", {"thread_id": thread_ids[0]})
    return None


def _drive_file_ids_from_citations(citations_json: str) -> list[str]:
    """Extract distinct, validated Google Drive IDs from a persisted assistant turn."""

    file_ids: list[str] = []
    for citation in json_list(citations_json):
        if not isinstance(citation, dict):
            continue
        candidate = str(citation.get("file_id") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", candidate):
            continue
        link = str(citation.get("web_view_link") or "")
        host = (urlsplit(link).hostname or "").casefold()
        if host not in {"drive.google.com", "docs.google.com"}:
            continue
        if candidate not in file_ids:
            file_ids.append(candidate)
    return file_ids


def _drive_followup_route(message: str, prior_messages: list[Message]) -> Route | None:
    """Re-read the same cited Drive file on a contextual deepening request."""

    if not _DRIVE_FOLLOWUP_INTENT.search(message):
        return None
    if not (
        _DRIVE_FOLLOWUP_REFERENCE.search(message) or _DRIVE_IMPLICIT_CONTINUATION.search(message)
    ):
        return None

    for row in prior_messages:
        if row.role == "assistant":
            file_ids = _drive_file_ids_from_citations(row.citations_json)
            if len(file_ids) == 1:
                return Route(
                    "drive_read_file",
                    {"file_id": file_ids[0], "max_characters": 20_000},
                )
            if len(file_ids) > 1:
                return Route(
                    direct=True,
                    clarification=(
                        "Câu trả lời trước dựa trên nhiều tệp Drive. Bạn muốn đào sâu tệp nào? "
                        "Hãy nêu tên tệp để tôi đọc lại đúng nguồn."
                    ),
                    required_sources=("drive",),
                )
            if getattr(row, "status", None) == "failed":
                continue
            break
        if row.role == "user" and str(row.content or "").strip():
            prior_request = str(row.content)
            if not re.search(
                r"\b(?:drive|file|tệp|tài liệu|docs|sheet|pdf)\b", prior_request, re.I
            ):
                break
    return None


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
):
    limit_value = limit if isinstance(limit, int) else 50
    rows = list(
        (
            await db.scalars(
                select(ChatSession)
                .where(ChatSession.user_id == user.id)
                .order_by(ChatSession.updated_at.desc())
                .limit(limit_value)
            )
        ).all()
    )
    return rows


@router.get("/sessions-page", response_model=SessionPage)
async def list_sessions_page(
    user: CurrentUser,
    db: DbSession,
    cursor: str | None = None,
    limit: int = Query(default=40, ge=1, le=100),
):
    statement = select(ChatSession).where(ChatSession.user_id == user.id)
    try:
        key = decode_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cursor phân trang không hợp lệ.") from exc
    if key:
        at, row_id = key
        statement = statement.where(
            or_(
                ChatSession.updated_at < at,
                and_(ChatSession.updated_at == at, ChatSession.id < row_id),
            )
        )
    rows = list(
        (
            await db.scalars(
                statement.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()).limit(
                    limit + 1
                )
            )
        ).all()
    )
    more = len(rows) > limit
    items = rows[:limit]
    next_cursor = encode_cursor(items[-1].updated_at, items[-1].id) if more and items else None
    return SessionPage(items=items, next_cursor=next_cursor)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def list_messages(session_id: str, user: CurrentUser, db: DbSession):
    session = await db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    rows = list(
        (
            await db.scalars(
                select(Message)
                .where(Message.session_id == session_id, Message.user_id == user.id)
                .order_by(Message.created_at.asc())
            )
        ).all()
    )
    proposals_by_message: dict[str, list[dict]] = {}
    # Join through the owned session; never expose proposals from another chat.
    proposals = await db.scalars(
        select(CreationProposalRecord)
        .join(Message)
        .where(Message.session_id == session_id, CreationProposalRecord.user_id == user.id)
        .order_by(CreationProposalRecord.ordinal)
    )
    for proposal in proposals:
        proposals_by_message.setdefault(proposal.message_id, []).append(
            {"id": proposal.id, **json_object(proposal.spec_json)}
        )
    return [
        MessageResponse(
            id=row.id,
            role=row.role,
            content=row.content,
            citations=json_list(row.citations_json),
            trace=json_list(row.trace_json),
            proposals=proposals_by_message.get(row.id, []),
            status=row.status,
            created_at=(
                row.created_at.replace(tzinfo=UTC)
                if row.created_at.tzinfo is None
                else row.created_at
            ),
        )
        for row in rows
    ]


@router.get("/sessions/{session_id}/messages-page", response_model=MessagePage)
async def list_messages_page(
    session_id: str,
    user: CurrentUser,
    db: DbSession,
    cursor: str | None = None,
    limit: int = Query(default=80, ge=1, le=200),
):
    session = await db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    statement = select(Message).where(Message.session_id == session_id, Message.user_id == user.id)
    try:
        key = decode_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cursor phân trang không hợp lệ.") from exc
    if key:
        at, row_id = key
        statement = statement.where(
            or_(Message.created_at < at, and_(Message.created_at == at, Message.id < row_id))
        )
    rows = list(
        (
            await db.scalars(
                statement.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
            )
        ).all()
    )
    more = len(rows) > limit
    selected_rows = rows[:limit]
    # Reuse the canonical serializer, including proposal ownership checks, for
    # now by materializing this bounded page directly.
    proposals_by_message: dict[str, list[dict]] = {}
    if selected_rows:
        proposals = await db.scalars(
            select(CreationProposalRecord)
            .where(
                CreationProposalRecord.user_id == user.id,
                CreationProposalRecord.message_id.in_([row.id for row in selected_rows]),
            )
            .order_by(CreationProposalRecord.ordinal)
        )
        for proposal in proposals:
            proposals_by_message.setdefault(proposal.message_id, []).append(
                {"id": proposal.id, **json_object(proposal.spec_json)}
            )
    items = [
        MessageResponse(
            id=row.id,
            role=row.role,
            content=row.content,
            citations=json_list(row.citations_json),
            trace=json_list(row.trace_json),
            proposals=proposals_by_message.get(row.id, []),
            status=row.status,
            created_at=(
                row.created_at.replace(tzinfo=UTC)
                if row.created_at.tzinfo is None
                else row.created_at
            ),
        )
        for row in reversed(selected_rows)
    ]
    next_cursor = (
        encode_cursor(selected_rows[-1].created_at, selected_rows[-1].id)
        if more and selected_rows
        else None
    )
    return MessagePage(items=items, next_cursor=next_cursor)


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, user: CurrentUser, db: DbSession):
    controls, user_message = payload.controls.parse_leading_commands(payload.message)
    if not user_message:
        raise HTTPException(
            status_code=422,
            detail="Hãy nhập yêu cầu sau lệnh nhanh, ví dụ: /drive liệt kê ba tệp gần đây.",
        )
    session = None
    if payload.session_id:
        session = await db.scalar(
            select(ChatSession).where(
                ChatSession.id == payload.session_id, ChatSession.user_id == user.id
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    else:
        session = ChatSession(user_id=user.id, title=user_message[:80])
        db.add(session)
        await db.flush()

    prior_messages: list[Message] = []
    route_override = None
    if payload.session_id and controls.source in {"auto", "gmail", "drive"}:
        prior_messages = list(
            (
                await db.scalars(
                    select(Message)
                    .where(Message.session_id == session.id, Message.user_id == user.id)
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .limit(12)
                )
            ).all()
        )
        if controls.source in {"auto", "gmail"}:
            route_override = _gmail_followup_route(user_message, prior_messages)
        if route_override is None and controls.source in {"auto", "drive"}:
            route_override = _drive_followup_route(user_message, prior_messages)

    request_id = request.state.request_id
    from app.services.run_progress import publish_progress

    publish_progress(user.id, request_id, {"stage": "orchestration", "status": "running"})
    session_id_value = session.id
    started = time.perf_counter()
    user_row = Message(
        session_id=session.id,
        user_id=user.id,
        role="user",
        content=user_message,
        status="running",
        request_id=request_id,
    )
    task_audit = AuditEvent(
        request_id=request_id,
        user_id=user.id,
        user_email=user.email,
        role=user.role,
        tool_name="agent_task",
        arguments_json=json.dumps(
            {
                "session_id": session.id,
                "source": controls.source,
                "agent": controls.agent,
                "output": controls.output,
                "workflow": controls.workflow,
            },
            ensure_ascii=False,
        ),
        status=AuditStatus.STARTED.value,
    )
    db.add(user_row)
    db.add(task_audit)
    # Keep immutable identifiers outside ORM state. A rollback expires mapped
    # attributes, and reading ``row.id`` afterwards can trigger async IO from a
    # non-greenlet context, masking the provider error with HTTP 500.
    await db.flush()
    user_row_id = user_row.id
    task_audit_id = task_audit.id
    await db.commit()
    # Some deployments use expire_on_commit=True. Refresh the authenticated
    # actor once so downstream routing/tool authorization never triggers an
    # implicit synchronous reload from async code.
    await db.refresh(user)

    async def finish_failed_turn(status: str, exc: BaseException) -> None:
        publish_progress(user.id, request_id, {"stage": "orchestration", "status": "failed"})
        """Keep the user's request and record why the task did not complete."""

        await db.rollback()
        persisted = await db.get(Message, user_row_id)
        if persisted is not None:
            persisted.status = status
        persisted_audit = await db.get(AuditEvent, task_audit_id)
        if persisted_audit is not None:
            persisted_audit.status = (
                AuditStatus.WARNING.value if status == "cancelled" else AuditStatus.ERROR.value
            )
            persisted_audit.error_type = type(exc).__name__
            message, diagnostic = _failed_task_diagnostic(exc, status)
            persisted_audit.error_message = message
            persisted_audit.result_json = json.dumps(diagnostic, ensure_ascii=False)
            persisted_audit.latency_ms = round((time.perf_counter() - started) * 1000)
        await db.commit()
        # Keep the dependency-injected auth entity usable by any remaining
        # endpoint/test work in expire_on_commit deployments.
        await db.refresh(user)

    async def run_with(selected_orchestrator: AgentOrchestrator):
        return await selected_orchestrator.run(
            user=user,
            session_id=session_id_value,
            request_id=request.state.request_id,
            user_message=user_message,
            model_name=payload.model,
            controls=controls,
            route_override=route_override,
        )

    async def run_provider_chain(initial_orchestrator: AgentOrchestrator):
        selected = initial_orchestrator
        attempted_credentials = {
            credential_id
            for credential_id in [getattr(selected, "_provider_credential_id", None)]
            if credential_id
        }
        while True:
            try:
                return await run_with(selected)
            except APIError as exc:
                # No model response has been returned at this boundary and
                # Google write tools are excluded from autonomous runs. Try
                # each opted-in user key at most once for this request.
                # Configuration/request errors are deterministic and must not
                # be replayed against every key; only transient provider
                # failures can benefit from credential failover.
                if int(getattr(exc, "code", 0) or 0) not in {429, 500, 502, 503, 504}:
                    raise
                alternate_resolver = getattr(
                    request.app.state, "resolve_user_alternate_orchestrator", None
                )
                replacement = (
                    await alternate_resolver(db, user.id, attempted_credentials)
                    if alternate_resolver is not None
                    else None
                )
                if replacement is None:
                    raise
                replacement_id = getattr(replacement, "_provider_credential_id", None)
                if replacement_id:
                    attempted_credentials.add(replacement_id)
                logger.warning(
                    "Retrying provider call with alternate user credential %s/%s; request_id=%s",
                    len(attempted_credentials),
                    5,
                    request.state.request_id,
                )
                selected = replacement

    async def resolve_and_run():
        # Pin before resolving: a key switch must not retire the selected client
        # between resolution and the first provider call. Retired clients drain
        # when all already-started requests finish, while new turns use the new key.
        pinning = getattr(request.app.state, "inference_pinning", None)

        async def execute():
            resolver = getattr(request.app.state, "resolve_user_orchestrator", None)
            orchestrator: AgentOrchestrator = (
                await resolver(db, user.id)
                if resolver is not None
                else request.app.state.orchestrator
            )
            return await run_provider_chain(orchestrator)

        if pinning is None:
            return await execute()
        async with pinning.request(user.id):
            return await execute()

    try:
        # Bound end-to-end provider recovery. More stored keys must improve
        # availability, not multiply the user's wait without limit.
        from app.services.operational_tracing import tracer

        with tracer().start_as_current_span(
            "veridra.agent", record_exception=False, set_status_on_exception=False
        ) as span:
            span.set_attribute("request_id", request_id)
            result = await asyncio.wait_for(resolve_and_run(), timeout=60)
            span.set_attribute("outcome", "success")
        output_contract_incomplete = any(
            event.get("stage") == "output_contract"
            and event.get("status") in {"degraded", "failed"}
            for event in result.trace
        )
        if result.proposals and not output_contract_incomplete:
            # Treat the HTTP persistence boundary as the final fidelity guard.
            # Orchestrators normally normalize creation specs themselves, but no
            # generated literal should reach durable history without one last
            # comparison against the user's exact request text.
            try:
                normalized = preserve_explicit_literals(
                    user_message,
                    CreationAnswer.model_validate(
                        {"answer": result.answer, "proposals": result.proposals}
                    ),
                )
            except (ValidationError, ValueError):
                raise ToolError(
                    "Bản xem trước không giữ nguyên dữ liệu đầu vào; chưa lưu đề xuất nào.",
                    code="invalid_spec",
                ) from None
            result.answer = normalized.answer
            result.proposals = [item.model_dump(mode="json") for item in normalized.proposals]
    except AgentNotConfiguredError as exc:
        await finish_failed_turn("failed", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APIError as exc:
        await finish_failed_turn("failed", exc)
        provider_status = exc.code
        provider_msg = getattr(exc, "message", None) or str(exc)
        messages = {
            429: (
                "Gemini đã hết hạn mức hoặc đang giới hạn tốc độ (429 Quota Exceeded). "
                "Hãy thử lại sau."
            ),
            503: (
                "Gemini đang tạm thời không phản hồi do lỗi máy chủ "
                "(503 Service Unavailable / Cụm máy chủ quá tải). "
                "Điều này không xác nhận bạn đã hết quota; hãy thử lại sau ít phút "
                "hoặc chuyển sang model phụ."
            ),
            504: (
                "Gemini đã quá thời hạn xử lý ở phía nhà cung cấp "
                "(504 Gateway Timeout). Đây không phải bằng chứng "
                "hết quota; yêu cầu chưa hoàn tất. Hãy thử lại sau ít phút hoặc thu hẹp phạm vi."
            ),
            401: (
                "Google không chấp nhận API key Gemini (401 Unauthorized). "
                "Kiểm tra cấu hình trên máy."
            ),
            403: "Project Gemini chưa có quyền sử dụng model đã chọn (403 Forbidden).",
            404: "Model Gemini đã chọn không khả dụng với project hiện tại (404 Not Found).",
            400: (
                "Gemini từ chối định dạng yêu cầu "
                f"(400 Bad Request / Lỗi cấu hình): {provider_msg}. "
                "Cần kiểm tra cấu hình tích hợp."
                if provider_msg
                else (
                    "Gemini từ chối định dạng yêu cầu (400 Bad Request / Lỗi cấu hình). "
                    "Cần kiểm tra cấu hình tích hợp."
                )
            ),
        }
        logger.warning(
            "Gemini rejected request; status=%s message=%s request_id=%s",
            provider_status,
            provider_msg,
            request.state.request_id,
        )
        base_message = messages.get(
            provider_status, f"Gemini từ chối yêu cầu (mã {provider_status}): {provider_msg}."
        )
        raise HTTPException(
            status_code=503 if provider_status in {429, 503, 504} else 502,
            detail=f"{base_message} Request ID: {request.state.request_id}",
        ) from None
    except ToolError as exc:
        await finish_failed_turn("failed", exc)
        raise
    except (httpx.TransportError, AiohttpClientError) as exc:
        await finish_failed_turn("failed", exc)
        logger.warning(
            "Gemini transport unavailable; type=%s request_id=%s",
            type(exc).__name__,
            request.state.request_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Không kết nối được Gemini. Kiểm tra mạng/proxy hoặc thử lại sau; "
                f"Veridra chưa thay đổi dữ liệu. Request ID: {request.state.request_id}"
            ),
        ) from exc
    except TimeoutError as exc:
        await finish_failed_turn("failed", exc)
        logger.warning(
            "Provider recovery latency budget exhausted; request_id=%s",
            request.state.request_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Quá thời gian chờ xử lý (Timeout quá 60s): Gemini chưa phản hồi "
                "trong thời gian chờ an toàn "
                "sau khi Veridra thử các tuyến dự phòng. "
                "Yêu cầu được giữ nguyên để bạn thử lại; dữ liệu chưa bị thay đổi. "
                f"Request ID: {request.state.request_id}"
            ),
        ) from exc
    except OSError as exc:
        await finish_failed_turn("failed", exc)
        logger.warning(
            "Gemini socket unavailable; type=%s request_id=%s",
            type(exc).__name__,
            request.state.request_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Không kết nối được Gemini. Kiểm tra mạng/proxy hoặc thử lại sau; "
                f"Veridra chưa thay đổi dữ liệu. Request ID: {request.state.request_id}"
            ),
        ) from exc
    except (asyncio.CancelledError, GeneratorExit) as exc:
        # Shield the tiny status write from the request cancellation so a page
        # refresh shows an honest cancelled turn instead of making it vanish.
        await asyncio.shield(finish_failed_turn("cancelled", exc))
        logger.info(
            "Yêu cầu trò chuyện bị dừng bởi người dùng; request_id=%s", request.state.request_id
        )
        raise
    except Exception as exc:
        await finish_failed_turn("failed", exc)
        logger.error(
            "Agent thất bại; type=%s request_id=%s", type(exc).__name__, request.state.request_id
        )
        raise HTTPException(
            status_code=502,
            detail=f"Agent không thể hoàn tất. Request ID: {request.state.request_id}",
        ) from exc

    # ADK may execute directly without a separate planner. Do not invent a blank plan event.
    response_trace = (
        [{"stage": "plan", "steps": result.plan}] if result.plan else []
    ) + result.trace
    # Use the HTTP request ID as the stable root correlation ID across the
    # persisted chat turn, trace events, and tool audit rows. This is metadata
    # only: never attach prompt, answer, email, or retrieved document contents.
    from app.services.agentops import sanitize_run_trace

    response_trace = sanitize_run_trace(response_trace, request_id)
    turn_status = "incomplete" if output_contract_incomplete else "completed"
    # An answer that missed an explicit structure/length requirement remains
    # available as a draft, but must not be offered as a finished deliverable.
    proposals_to_persist = [] if output_contract_incomplete else result.proposals
    assistant_row = Message(
        session_id=session_id_value,
        user_id=user.id,
        role="assistant",
        content=result.answer,
        citations_json=json.dumps(result.citations, ensure_ascii=False),
        trace_json=json.dumps(
            response_trace,
            ensure_ascii=False,
        ),
        status=turn_status,
        request_id=request_id,
    )
    user_row.status = "completed"
    db.add(assistant_row)
    await db.flush()
    assistant_message_id = assistant_row.id
    response_proposals = []
    for ordinal, spec in enumerate(proposals_to_persist):
        proposal = CreationProposalRecord(
            user_id=user.id,
            message_id=assistant_message_id,
            ordinal=ordinal,
            spec_json=json.dumps(spec, ensure_ascii=False),
        )
        db.add(proposal)
        await db.flush()
        response_proposals.append({"id": proposal.id, **spec})
    task_audit.status = (
        AuditStatus.WARNING.value if output_contract_incomplete else AuditStatus.SUCCESS.value
    )
    task_audit.result_json = json.dumps(
        {
            "answer_characters": len(result.answer),
            "citation_count": len(result.citations),
            "proposal_count": len(proposals_to_persist),
            "turn_status": turn_status,
        }
    )
    task_audit.latency_ms = round((time.perf_counter() - started) * 1000)
    await db.commit()
    return ChatResponse(
        session_id=session_id_value,
        message_id=assistant_message_id,
        answer=result.answer,
        status=turn_status,
        citations=result.citations,
        trace=response_trace,
        proposals=response_proposals,
    )


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str, payload: SessionUpdateRequest, user: CurrentUser, db: DbSession
):
    session = await db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    session.title = payload.title.strip()
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, user: CurrentUser, db: DbSession):
    session = await db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    await db.delete(session)
    await db.commit()


@router.post("/morning-briefing")
async def trigger_morning_briefing(request: Request, user: CurrentUser, db: DbSession):
    from uuid import uuid4

    from app.core.config import get_settings
    from app.services.morning_briefing import MorningBriefingService
    from app.tools.registry import ToolRegistry

    registry = getattr(request.app.state, "registry", None) or ToolRegistry()
    service = MorningBriefingService(get_settings(), registry)
    request_id = getattr(request.state, "request_id", None) or str(uuid4())
    return await service.generate_brief(
        user,
        db,
        request_id=request_id,
    )
