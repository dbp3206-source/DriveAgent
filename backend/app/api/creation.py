"""Prepare a persisted chat proposal without trusting a browser-supplied spec.

Preparation is not execution. The separate Docs/Sheets approve endpoint requires
the exact reviewed digest; refreshing or reopening chat cannot approve a write.
"""

import json

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.agent.creation import CreationAnswer
from app.api.dependencies import CurrentUser, DbSession
from app.api.documents import invoke
from app.db.models import CreationProposalRecord
from app.tools.documents import DocumentPrepare
from app.tools.sheets import SpreadsheetPrepare

router = APIRouter(prefix="/api/creation", tags=["creation"])


@router.post("/proposals/{proposal_id}/prepare")
async def prepare(proposal_id: str, request: Request, user: CurrentUser, db: DbSession):
    record = await db.scalar(
        select(CreationProposalRecord).where(
            CreationProposalRecord.id == proposal_id,
            CreationProposalRecord.user_id == user.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản đề xuất.")
    raw_proposal = json.loads(record.spec_json)
    # Old chat history remains visible after retiring creative generators, but it
    # must never be parsed as a currently executable contract.
    if raw_proposal.get("kind") not in {
        "document",
        "spreadsheet",
        "document_edit",
        "spreadsheet_edit",
    }:
        raise HTTPException(
            status_code=410,
            detail="Google Slides và Visual Studio đã được rút khỏi phạm vi sản phẩm.",
        )
    proposal = CreationAnswer(answer="Preview", proposals=[raw_proposal]).proposals[0]
    # A stable key binds all retries/reloads to this one proposal, never a new file.
    if proposal.kind == "document":
        payload = DocumentPrepare(
            request_key=record.id,
            action="create",
            document=proposal.document,
        )
        return await invoke("docs_prepare", payload, request, user, db)
    if proposal.kind == "document_edit":
        return await invoke(
            "docs_prepare",
            DocumentPrepare(request_key=record.id, action="edit", edit=proposal.document_edit),
            request,
            user,
            db,
        )
    if proposal.kind == "spreadsheet":
        payload = SpreadsheetPrepare(request_key=record.id, spreadsheet=proposal.spreadsheet)
        return await invoke("sheets_prepare", payload, request, user, db)
    if proposal.kind == "spreadsheet_edit":
        return await invoke(
            "sheets_prepare",
            SpreadsheetPrepare(
                request_key=record.id, action="edit", edit=proposal.spreadsheet_edit
            ),
            request,
            user,
            db,
        )
    raise HTTPException(status_code=422, detail="Loại đề xuất không được hỗ trợ.")
