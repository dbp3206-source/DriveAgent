"""Private PDF object storage with local and Supabase implementations."""

import asyncio
import os
import re
from pathlib import Path
from tempfile import mkstemp
from urllib.parse import quote

import httpx

from app.core.config import Settings

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

    async def processing_path(self, owner: str, job_id: str) -> tuple[Path, bool]:
        data = await self.get(owner, job_id)
        descriptor, raw_path = mkstemp(prefix="veridra-pdf-", suffix=".pdf")
        os.close(descriptor)
        path = Path(raw_path)
        try:
            await asyncio.to_thread(path.write_bytes, data)
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
        path = (self.root / owner / f"{job_id}.pdf").resolve()
        if not path.is_relative_to(self.root):
            raise ObjectStorageError("invalid_object_identity")
        return path

    def _legacy_path(self, job_id: str) -> Path:
        if not OBJECT_ID.fullmatch(job_id):
            raise ObjectStorageError("invalid_object_identity")
        return (self.root / f"{job_id}.pdf").resolve()

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
        await asyncio.to_thread(path.write_bytes, data)

    async def get(self, owner: str, job_id: str) -> bytes:
        return await asyncio.to_thread((await self._existing_path(owner, job_id)).read_bytes)

    async def delete(self, owner: str, job_id: str) -> None:
        await asyncio.to_thread(self._path(owner, job_id).unlink, missing_ok=True)
        await asyncio.to_thread(self._legacy_path(job_id).unlink, missing_ok=True)

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
            response = await client.post(
                f"{self.base_url}/bucket", headers=self._headers(), json=payload
            )
        if response.status_code not in {200, 201, 409}:
            raise ObjectStorageError("storage_bucket_unavailable")

    async def put(self, owner: str, job_id: str, data: bytes) -> None:
        if not data or len(data) > self.maximum:
            raise ObjectStorageError("object_size_invalid")
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


def object_storage_for(settings: Settings) -> PdfObjectStorage:
    if getattr(settings, "storage_backend", "local") == "supabase":
        return SupabasePdfObjectStorage(settings)
    return LocalPdfObjectStorage(settings.data_dir / "pdf-inputs")


async def initialize_object_storage(settings: Settings) -> None:
    await object_storage_for(settings).initialize()
