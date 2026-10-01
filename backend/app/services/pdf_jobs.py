"""Serial durable PDF worker, with fenced leases and per-page subprocess bounds."""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import and_, or_, select, update

from app.db.models import LocalSource, PdfIngestionJob
from app.services.local_sources import hash_content
from app.services.object_storage import object_storage_for
from app.services.pdf_ingestion import PageExtraction


def checkpoint_pages(job: PdfIngestionJob) -> list[dict]:
    value = json.loads(job.checkpoint_json or "[]")
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("invalid_checkpoint")
    return value


def public_job(job: PdfIngestionJob) -> dict:
    pages = checkpoint_pages(job)
    return {"id": job.id, "name": job.name, "status": job.status, "stage": job.stage,
            "pages": job.pages, "processed_pages": len(pages), "source_id": job.source_id,
            "error_code": job.error_code, "attempts": job.attempts,
            "page_results": [{key: page.get(key) for key in
                              ("page", "status", "confidence", "error_code", "ocr_rotation")}
                             for page in pages]}


async def claim(factory, now: float) -> tuple[str, str] | None:
    async with factory() as db:
        due = or_(PdfIngestionJob.status == "queued", and_(
            PdfIngestionJob.status == "running", PdfIngestionJob.lease_until < now))
        await db.execute(update(PdfIngestionJob).where(
            due, PdfIngestionJob.attempts >= 3).values(status="failed", error_code="retry_limit"))
        job = await db.scalar(select(PdfIngestionJob).where(
            due, PdfIngestionJob.attempts < 3).order_by(PdfIngestionJob.created_at).limit(1))
        if not job:
            await db.commit()
            return None
        token = str(uuid4())
        changed = await db.execute(update(PdfIngestionJob).where(
            PdfIngestionJob.id == job.id, due, PdfIngestionJob.attempts == job.attempts,
        ).values(status="running", lease_token=token, lease_until=now + 180,
                 attempts=job.attempts + 1))
        await db.commit()
        return (job.id, token) if changed.rowcount == 1 else None


async def active(factory, job_id: str, token: str) -> bool:
    async with factory() as db:
        return bool(await db.scalar(select(PdfIngestionJob.id).where(
            PdfIngestionJob.id == job_id, PdfIngestionJob.status == "running",
            PdfIngestionJob.lease_token == token)))


async def fenced_update(factory, job_id: str, token: str, **values) -> bool:
    async with factory() as db:
        result = await db.execute(update(PdfIngestionJob).where(
            PdfIngestionJob.id == job_id, PdfIngestionJob.status == "running",
            PdfIngestionJob.lease_token == token).values(**values))
        await db.commit()
        return result.rowcount == 1


async def _invoke(factory, job_id: str, token: str, path: Path, settings,
                  page: int | None = None) -> dict:
    command = [sys.executable, "-m", "app.services.pdf_ingestion", str(path)]
    if page is not None:
        command += ["--page", str(page)]
        if not settings.pdf_ocr_enabled:
            command += ["--no-ocr"]
        for flag, value in (("--tesseract", settings.pdf_tesseract_binary),
                            ("--pdftoppm", settings.pdf_pdftoppm_binary),
                            ("--tessdata", settings.pdf_tessdata_dir)):
            if value:
                command += [flag, str(value)]
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        cwd=str(Path(__file__).resolve().parents[2]))
    output = asyncio.create_task(process.communicate())
    started = time.monotonic()
    try:
        while not output.done():
            await asyncio.wait({output}, timeout=1)
            if not await active(factory, job_id, token):
                raise asyncio.CancelledError
            if time.monotonic() - started > 145:
                raise TimeoutError("pdf_page_timeout")
        stdout, _ = await output
        if process.returncode != 0 or len(stdout) > 2_000_000:
            raise ValueError("pdf_worker_output_invalid")
        result = json.loads(stdout)
        if not isinstance(result, dict):
            raise ValueError("pdf_worker_output_invalid")
        return result
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
        if not output.done():
            output.cancel()
        await asyncio.gather(output, return_exceptions=True)


async def execute_one(factory, settings, *, invoke=None) -> bool:
    claimed = await claim(factory, time.time())
    if not claimed:
        return False
    job_id, token = claimed
    invoke = invoke or _invoke
    path: Path | None = None
    temporary_path = False
    try:
        async with factory() as db:
            job = await db.get(PdfIngestionJob, job_id)
            completed = checkpoint_pages(job)
            total = job.pages
            owner = job.user_id
        path, temporary_path = await object_storage_for(settings).processing_path(owner, job_id)
        if not total:
            inspection = await invoke(factory, job_id, token, path, settings)
            total = inspection.get("pages", 0)
            if type(total) is not int or not 1 <= total <= 1000:
                raise ValueError("invalid_pdf")
            if not await fenced_update(factory, job_id, token, pages=total, stage="extract"):
                return True
        for number in range(len(completed) + 1, total + 1):
            result = await invoke(factory, job_id, token, path, settings, number)
            page_result = PageExtraction(**result)
            if page_result.page != number:
                raise ValueError("checkpoint_page_mismatch")
            completed.append(result)
            if not await fenced_update(factory, job_id, token,
                                       checkpoint_json=json.dumps(completed, ensure_ascii=False),
                                       lease_until=time.time() + 180):
                return True
        content = "\n\n".join(PageExtraction(**row).markdown() for row in completed).strip()
        if not content:
            await fenced_update(factory, job_id, token, status="needs_attention",
                                error_code="no_indexable_pages", lease_until=None)
            return True
        # SQL transaction publishes source and completion together. A retry can
        # resolve a same-owner digest, but never publishes a second source.
        async with factory() as db:
            locked = await db.execute(update(PdfIngestionJob).where(
                PdfIngestionJob.id == job_id, PdfIngestionJob.status == "running",
                PdfIngestionJob.lease_token == token).values(stage="publishing"))
            if locked.rowcount != 1:
                return True
            job = await db.get(PdfIngestionJob, job_id)
            digest = hash_content(content)
            source = await db.scalar(select(LocalSource).where(
                LocalSource.user_id == job.user_id, LocalSource.content_hash == digest))
            if source is None and job.source_id:
                source = await db.scalar(select(LocalSource).where(
                    LocalSource.id == job.source_id, LocalSource.user_id == job.user_id))
                if source:
                    source.content = content
                    source.content_hash = digest
            if source is None:
                source = LocalSource(user_id=job.user_id, name=job.name,
                                     content=content, content_hash=digest)
                db.add(source)
                await db.flush()
            job.source_id = source.id
            job.status = "completed" if all(PageExtraction(**row).indexable
                                             for row in completed) else "needs_attention"
            job.stage = "keyword_ready"
            job.error_code = None if job.status == "completed" else "pages_require_review"
            job.lease_until = None
            await db.commit()
    except asyncio.CancelledError:
        if await active(factory, job_id, token):
            await fenced_update(factory, job_id, token, status="queued", lease_until=None,
                                lease_token=None)
            raise
    except Exception as exc:
        # No document text, path or exception message in operational logs.
        logging.getLogger(__name__).warning("PDF worker failed: %s", type(exc).__name__)
        await fenced_update(factory, job_id, token, status="failed",
                            error_code="pdf_processing_failed", lease_until=None)
    finally:
        if temporary_path and path is not None:
            await asyncio.to_thread(path.unlink, missing_ok=True)
    return True


async def worker(factory, settings):
    while True:
        try:
            await execute_one(factory, settings)
        except Exception:
            logging.getLogger(__name__).warning("PDF queue will retry after storage error")
        await asyncio.sleep(2)
