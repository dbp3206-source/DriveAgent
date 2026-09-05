"""API tìm kiếm RAG có citation."""

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUser, DbSession
from app.api.drive import execute
from app.api.schemas import RagSearchRequest, RagSearchResponse
from app.services.rag import SearchKnowledgeInput

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/search", response_model=RagSearchResponse)
async def search_rag(payload: RagSearchRequest, request: Request, user: CurrentUser, db: DbSession):
    return await execute(
        request,
        user,
        db,
        "rag_search",
        SearchKnowledgeInput(**payload.model_dump()).model_dump(mode="json"),
    )
