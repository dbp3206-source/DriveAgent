import asyncio
import hashlib
import json
from contextlib import suppress
from pathlib import PurePath
from urllib.parse import quote
from uuid import uuid4
from weakref import WeakValueDictionary

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession, require_permission
from app.auth.permissions import RAG_READ, RAG_WRITE, permissions_for_role
from app.core.config import get_settings
from app.db.models import AuditEvent, LocalSource, PdfIngestionJob, User
from app.services.local_sources import MAX_BYTES, excluded_ocr_source, extract_text, hash_content
from app.services.object_storage import (
    LocalPdfObjectStorage,
    ObjectStorageError,
    object_storage_for,
)
from app.services.pdf_ingestion import MAX_PDF_BYTES
from app.services.pdf_jobs import public_job
from app.services.user_inference import user_runtime_settings

router = APIRouter(prefix="/api/local-sources", tags=["local-sources"])
_pdf_upload_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


@router.get("", dependencies=[Depends(require_permission(RAG_READ))])
async def listing(user: CurrentUser, db: DbSession):
    rows = await db.scalars(
        select(LocalSource)
        .where(LocalSource.user_id == user.id)
        .order_by(LocalSource.created_at.desc())
        .limit(200)
    )
    return [{"id": row.id, "name": row.name, "characters": len(row.content)} for row in rows
            if not excluded_ocr_source(row, get_settings())]


@router.post("")
async def upload(name: str, request: Request, user: CurrentUser, db: DbSession):
    if RAG_WRITE not in permissions_for_role(user.role):
        raise HTTPException(403, "Bạn không có quyền import tài liệu.")
    if not name.strip() or len(name) > 240 or any(c in name for c in "/\\\r\n\x00"):
        raise HTTPException(400, "Tên tệp không hợp lệ.")
    # Read raw stream: rejects oversized bodies before buffering an entire multipart upload.
    is_pdf = PurePath(name).suffix.lower() == ".pdf"
    maximum = MAX_PDF_BYTES if is_pdf else MAX_BYTES
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > maximum:
            raise HTTPException(413, "PDF vượt 25 MiB." if is_pdf else "Tệp vượt 2 MB.")
        data.extend(chunk)
    if is_pdf:
        return await enqueue_pdf(name, bytes(data), user, db)
    text = await asyncio.to_thread(extract_text, name, bytes(data))
    digest = hash_content(text)
    row = await db.scalar(
        select(LocalSource).where(
            LocalSource.user_id == user.id, LocalSource.content_hash == digest
        )
    )
    if row is None:
        row = LocalSource(user_id=user.id, name=name, content=text, content_hash=digest)
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
        except IntegrityError:
            row = await db.scalar(
                select(LocalSource).where(
                    LocalSource.user_id == user.id, LocalSource.content_hash == digest
                )
            )
            if row is None:
                raise HTTPException(409, "Tài liệu vừa thay đổi, hãy thử lại.") from None
    db.add(
        AuditEvent(
            request_id=request.state.request_id,
            user_id=user.id,
            role=user.role,
            tool_name="local_source_import",
            status="success",
            result_json=json.dumps({"source_id": row.id, "characters": len(text)}),
        )
    )
    await db.commit()

    rag_service = getattr(request.app.state, "rag_service", None)
    if rag_service:
        try:
            from app.core.config import get_settings
            from app.tools.contracts import ToolContext

            await rag_service.index_local_source(
                row,
                ToolContext(
                    request_id=request.state.request_id,
                    user=user,
                    db=db,
                    settings=await user_runtime_settings(db, user.id, get_settings()),
                    source="local_import",
                ),
            )
        except Exception:
            # Fallback gracefully if embedding quota or vector index fails
            pass

    return {"id": row.id, "name": row.name, "characters": len(row.content)}


async def enqueue_pdf(name, data, user, db):
    # One local app uses a per-owner lock; PostgreSQL additionally serializes
    # reservations across app processes by locking the durable owner row.
    lock = _pdf_upload_locks.setdefault(user.id, asyncio.Lock())
    async with lock:
        if db.get_bind().dialect.name == "postgresql":
            await db.scalar(select(User.id).where(User.id == user.id).with_for_update())
        return await _enqueue_pdf(name, data, user, db)


async def _enqueue_pdf(name, data, user, db):
    if not data[:1024].lstrip().startswith(b"%PDF-"):
        raise HTTPException(400, "Tệp không có chữ ký PDF hợp lệ.")
    digest = hashlib.sha256(data).hexdigest()
    existing = await db.scalar(select(PdfIngestionJob).where(
        PdfIngestionJob.user_id == user.id, PdfIngestionJob.content_hash == digest))
    if existing:
        return {"kind": "pdf_job", **public_job(existing)}
    pending = await db.scalar(select(func.count()).select_from(PdfIngestionJob).where(
        PdfIngestionJob.user_id == user.id,
        PdfIngestionJob.status.in_(["queued", "running"])))
    used = await db.scalar(select(func.sum(PdfIngestionJob.size_bytes)).where(
        PdfIngestionJob.user_id == user.id))
    if pending >= 4 or (used or 0) + len(data) > 200 * 1024 * 1024:
        raise HTTPException(429, "Tối đa 4 PDF đang xử lý và 200 MiB PDF mỗi tài khoản.")
    settings = get_settings()
    storage = object_storage_for(settings)
    job = PdfIngestionJob(id=str(uuid4()), user_id=user.id, name=name,
                          content_hash=digest, size_bytes=len(data))
    try:
        await storage.put(user.id, job.id, data)
    except ObjectStorageError as exc:
        raise HTTPException(503, "Kho tệp riêng tạm thời chưa sẵn sàng.") from exc
    try:
        db.add(job)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        with suppress(ObjectStorageError):
            await storage.delete(user.id, job.id)
        existing = await db.scalar(select(PdfIngestionJob).where(
            PdfIngestionJob.user_id == user.id, PdfIngestionJob.content_hash == digest))
        if not existing:
            raise HTTPException(409, "Upload vừa thay đổi, hãy thử lại.") from None
        job = existing
    except Exception:
        with suppress(ObjectStorageError):
            await storage.delete(user.id, job.id)
        raise
    return {"kind": "pdf_job", **public_job(job)}


@router.get("/pdf-jobs", dependencies=[Depends(require_permission(RAG_READ))])
async def pdf_jobs(user: CurrentUser, db: DbSession):
    jobs = await db.scalars(select(PdfIngestionJob).where(
        PdfIngestionJob.user_id == user.id).order_by(PdfIngestionJob.created_at.desc()).limit(50))
    return [public_job(job) for job in jobs]


@router.post("/pdf-jobs/{job_id}/{action}",
             dependencies=[Depends(require_permission(RAG_WRITE))])
async def pdf_job_action(job_id: str, action: str, user: CurrentUser, db: DbSession):
    job = await db.scalar(select(PdfIngestionJob).where(
        PdfIngestionJob.id == job_id, PdfIngestionJob.user_id == user.id))
    if not job:
        raise HTTPException(404, "Không tìm thấy tác vụ PDF của bạn.")
    if action == "cancel":
        allowed = ["queued", "running"]
        status = "cancelled"
    elif action in {"retry", "resume", "reextract"}:
        allowed = ["failed", "cancelled", "needs_attention"]
        if action == "reextract":
            allowed += ["completed"]
        status = "queued"
    else:
        raise HTTPException(400, "Hành động PDF không hợp lệ.")
    values = {"status": status, "lease_token": None, "lease_until": None, "error_code": None}
    if status == "queued":
        values["attempts"] = 0
        # Retain safe checkpoints, but reprocess unverified/error pages after
        # installing OCR. Drop only from the first incomplete page onward.
        pages = [] if action == "reextract" else json.loads(job.checkpoint_json or "[]")
        retained = []
        for page in pages:
            if page.get("status") not in {"text", "ocr"}:
                break
            retained.append(page)
        values["checkpoint_json"] = json.dumps(retained, ensure_ascii=False)
        if action == "reextract":
            values["stage"] = "queued"
    changed = await db.execute(update(PdfIngestionJob).where(
        PdfIngestionJob.id == job_id, PdfIngestionJob.user_id == user.id,
        PdfIngestionJob.status.in_(allowed)).values(**values))
    if changed.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, "Trạng thái đã đổi; hãy tải lại tác vụ.")
    await db.commit()
    await db.refresh(job)
    return public_job(job)


@router.get("/pdf-jobs/{job_id}/original",
            dependencies=[Depends(require_permission(RAG_READ))])
async def pdf_original(job_id: str, user: CurrentUser, db: DbSession):
    job = await db.scalar(select(PdfIngestionJob).where(
        PdfIngestionJob.id == job_id, PdfIngestionJob.user_id == user.id))
    if not job:
        raise HTTPException(404, "Không tìm thấy PDF của bạn.")
    storage = object_storage_for(get_settings())
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox",
    }
    try:
        if isinstance(storage, LocalPdfObjectStorage):
            path, _temporary = await storage.processing_path(user.id, job.id)
            return FileResponse(
                path,
                media_type="application/pdf",
                filename=job.name,
                content_disposition_type="attachment",
                headers=headers,
            )
        data = await storage.get(user.id, job.id)
    except ObjectStorageError as exc:
        raise HTTPException(404, "Tệp PDF gốc không còn khả dụng.") from exc
    headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(job.name)}"
    # Bytes are proxied only after the backend has enforced database ownership.
    return Response(data, media_type="application/pdf", headers=headers)


@router.get(
    "/{source_id}/text",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_permission(RAG_READ))],
)
async def read(source_id: str, user: CurrentUser, db: DbSession):
    row = await db.scalar(
        select(LocalSource).where(LocalSource.id == source_id, LocalSource.user_id == user.id)
    )
    if row is None:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    if excluded_ocr_source(row, get_settings()):
        raise HTTPException(409,
                            "Bản OCR cũ không còn được dùng; hãy trích xuất lại lớp văn bản PDF.")
    return PlainTextResponse(
        row.content, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    )
