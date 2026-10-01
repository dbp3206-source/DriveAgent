"""Authenticated, metadata-only release evidence, never private benchmark answers."""

from fastapi import APIRouter

from app.api.dependencies import CurrentUser
from app.core.config import PROJECT_ROOT, get_settings
from app.services.release_readiness import readiness

router = APIRouter(prefix="/api/release", tags=["release"])


@router.get("/readiness")
async def release_readiness(_user: CurrentUser):
    return readiness(PROJECT_ROOT, get_settings().data_dir / "release-evidence")
