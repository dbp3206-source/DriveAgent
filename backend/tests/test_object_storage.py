import os
import subprocess

import httpx
import pytest
import respx

from app.core.config import Settings
from app.services.object_storage import (
    LocalPdfObjectStorage,
    ObjectStorageError,
    SupabasePdfObjectStorage,
    probe_object_storage,
)


@pytest.mark.parametrize(
    "status,public,expected",
    [(200, False, True), (200, True, False), (403, False, False), (503, False, False)],
)
@respx.mock
async def test_storage_probe_is_read_only(status, public, expected):
    settings = Settings(
        _env_file=None,
        storage_backend="supabase",
        supabase_url="https://project-ref.supabase.co",
        supabase_service_role_key="backend-secret",
    )
    read = respx.get("https://project-ref.supabase.co/storage/v1/bucket/veridra-private").mock(
        return_value=httpx.Response(status, json={"public": public})
    )
    assert await probe_object_storage(settings) is expected
    assert read.call_count == 1
    assert len(respx.calls) == 1


async def test_local_probe_does_not_create_missing_storage(tmp_path, monkeypatch):
    settings = Settings(_env_file=None)
    storage = LocalPdfObjectStorage(tmp_path / "pdf-inputs")
    monkeypatch.setattr("app.services.object_storage.object_storage_for", lambda _: storage)
    assert not await probe_object_storage(settings)
    assert not (tmp_path / "pdf-inputs").exists()
    await LocalPdfObjectStorage(tmp_path / "pdf-inputs").initialize()
    assert await probe_object_storage(settings)


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


@pytest.mark.parametrize("operation", ["get", "put", "delete", "exists", "delete_verified",
                                       "processing_path"])
async def test_local_storage_rejects_owner_directory_alias(tmp_path, operation):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.initialize()
    await storage.put("owner-b", "job-one", b"private owner-b canary")
    alias = storage.root / "owner-a"
    try:
        alias.symlink_to(storage.root / "owner-b", target_is_directory=True)
    except (OSError, NotImplementedError):
        if os.name != "nt":
            pytest.skip("Directory symlinks unavailable on this host")
        # Windows junctions exercise the same redirect without requiring the
        # elevated privilege needed to create file/directory symlinks.
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(storage.root / "owner-b")],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")
    with pytest.raises(ObjectStorageError, match="invalid_object_identity"):
        if operation == "put":
            await storage.put("owner-a", "job-one", b"unauthorized overwrite")
        else:
            await getattr(storage, operation)("owner-a", "job-one")
    assert await storage.get("owner-b", "job-one") == b"private owner-b canary"


@pytest.mark.parametrize("operation", ["get", "delete", "exists", "delete_verified",
                                       "processing_path"])
async def test_local_storage_rejects_legacy_file_alias_without_touching_canary(tmp_path, operation):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.initialize()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"private outside canary")
    alias = storage.root / "job-old.pdf"
    try:
        alias.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("File symlinks unavailable on this host")
    # Delete validates both paths before removing even the owned object.
    await storage.put("owner-a", "job-old", b"owned canary")
    if operation not in {"delete", "delete_verified"}:
        (storage.root / "owner-a" / "job-old.pdf").unlink()
    with pytest.raises(ObjectStorageError, match="invalid_object_identity"):
        await getattr(storage, operation)("owner-a", "job-old")
    assert outside.read_bytes() == b"private outside canary"
    assert alias.is_symlink()
    if operation in {"delete", "delete_verified"}:
        assert await storage.get("owner-a", "job-old") == b"owned canary"


@respx.mock
async def test_supabase_storage_uses_private_authenticated_routes_and_backend_secret():
    settings = Settings(
        _env_file=None,
        storage_backend="supabase",
        supabase_url="https://project-ref.supabase.co",
        supabase_service_role_key="backend-secret",
    )
    storage = SupabasePdfObjectStorage(settings)
    respx.get("https://project-ref.supabase.co/storage/v1/bucket/veridra-private").mock(
        side_effect=[
            httpx.Response(404),
            httpx.Response(200, json={"public": False}),
            httpx.Response(200, json={"public": False}),
        ]
    )
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
        "https://project-ref.supabase.co/storage/v1/object/veridra-private/owner-a/job-one.pdf"
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


async def test_local_verified_delete_reads_back_current_and_legacy_without_touching_other_owner(
    tmp_path,
):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.initialize()
    await storage.put("owner-a", "synthetic-one", b"%PDF synthetic owner A")
    await storage.put("owner-b", "synthetic-one", b"%PDF synthetic owner B")
    legacy = storage.root / "synthetic-one.pdf"
    legacy.write_bytes(b"%PDF synthetic legacy")
    assert await storage.exists("owner-a", "synthetic-one")
    await storage.delete_verified("owner-a", "synthetic-one")
    assert not await storage.exists("owner-a", "synthetic-one")
    assert not legacy.exists()
    assert await storage.exists("owner-b", "synthetic-one")
    assert await storage.get("owner-b", "synthetic-one") == b"%PDF synthetic owner B"
    await storage.delete_verified("owner-a", "synthetic-one")  # Safe continuation after lost reply.


@pytest.mark.parametrize("status,code,expected", [
    (200, None, True), (206, None, True), (404, "NoSuchKey", False),
    (404, "NoSuchBucket", None), (404, "InvalidJWT", None), (403, "AccessDenied", None),
    (500, "InternalError", None), (302, None, None), (404, "not_found", None),
])
@respx.mock
async def test_supabase_existence_is_bounded_private_and_does_not_accept_arbitrary_404(
    status, code, expected,
):
    storage = SupabasePdfObjectStorage(Settings(
        _env_file=None, storage_backend="supabase", supabase_url="https://project-ref.supabase.co",
        supabase_service_role_key="synthetic-test-secret",
    ))
    respx.get("https://project-ref.supabase.co/storage/v1/bucket/veridra-private").mock(
        return_value=httpx.Response(200, json={"public": False}),
    )
    route = respx.get("https://project-ref.supabase.co/storage/v1/object/authenticated/"
                      "veridra-private/owner-a/synthetic-one.pdf").mock(return_value=(
        httpx.Response(status, content=b"PRIVATE_PDF_MUST_NOT_BE_LOGGED") if code is None else
        httpx.Response(status, json={"code": code, "message": "PRIVATE_ERROR_MUST_NOT_BE_LOGGED"})
    ))
    if expected is None:
        with pytest.raises(ObjectStorageError, match="^object_probe_failed$"):
            await storage.exists("owner-a", "synthetic-one")
    else:
        assert await storage.exists("owner-a", "synthetic-one") is expected
    assert route.call_count == 1
    assert route.calls.last.request.headers["range"] == "bytes=0-0"
    assert route.calls.last.request.headers["cache-control"] == "no-cache"
    assert route.calls.last.request.headers["authorization"] == "Bearer synthetic-test-secret"


@respx.mock
async def test_delete_success_is_not_claimed_if_object_still_exists():
    storage = SupabasePdfObjectStorage(Settings(
        _env_file=None, storage_backend="supabase", supabase_url="https://project-ref.supabase.co",
        supabase_service_role_key="synthetic-test-secret",
    ))
    respx.delete("https://project-ref.supabase.co/storage/v1/object/"
                 "veridra-private/owner-a/synthetic-one.pdf").mock(return_value=httpx.Response(204))
    respx.get("https://project-ref.supabase.co/storage/v1/bucket/veridra-private").mock(
        return_value=httpx.Response(200, json={"public": False}),
    )
    respx.get("https://project-ref.supabase.co/storage/v1/object/authenticated/"
              "veridra-private/owner-a/synthetic-one.pdf").mock(return_value=httpx.Response(206))
    with pytest.raises(ObjectStorageError, match="^object_delete_unverified$"):
        await storage.delete_verified("owner-a", "synthetic-one")


@pytest.mark.parametrize("http_status", [400, 404])
@respx.mock
async def test_supabase_legacy_missing_object_requires_explicit_code_and_resource_status(
    http_status,
):
    storage = SupabasePdfObjectStorage(Settings(
        _env_file=None, storage_backend="supabase", supabase_url="https://project-ref.supabase.co",
        supabase_service_role_key="synthetic-test-secret",
    ))
    respx.get("https://project-ref.supabase.co/storage/v1/bucket/veridra-private").mock(
        return_value=httpx.Response(200, json={"public": False}),
    )
    respx.get("https://project-ref.supabase.co/storage/v1/object/authenticated/"
              "veridra-private/owner-a/synthetic-one.pdf").mock(return_value=httpx.Response(
        http_status, json={"statusCode": "404", "error": "not_found"},
    ))
    assert not await storage.exists("owner-a", "synthetic-one")


@pytest.mark.parametrize("bucket_status,public", [(404, False), (200, True), (401, False)])
@respx.mock
async def test_unavailable_or_public_bucket_cannot_prove_an_object_absent(bucket_status, public):
    storage = SupabasePdfObjectStorage(Settings(
        _env_file=None, storage_backend="supabase", supabase_url="https://project-ref.supabase.co",
        supabase_service_role_key="synthetic-test-secret",
    ))
    respx.get("https://project-ref.supabase.co/storage/v1/bucket/veridra-private").mock(
        return_value=httpx.Response(bucket_status, json={"public": public}),
    )
    with pytest.raises(ObjectStorageError, match="^object_probe_failed$"):
        await storage.exists("owner-a", "synthetic-one")
    assert len(respx.calls) == 1


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


@respx.mock
async def test_existing_private_bucket_does_not_get_recreated():
    storage = SupabasePdfObjectStorage(
        Settings(
            _env_file=None,
            storage_backend="supabase",
            supabase_url="https://project-ref.supabase.co",
            supabase_service_role_key="backend-secret",
        )
    )
    existing = respx.get("https://project-ref.supabase.co/storage/v1/bucket/veridra-private").mock(
        return_value=httpx.Response(200, json={"public": False})
    )
    creation = respx.post("https://project-ref.supabase.co/storage/v1/bucket").mock(
        return_value=httpx.Response(400)
    )
    await storage.initialize()
    assert existing.called and not creation.called
    existing.return_value = httpx.Response(200, json={"public": True})
    with pytest.raises(ObjectStorageError, match="storage_bucket_not_private"):
        await storage.initialize()


@pytest.mark.parametrize(
    "status, metadata, code",
    [
        (200, {"public": True}, "storage_bucket_not_private"),
        (200, {}, "storage_bucket_not_private"),
        (403, {}, "storage_bucket_unavailable"),
        (404, {}, "storage_bucket_unavailable"),
        (503, {}, "storage_bucket_unavailable"),
    ],
)
@respx.mock
async def test_bucket_creation_conflict_requires_verified_private_bucket(status, metadata, code):
    storage = SupabasePdfObjectStorage(
        Settings(
            _env_file=None,
            storage_backend="supabase",
            supabase_url="https://project-ref.supabase.co",
            supabase_service_role_key="backend-secret",
        )
    )
    existing = respx.get("https://project-ref.supabase.co/storage/v1/bucket/veridra-private").mock(
        side_effect=[httpx.Response(404), httpx.Response(status, json=metadata)],
    )
    respx.post("https://project-ref.supabase.co/storage/v1/bucket").mock(
        return_value=httpx.Response(409),
    )
    with pytest.raises(ObjectStorageError, match=code):
        await storage.initialize()
    assert existing.call_count == 2
