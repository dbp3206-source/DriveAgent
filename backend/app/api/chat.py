"""Chat API lưu raw messages trước/sau khi chạy LangGraph."""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.agent.orchestrator import AgentNotConfiguredError, AgentOrchestrator
from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    SessionResponse,
)
from app.db.models import ChatSession, Message

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
    return [
        MessageResponse(
            id=row.id,
            role=row.role,
            content=row.content,
            citations=json.loads(row.citations_json),
            trace=json.loads(row.trace_json),
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, user: CurrentUser, db: DbSession):
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

    orchestrator: AgentOrchestrator = request.app.state.orchestrator
    try:
        result = await orchestrator.run(
            user=user,
            session_id=session.id,
            request_id=request.state.request_id,
            user_message=payload.message.strip(),
        )
    except AgentNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # Không phản chiếu lỗi SDK/provider có thể chứa metadata nhạy cảm về client.
        logger.exception("Agent thất bại; request_id=%s", request.state.request_id)
        raise HTTPException(
            status_code=502,
            detail=f"Agent không thể hoàn tất. Request ID: {request.state.request_id}",
        ) from exc

    assistant_row = Message(
        session_id=session.id,
        user_id=user.id,
        role="assistant",
        content=result.answer,
        citations_json=json.dumps(result.citations, ensure_ascii=False),
        trace_json=json.dumps(
            [{"stage": "plan", "steps": result.plan}] + result.trace,
            ensure_ascii=False,
        ),
    )
    db.add(assistant_row)
    await db.commit()
    return ChatResponse(
        session_id=session.id,
        message_id=assistant_row.id,
        answer=result.answer,
        citations=result.citations,
        trace=[{"stage": "plan", "steps": result.plan}] + result.trace,
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, user: CurrentUser, db: DbSession):
    session = await db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    await db.delete(session)
    await db.commit()
