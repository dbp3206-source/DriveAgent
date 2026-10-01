from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import CurrentUser, is_trusted_ui_origin
from app.core.config import get_settings
from app.services.protocols import token_signer

router = APIRouter(prefix="/api/protocols", tags=["protocols"])


@router.post("/token")
async def issue_token(request: Request, user: CurrentUser):
    settings = get_settings()
    if not is_trusted_ui_origin(request, settings):
        raise HTTPException(403, "Token phải được yêu cầu từ giao diện local.")
    token = token_signer(settings).dumps({"sub": user.id, "scope": "knowledge:read"})
    return JSONResponse(
        {"token": token, "expires_in": 3600, "scope": "knowledge:read"},
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )
