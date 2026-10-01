import asyncio
import json
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.local_sources import enqueue_pdf, pdf_job_action, pdf_original
from app.db.models import Base, LocalSource, PdfIngestionJob, User
from app.services.pdf_jobs import claim, execute_one, fenced_update, public_job


@pytest_asyncio.fixture
async def storage(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(User(id="owner", email="owner@example.test", display_name="Owner"))
        db.add(PdfIngestionJob(id="job", user_id="owner", name="sample.pdf",
                               content_hash="a" * 64, size_bytes=100))
        await db.commit()
    object_folder = tmp_path / "pdf-inputs" / "owner"
    object_folder.mkdir(parents=True)
    (object_folder / "job.pdf").write_bytes(b"%PDF-1.7 test fixture")
    yield factory, SimpleNamespace(data_dir=tmp_path), "job"
    await engine.dispose()


async def fake_invoke(_factory, _job, _token, _path, _settings, page=None):
    if page is None:
        return {"pages": 2}
    return {"page": page, "status": "text", "text": f"Source page {page}: revenue 100.",
            "confidence": None, "error_code": None}


async def test_worker_publishes_once_without_provider_or_cloud(storage):
    factory, settings, job_id = storage
    assert await execute_one(factory, settings, invoke=fake_invoke)
    assert not await execute_one(factory, settings, invoke=fake_invoke)
    async with factory() as db:
        job = await db.get(PdfIngestionJob, job_id)
        sources = list(await db.scalars(select(LocalSource)))
        assert job.status == "completed" and len(sources) == 1
        assert "<!-- page:2 -->" in sources[0].content
        assert "text" not in public_job(job)["page_results"][0]


async def test_expired_lease_is_fenced_and_checkpoint_survives(storage):
    factory, settings, job_id = storage
    claimed = await claim(factory, 1)
    assert claimed
    checkpoint = [await fake_invoke(None, None, None, None, None, 1)]
    await fenced_update(factory, job_id, claimed[1], pages=2,
                        checkpoint_json=json.dumps(checkpoint))
    recovered = await claim(factory, 182)
    assert recovered and recovered[1] != claimed[1]
    assert not await fenced_update(factory, job_id, claimed[1], status="completed")
    await fenced_update(factory, job_id, recovered[1], lease_until=0)
    calls = []

    async def invoke(*args):
        calls.append(args[-1])
        return await fake_invoke(*args)

    await execute_one(factory, settings, invoke=invoke)
    assert calls == [2]


async def test_missing_ocr_never_publishes_empty_success(storage):
    factory, settings, job_id = storage

    async def invoke(*args):
        page = args[-1] if isinstance(args[-1], int) else None
        if page is None:
            return {"pages": 1}
        return {"page": 1, "status": "needs_ocr", "text": "", "confidence": None,
                "error_code": "ocr_dependencies_missing"}

    await execute_one(factory, settings, invoke=invoke)
    async with factory() as db:
        job = await db.get(PdfIngestionJob, job_id)
        assert job.status == "needs_attention" and job.source_id is None
        assert not list(await db.scalars(select(LocalSource)))


async def test_cancel_requires_owner_and_stale_worker_cannot_publish(storage):
    factory, _settings, job_id = storage
    claimed = await claim(factory, 1)
    async with factory() as db:
        with pytest.raises(HTTPException) as caught:
            await pdf_job_action(job_id, "cancel", SimpleNamespace(id="other"), db)
        assert caught.value.status_code == 404
        result = await pdf_job_action(job_id, "cancel", SimpleNamespace(id="owner"), db)
        assert result["status"] == "cancelled"
    assert not await fenced_update(factory, job_id, claimed[1], status="completed")


async def test_resume_reprocesses_uncertain_pages_only(storage):
    factory, _settings, job_id = storage
    async with factory() as db:
        job = await db.get(PdfIngestionJob, job_id)
        job.status = "needs_attention"
        job.pages = 2
        job.checkpoint_json = json.dumps([
            await fake_invoke(None, None, None, None, None, 1),
            {"page": 2, "status": "low_confidence", "text": "uncertain", "confidence": 30,
             "error_code": None}])
        await db.commit()
        result = await pdf_job_action(job_id, "resume", SimpleNamespace(id="owner"), db)
        assert result["status"] == "queued" and result["processed_pages"] == 1


async def test_active_lease_is_not_claimed_twice(storage):
    factory, _settings, _job_id = storage
    assert await claim(factory, 1)
    assert await claim(factory, 2) is None


async def test_concurrent_uploads_cannot_exceed_owner_queue_limit(storage, monkeypatch):
    factory, settings, _job_id = storage
    monkeypatch.setattr("app.api.local_sources.get_settings", lambda: settings)

    class Objects:
        async def put(self, *_args):
            await asyncio.sleep(0)

        async def delete(self, *_args):
            pass

    monkeypatch.setattr("app.api.local_sources.object_storage_for", lambda _: Objects())

    async def upload_one(index):
        async with factory() as db:
            try:
                return await enqueue_pdf(f"sample-{index}.pdf", f"%PDF-1.7 {index}".encode(),
                                         SimpleNamespace(id="owner"), db)
            except HTTPException as exc:
                return exc.status_code

    results = await asyncio.gather(*(upload_one(index) for index in range(5)))
    assert sum(isinstance(result, dict) for result in results) == 3
    assert results.count(429) == 2
    async with factory() as db:
        assert len(list(await db.scalars(select(PdfIngestionJob)))) == 4


async def test_original_pdf_is_owner_scoped_download(storage, monkeypatch):
    factory, settings, job_id = storage
    monkeypatch.setattr("app.api.local_sources.get_settings", lambda: settings)
    folder = settings.data_dir / "pdf-inputs" / "owner"
    folder.mkdir(parents=True, exist_ok=True)
    original = folder / f"{job_id}.pdf"
    original.write_bytes(b"%PDF-1.7 original evidence")
    async with factory() as db:
        with pytest.raises(HTTPException) as caught:
            await pdf_original(job_id, SimpleNamespace(id="other"), db)
        assert caught.value.status_code == 404
        response = await pdf_original(job_id, SimpleNamespace(id="owner"), db)
        assert response.path == original
        assert response.headers["content-disposition"].startswith("attachment;")
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-security-policy"] == "sandbox"


async def test_reextract_uses_original_and_updates_existing_source(storage):
    factory, settings, job_id = storage
    await execute_one(factory, settings, invoke=fake_invoke)
    async with factory() as db:
        job = await db.get(PdfIngestionJob, job_id)
        original_source = job.source_id
        result = await pdf_job_action(job_id, "reextract", SimpleNamespace(id="owner"), db)
        assert result["processed_pages"] == 0 and result["status"] == "queued"

    async def changed(*args):
        result = await fake_invoke(*args)
        if "text" in result:
            result["text"] += " Correct column reading order."
        return result

    await execute_one(factory, settings, invoke=changed)
    async with factory() as db:
        job = await db.get(PdfIngestionJob, job_id)
        sources = list(await db.scalars(select(LocalSource)))
        assert job.source_id == original_source and len(sources) == 1
        assert "Correct column reading order" in sources[0].content
