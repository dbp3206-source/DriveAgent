import httpx
import pytest
import respx

from app.core.config import Settings
from app.services.object_storage import (
    LocalPdfObjectStorage,
    ObjectStorageError,
    SupabasePdfObjectStorage,
)


async def test_local_pdf_storage_is_owner_scoped_and_keeps_legacy_read_compatibility(tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.initialize()
    await storage.put("owner-a", "job-one", b"%PDF-1.7 private")
    assert await storage.get("owner-a", "job-one") == b"%PDF-1.7 private"
    with pytest.raises(ObjectStorageError):
        await storage.get("owner-b", "job-one")
    with pytest.raises(ObjectStorageError):
        await storage.put("../escape", "job-two", b"data")

    legacy = tmp_path / "objects" / "job-old.pdf"
    legacy.write_bytes(b"legacy")
    assert await storage.get("owner-a", "job-old") == b"legacy"
    await storage.delete("owner-a", "job-old")
    assert not legacy.exists()


@respx.mock
async def test_supabase_storage_uses_private_authenticated_routes_and_backend_secret():
    settings = Settings(
        _env_file=None,
        storage_backend="supabase",
        supabase_url="https://project-ref.supabase.co",
        supabase_service_role_key="backend-secret",
    )
    storage = SupabasePdfObjectStorage(settings)
    bucket = respx.post("https://project-ref.supabase.co/storage/v1/bucket").mock(
        return_value=httpx.Response(409)
    )
    upload = respx.post(
        "https://project-ref.supabase.co/storage/v1/object/veridra-private/owner-a/job-one.pdf"
    ).mock(return_value=httpx.Response(200, json={"Key": "owner-a/job-one.pdf"}))
    download = respx.get(
        "https://project-ref.supabase.co/storage/v1/object/authenticated/"
        "veridra-private/owner-a/job-one.pdf"
    ).mock(return_value=httpx.Response(200, content=b"%PDF-1.7 private"))
    deletion = respx.delete(
        "https://project-ref.supabase.co/storage/v1/object/"
        "veridra-private/owner-a/job-one.pdf"
    ).mock(return_value=httpx.Response(200, json={"message": "Successfully deleted"}))

    await storage.initialize()
    await storage.put("owner-a", "job-one", b"%PDF-1.7 private")
    assert await storage.get("owner-a", "job-one") == b"%PDF-1.7 private"
    await storage.delete("owner-a", "job-one")

    for route in (bucket, upload, download, deletion):
        assert route.called
        request = route.calls.last.request
        assert request.headers["authorization"] == "Bearer backend-secret"
        assert request.headers["apikey"] == "backend-secret"
    assert upload.calls.last.request.headers["x-upsert"] == "false"
    assert "/public/" not in str(download.calls.last.request.url)


@respx.mock
async def test_supabase_storage_returns_safe_error_codes_only():
    settings = Settings(
        _env_file=None,
        storage_backend="supabase",
        supabase_url="https://project-ref.supabase.co",
        supabase_service_role_key="backend-secret",
    )
    storage = SupabasePdfObjectStorage(settings)
    respx.get(
        "https://project-ref.supabase.co/storage/v1/object/authenticated/"
        "veridra-private/owner-a/missing.pdf"
    ).mock(return_value=httpx.Response(404, text="private provider detail"))
    with pytest.raises(ObjectStorageError) as missing:
        await storage.get("owner-a", "missing")
    assert missing.value.code == "object_not_found"
    assert "private provider detail" not in str(missing.value)
