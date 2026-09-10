"""Chat history and inert creation proposals, scoped to the authenticated user."""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from google.genai.errors import APIError
from sqlalchemy import select

from app.agent.orchestrator import AgentNotConfiguredError, AgentOrchestrator
from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.db.models import ChatSession, CreationProposalRecord, Message
from app.tools.contracts import ToolError

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(user: CurrentUser, db: DbSession):
    rows = list(
        (
            await db.scalars(
                select(ChatSession)
                .where(ChatSession.user_id == user.id)
                .order_by(ChatSession.updated_at.desc())
            )
        ).all()
    )
    return rows


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
            {"id": proposal.id, **json.loads(proposal.spec_json)}
        )
    return [
        MessageResponse(
            id=row.id,
            role=row.role,
            content=row.content,
            citations=json.loads(row.citations_json),
            trace=json.loads(row.trace_json),
            proposals=proposals_by_message.get(row.id, []),
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, user: CurrentUser, db: DbSession):
    session = None
    created_session = not bool(payload.session_id)
    if payload.session_id:
        session = await db.scalar(
            select(ChatSession).where(
                ChatSession.id == payload.session_id, ChatSession.user_id == user.id
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    else:
        session = ChatSession(user_id=user.id, title=payload.message.strip()[:80])
        db.add(session)
        await db.flush()

    user_row = Message(
        session_id=session.id,
        user_id=user.id,
        role="user",
        content=payload.message.strip(),
    )
    db.add(user_row)
    await db.commit()

    async def discard_failed_turn() -> None:
        """Do not leave an unmatched user bubble when the agent never replied."""

        await db.rollback()
        persisted = await db.get(Message, user_row.id)
        if persisted is not None:
            await db.delete(persisted)
        if created_session:
            empty_session = await db.get(ChatSession, session.id)
            if empty_session is not None:
                await db.delete(empty_session)
        await db.commit()

    orchestrator: AgentOrchestrator = request.app.state.orchestrator
    try:
        result = await orchestrator.run(
            user=user,
            session_id=session.id,
            request_id=request.state.request_id,
            user_message=payload.message.strip(),
            model_name=payload.model,
        )
    except AgentNotConfiguredError as exc:
        await discard_failed_turn()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APIError as exc:
        await discard_failed_turn()
        provider_status = exc.code
        messages = {
            429: "Gemini đã hết hạn mức hoặc đang giới hạn tốc độ. Hãy thử lại sau.",
            503: "Gemini hiện quá tải. Drive vẫn dùng được; hãy gửi lại câu hỏi sau ít phút.",
            401: "Google không chấp nhận API key Gemini. Kiểm tra cấu hình trên máy.",
            403: "Project Gemini chưa có quyền sử dụng model đã chọn.",
            404: "Model Gemini đã chọn không khả dụng với project hiện tại.",
            400: "Gemini từ chối định dạng yêu cầu. Cần kiểm tra cấu hình tích hợp.",
        }
        logger.warning(
            "Gemini rejected request; status=%s request_id=%s",
            provider_status,
            request.state.request_id,
        )
        raise HTTPException(
            status_code=503 if provider_status in {429, 503} else 502,
            detail=messages.get(provider_status, "Gemini tạm thời không trả lời được.")
            + f" Request ID: {request.state.request_id}",
        ) from None
    except ToolError:
        await discard_failed_turn()
        raise
    except Exception as exc:
        await discard_failed_turn()
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
    assistant_row = Message(
        session_id=session.id,
        user_id=user.id,
        role="assistant",
        content=result.answer,
        citations_json=json.dumps(result.citations, ensure_ascii=False),
        trace_json=json.dumps(
            response_trace,
            ensure_ascii=False,
        ),
    )
    db.add(assistant_row)
    await db.flush()
    response_proposals = []
    for ordinal, spec in enumerate(result.proposals):
        proposal = CreationProposalRecord(
            user_id=user.id,
            message_id=assistant_row.id,
            ordinal=ordinal,
            spec_json=json.dumps(spec, ensure_ascii=False),
        )
        db.add(proposal)
        await db.flush()
        response_proposals.append({"id": proposal.id, **spec})
    await db.commit()
    return ChatResponse(
        session_id=session.id,
        message_id=assistant_row.id,
        answer=result.answer,
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
    from app.core.config import get_settings
    from app.services.morning_briefing import MorningBriefingService

    service = MorningBriefingService(get_settings(), request.app.state.registry)
    return await service.generate_brief(
        user,
        db,
        request_id=request.state.request_id,
    )
