"""Human-only data cleanup: signed session + trusted origin + explicit approval."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dependencies import CurrentUser, is_trusted_ui_origin
from app.core.config import get_settings
from app.db.models import CleanupJob
from app.services import cleanup_jobs
from app.services.owner_admission import AdmissionError
from app.services.retention_policy import RetentionPolicyError


class PrivateRoute(APIRoute):
    async def handle(self, scope, receive, send):
        # Method rejection happens before FastAPI's endpoint handler.
        try:
            await super().handle(scope, receive, send)
        except StarletteHTTPException as error:
            error.headers = {**(error.headers or {}), "Cache-Control": "no-store, private"}
            raise

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private(request):
            try:
                response = await handler(request)
            except HTTPException as error:
                error.headers = {**(error.headers or {}), "Cache-Control": "no-store, private"}
                raise
            except RequestValidationError:
                return JSONResponse({"detail": "Dữ liệu xác nhận không hợp lệ."}, status_code=422,
                                    headers={"Cache-Control": "no-store, private"})
            response.headers["Cache-Control"] = "no-store, private"
            return response
        return private


router = APIRouter(prefix="/api/retention", tags=["retention"], route_class=PrivateRoute)
JobId = Annotated[str, Path(pattern=r"^[a-f0-9-]{36}$")]


class ConfirmCleanup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=10, max_length=100_000)
    confirmed: StrictBool

    @field_validator("confirmed")
    @classmethod
    def deliberate_confirmation(cls, value):
        if value is not True:
            raise ValueError("Cần xác nhận trước khi xóa.")
        return value


def service(request, response, *, mutation=False):
    response.headers["Cache-Control"] = "no-store, private"
    if mutation and not is_trusted_ui_origin(request, get_settings()):
        raise HTTPException(403, "Cần xác nhận từ giao diện Veridra.",
                            headers={"Cache-Control": "no-store"})
    coordinator = getattr(request.app.state, "retention_coordinator", None)
    if coordinator is None:
        raise HTTPException(503, "Chưa thể kiểm tra dữ liệu cần dọn. Hãy thử lại sau.",
                            headers={"Cache-Control": "no-store"})
    return coordinator


def safe_error(error):
    code = getattr(error, "code", str(error))
    if isinstance(error, AdmissionError):
        return HTTPException(409, str(error), headers={"Cache-Control": "no-store"})
    changed = code in {"retention_preview_changed", "retention_approval_expired",
                       "invalid_retention_approval", "cleanup_approval_expired"}
    conflict = changed or code.startswith("cleanup_") or code == "retention_owner_busy"
    message = ("Danh sách đã thay đổi hoặc hết hạn. Hãy xem lại rồi xác nhận."
               if changed else "Đang có việc cần hoàn tất. Hãy kiểm tra trạng thái rồi thử lại."
               if conflict else "Chưa kiểm tra được đầy đủ các bản lưu. Chưa có xác nhận xóa mới.")
    return HTTPException(409 if conflict else 503, message,
                         headers={"Cache-Control": "no-store"})


@router.get("/preview")
async def preview(request: Request, response: Response, user: CurrentUser):
    coordinator = service(request, response)
    try:
        return await coordinator.preview(user.id)
    except (RetentionPolicyError, cleanup_jobs.CleanupStateError, AdmissionError) as error:
        raise safe_error(error) from None


@router.post("/confirm", status_code=202)
async def confirm(payload: ConfirmCleanup, request: Request, response: Response, user: CurrentUser):
    coordinator = service(request, response, mutation=True)
    try:
        identity = await coordinator.confirm(user.id, payload.token)
        return {"id": identity, "status": "queued"}
    except (RetentionPolicyError, cleanup_jobs.CleanupStateError, AdmissionError) as error:
        raise safe_error(error) from None


@router.get("/status")
async def latest(request: Request, response: Response, user: CurrentUser):
    coordinator = service(request, response)
    async with coordinator.factory() as db:
        identity = await db.scalar(select(CleanupJob.id).where(
            CleanupJob.user_id == user.id,
        ).order_by(CleanupJob.created_at.desc()).limit(1))
    return {"job": await cleanup_jobs.status(coordinator.factory, user.id, identity)
            if identity else None}


@router.get("/jobs/{job_id}")
async def status(job_id: JobId, request: Request, response: Response, user: CurrentUser):
    coordinator = service(request, response)
    result = await cleanup_jobs.status(coordinator.factory, user.id, job_id)
    if result is None:
        raise HTTPException(404, "Không tìm thấy lần dọn dữ liệu này.")
    return result


@router.post("/jobs/{job_id}/retry", status_code=202)
async def retry(job_id: JobId, request: Request, response: Response, user: CurrentUser):
    coordinator = service(request, response, mutation=True)
    try:
        async with coordinator.gate.exclusive(user.id):
            await cleanup_jobs.retry(coordinator.factory, user.id, job_id)
    except (cleanup_jobs.CleanupStateError, AdmissionError) as error:
        raise safe_error(error) from None
    return {"id": job_id, "status": "queued"}


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: JobId, request: Request, response: Response, user: CurrentUser):
    coordinator = service(request, response, mutation=True)
    try:
        async with coordinator.gate.exclusive(user.id):
            await cleanup_jobs.cancel(coordinator.factory, user.id, job_id)
    except (cleanup_jobs.CleanupStateError, AdmissionError) as error:
        raise safe_error(error) from None
    return {"id": job_id, "status": "cancelled"}
