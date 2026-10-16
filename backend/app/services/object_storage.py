"""Private PDF object storage with local and Supabase implementations."""

import asyncio
import json
import os
import re
import stat
from pathlib import Path
from tempfile import mkstemp
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.services.owner_admission import joined_thread

OBJECT_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class ObjectStorageError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class PdfObjectStorage:
    async def initialize(self) -> None:
        raise NotImplementedError

    async def put(self, owner: str, job_id: str, data: bytes) -> None:
        raise NotImplementedError

    async def get(self, owner: str, job_id: str) -> bytes:
        raise NotImplementedError

    async def delete(self, owner: str, job_id: str) -> None:
        raise NotImplementedError

    async def exists(self, owner: str, job_id: str) -> bool:
        raise NotImplementedError

    async def delete_verified(self, owner: str, job_id: str) -> None:
        """Internal runner only, under its approval/admission fence; no consent here."""
        try:
            await self.delete(owner, job_id)
        except (httpx.HTTPError, OSError):
            raise ObjectStorageError("object_delete_failed") from None
        if await self.exists(owner, job_id):
            raise ObjectStorageError("object_delete_unverified")

    async def processing_path(self, owner: str, job_id: str) -> tuple[Path, bool]:
        data = await self.get(owner, job_id)
        descriptor, raw_path = mkstemp(prefix="veridra-pdf-", suffix=".pdf")
        os.close(descriptor)
        path = Path(raw_path)
        try:
            # This temporary path is unlinked by the cancellation handler.
            # Join first so a late writer cannot recreate it after that unlink.
            await joined_thread(path.write_bytes, data, wait_on_cancel=True)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path, True


class LocalPdfObjectStorage(PdfObjectStorage):
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, owner: str, job_id: str) -> Path:
        if not OBJECT_ID.fullmatch(owner) or not OBJECT_ID.fullmatch(job_id):
            raise ObjectStorageError("invalid_object_identity")
        unresolved = self.root / owner / f"{job_id}.pdf"
        path = unresolved.resolve()
        # Require the exact owner namespace, not merely any path under root.
        # Resolving a file symlink or an owner-directory junction must never
        # turn a read/write/delete into an operation on another owner's data.
        if path != unresolved:
            raise ObjectStorageError("invalid_object_identity")
        return path

    def _legacy_path(self, job_id: str) -> Path:
        if not OBJECT_ID.fullmatch(job_id):
            raise ObjectStorageError("invalid_object_identity")
        unresolved = self.root / f"{job_id}.pdf"
        path = unresolved.resolve()
        if path != unresolved:
            raise ObjectStorageError("invalid_object_identity")
        return path

    async def _existing_path(self, owner: str, job_id: str) -> Path:
        current = self._path(owner, job_id)
        if await asyncio.to_thread(current.is_file):
            return current
        legacy = self._legacy_path(job_id)
        if await asyncio.to_thread(legacy.is_file):
            return legacy
        raise ObjectStorageError("object_not_found")

    async def initialize(self) -> None:
        await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)

    async def put(self, owner: str, job_id: str, data: bytes) -> None:
        path = self._path(owner, job_id)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await joined_thread(path.write_bytes, data)

    async def get(self, owner: str, job_id: str) -> bytes:
        return await asyncio.to_thread((await self._existing_path(owner, job_id)).read_bytes)

    async def delete(self, owner: str, job_id: str) -> None:
        current = self._path(owner, job_id)
        legacy = self._legacy_path(job_id)
        await joined_thread(current.unlink, missing_ok=True)
        await joined_thread(legacy.unlink, missing_ok=True)

    async def exists(self, owner: str, job_id: str) -> bool:
        # Validate BOTH paths first, including legacy aliases, even when one
        # already exists. Never follow an alias into another owner's namespace.
        paths = self._path(owner, job_id), self._legacy_path(job_id)

        def present():
            found = False
            for path in paths:
                try:
                    metadata = path.stat()
                except (FileNotFoundError, NotADirectoryError):
                    continue
                if not stat.S_ISREG(metadata.st_mode):
                    raise ObjectStorageError("object_probe_failed")
                found = True
            return found

        try:
            return await asyncio.to_thread(present)
        except OSError:
            raise ObjectStorageError("object_probe_failed") from None

    async def processing_path(self, owner: str, job_id: str) -> tuple[Path, bool]:
        return await self._existing_path(owner, job_id), False


class SupabasePdfObjectStorage(PdfObjectStorage):
    def __init__(self, settings: Settings):
        if settings.supabase_service_role_key is None:
            raise ObjectStorageError("storage_not_configured")
        self.base_url = settings.supabase_url.rstrip("/") + "/storage/v1"
        self.bucket = settings.supabase_storage_bucket
        self.secret = settings.supabase_service_role_key.get_secret_value()
        self.maximum = settings.max_download_mb * 1024 * 1024

    def _headers(self, **extra: str) -> dict[str, str]:
        return {
            "apikey": self.secret,
            "Authorization": f"Bearer {self.secret}",
            **extra,
        }

    def _object(self, owner: str, job_id: str) -> str:
        if not OBJECT_ID.fullmatch(owner) or not OBJECT_ID.fullmatch(job_id):
            raise ObjectStorageError("invalid_object_identity")
        return f"{quote(owner, safe='')}/{quote(job_id, safe='')}.pdf"

    async def initialize(self) -> None:
        payload = {
            "id": self.bucket,
            "name": self.bucket,
            "public": False,
            "file_size_limit": self.maximum,
            "allowed_mime_types": ["application/pdf"],
        }
        async with httpx.AsyncClient(timeout=15) as client:
            existing = await client.get(
                f"{self.base_url}/bucket/{quote(self.bucket, safe='')}",
                headers=self._headers(),
            )
            if existing.status_code == 200:
                if existing.json().get("public") is not False:
                    raise ObjectStorageError("storage_bucket_not_private")
                return
            if existing.status_code != 404:
                raise ObjectStorageError("storage_bucket_unavailable")
            response = await client.post(
                f"{self.base_url}/bucket", headers=self._headers(), json=payload
            )
            if response.status_code == 409:
                # Another creator won the race; conflict alone proves neither
                # availability nor privacy. Read the winning bucket before use.
                verified = await client.get(
                    f"{self.base_url}/bucket/{quote(self.bucket, safe='')}",
                    headers=self._headers(),
                )
                if verified.status_code != 200:
                    raise ObjectStorageError("storage_bucket_unavailable")
                if verified.json().get("public") is not False:
                    raise ObjectStorageError("storage_bucket_not_private")
        if response.status_code not in {200, 201, 409}:
            raise ObjectStorageError("storage_bucket_unavailable")

    async def put(self, owner: str, job_id: str, data: bytes) -> None:
        if not data or len(data) > self.maximum:
            raise ObjectStorageError("object_size_invalid")
        await self.initialize()
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                f"{self.base_url}/object/{self.bucket}/{self._object(owner, job_id)}",
                headers=self._headers(**{"Content-Type": "application/pdf", "x-upsert": "false"}),
                content=data,
            )
        if response.status_code not in {200, 201}:
            raise ObjectStorageError(
                "object_already_exists" if response.status_code == 409 else "object_upload_failed"
            )

    async def get(self, owner: str, job_id: str) -> bytes:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.get(
                f"{self.base_url}/object/authenticated/{self.bucket}/"
                f"{self._object(owner, job_id)}",
                headers=self._headers(),
            )
        if response.status_code == 404:
            raise ObjectStorageError("object_not_found")
        if response.status_code != 200 or len(response.content) > self.maximum:
            raise ObjectStorageError("object_download_failed")
        return response.content

    async def delete(self, owner: str, job_id: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.delete(
                f"{self.base_url}/object/{self.bucket}/{self._object(owner, job_id)}",
                headers=self._headers(),
            )
        if response.status_code not in {200, 204, 404}:
            raise ObjectStorageError("object_delete_failed")

    async def exists(self, owner: str, job_id: str) -> bool:
        identity = self._object(owner, job_id)
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                # A missing bucket, failed credential or gateway 404 must not be
                # interpreted as proof that this particular PDF was deleted.
                bucket = await client.get(
                    f"{self.base_url}/bucket/{quote(self.bucket, safe='')}",
                    headers=self._headers(),
                )
                if bucket.status_code != 200 or bucket.json().get("public") is not False:
                    raise ObjectStorageError("object_probe_failed")
                async with client.stream(
                    "GET", f"{self.base_url}/object/authenticated/{self.bucket}/{identity}",
                    headers=self._headers(**{"Range": "bytes=0-0", "Cache-Control": "no-cache"}),
                ) as response:
                    if response.status_code in {200, 206}:
                        return True  # Never read or log the private PDF body.
                    if response.status_code not in {400, 404}:
                        raise ObjectStorageError("object_probe_failed")
                    error_body = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=1024):
                        error_body.extend(chunk)
                        if len(error_body) > 2048:
                            raise ObjectStorageError("object_probe_failed")
                    error = json.loads(error_body)
                    if not isinstance(error, dict):
                        raise ObjectStorageError("object_probe_failed")
                    if response.status_code == 404 and error.get("code") == "NoSuchKey":
                        return False
                    # Storage still supports legacy SDK errors. Require both
                    # the resource-specific code and its explicit 404 status;
                    # never accept a generic gateway/router 404 or status alone.
                    legacy_status = error.get("statusCode", error.get("httpStatusCode"))
                    legacy_code = error.get("error", error.get("code"))
                    if str(legacy_status) == "404" and legacy_code == "not_found":
                        return False
                    raise ObjectStorageError("object_probe_failed")
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise ObjectStorageError("object_probe_failed") from None


def object_storage_for(settings: Settings) -> PdfObjectStorage:
    if getattr(settings, "storage_backend", "local") == "supabase":
        return SupabasePdfObjectStorage(settings)
    return LocalPdfObjectStorage(settings.data_dir / "pdf-inputs")


async def initialize_object_storage(settings: Settings) -> None:
    await object_storage_for(settings).initialize()


async def probe_object_storage(settings: Settings) -> bool:
    """Read-only readiness check: never create a bucket during health probes."""
    storage = object_storage_for(settings)
    if isinstance(storage, LocalPdfObjectStorage):
        return await asyncio.to_thread(storage.root.is_dir)
    async with httpx.AsyncClient(timeout=4) as client:
        response = await client.get(
            f"{storage.base_url}/bucket/{quote(storage.bucket, safe='')}",
            headers=storage._headers(),
        )
    return response.status_code == 200 and response.json().get("public") is False
