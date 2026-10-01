
"""Provision the two user-approved Gate 2 QA sources without overwriting Drive files.

Dry-run is the default. ``--commit`` creates/reuses a dedicated Drive folder and
uploads only the exact hashed PDF/XLSX in the current golden manifest. The receipt
contains IDs and hashes, never OAuth tokens or source contents.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.auth.google_oauth import refresh_and_store_if_needed
from app.core.config import Settings
from app.db.models import User, UserRole
from app.db.session import SessionFactory

MANIFEST = ROOT / "backend" / "evals" / "golden_gate2.json"
RECEIPT = ROOT / "data" / "gate2-provisioning.json"
FOLDER_NAME = "DriveAgent Gate 2 QA"
DRIVE_FILE = "https://www.googleapis.com/auth/drive.file"
MIME = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
FIELDS = "id,name,mimeType,parents,size,md5Checksum,version,modifiedTime,appProperties"


def _hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sources() -> tuple[str, list[dict[str, Any]]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    unique: dict[str, dict[str, Any]] = {}
    for case in manifest["cases"]:
        for ref in case.get("source_refs", []):
            path = Path(ref["path"])
            if path.suffix.lower() not in MIME:
                continue
            if not path.is_file() or _hash(path, "sha256") != ref["sha256"]:
                raise ValueError(f"Missing or changed QA source: {path.name}")
            unique[str(path)] = {
                "path": path,
                "name": path.name,
                "sha256": ref["sha256"],
                # Drive exposes an MD5 checksum for verifying uploaded bytes.
                "md5": _hash(path, "md5"),
                "size": path.stat().st_size,
                "mime_type": MIME[path.suffix.lower()],
            }
    sources = list(unique.values())
    if {item["name"] for item in sources} != {"Evaluation-Harness.pdf", "budget.xlsx"}:
        raise ValueError("Gate 2 provisioning expects exactly the approved PDF and workbook")
    return str(manifest["version"]), sources


def _list(service: Any, query: str) -> list[dict[str, Any]]:
    response = service.files().list(
        q=query, spaces="drive", pageSize=100, fields=f"nextPageToken,files({FIELDS})"
    ).execute()
    if response.get("nextPageToken"):
        raise ValueError("Too many matching QA files; inspect Drive manually")
    return response.get("files", [])


def _folder(service: Any) -> dict[str, Any]:
    found = _list(
        service,
        "name = 'DriveAgent Gate 2 QA' and mimeType = "
        "'application/vnd.google-apps.folder' and trashed = false",
    )
    owned = [
        item for item in found
        if item.get("appProperties", {}).get("driveagent_qa") == "gate2"
    ]
    if len(owned) > 1:
        raise ValueError("Duplicate app-owned Gate 2 folders; inspect Drive manually")
    if owned:
        return owned[0]
    return service.files().create(
        body={
            "name": FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder",
            "appProperties": {"driveagent_qa": "gate2"},
        },
        fields=FIELDS,
    ).execute()


def _upload_or_reuse(service: Any, folder_id: str, source: dict[str, Any]) -> dict[str, Any]:
    escaped = source["name"].replace("\\", "\\\\").replace("'", "\\'")
    found = _list(
        service,
        f"name = '{escaped}' and '{folder_id}' in parents and trashed = false",
    )
    if len(found) > 1:
        raise ValueError(f"Duplicate QA source name in folder: {source['name']}")
    if found:
        item = found[0]
        if item.get("appProperties", {}).get("source_sha256") != source["sha256"]:
            raise ValueError(f"Existing QA source differs; refusing overwrite: {source['name']}")
    else:
        media = MediaFileUpload(
            str(source["path"]), mimetype=source["mime_type"], resumable=False
        )
        item = service.files().create(
            body={
                "name": source["name"],
                "parents": [folder_id],
                "appProperties": {
                    "driveagent_qa": "gate2",
                    "source_sha256": source["sha256"],
                },
            },
            media_body=media,
            fields=FIELDS,
        ).execute()
    item = service.files().get(fileId=item["id"], fields=FIELDS).execute()
    if item.get("md5Checksum") != source["md5"] or int(item.get("size", -1)) != source["size"]:
        raise ValueError(f"Drive checksum/size mismatch: {source['name']}")
    return {
        "name": source["name"],
        "file_id": item["id"],
        "version": item.get("version"),
        "modified_time": item.get("modifiedTime"),
        "sha256": source["sha256"],
        "md5_verified": True,
    }


async def _commit(user_id: str | None, version: str, sources: list[dict[str, Any]]) -> None:
    async with SessionFactory() as db:
        users = list((await db.scalars(select(User).where(User.is_active.is_(True)))).all())
        candidates = [user for user in users if user.id == user_id] if user_id else [
            user for user in users
            if user.role == UserRole.SUPER_ADMIN.value
            and user.encrypted_google_credentials
            and DRIVE_FILE in json.loads(user.oauth_scopes_json)
        ]
        if len(candidates) != 1:
            raise ValueError("Pass --user-id for exactly one active QA admin")
        user = candidates[0]
        if DRIVE_FILE not in json.loads(user.oauth_scopes_json):
            raise PermissionError("QA user has not granted drive.file; reconnect through OAuth")
        credentials = await refresh_and_store_if_needed(user, db, Settings())
        service = await asyncio.to_thread(
            build, "drive", "v3", credentials=credentials, cache_discovery=False
        )
        folder = await asyncio.to_thread(_folder, service)
        uploaded = [
            await asyncio.to_thread(_upload_or_reuse, service, folder["id"], source)
            for source in sources
        ]
        receipt = {
            "manifest_version": version,
            "folder_id": folder["id"],
            "sources": uploaded,
        }
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(
            {"status": "verified", "folder": FOLDER_NAME, "files": uploaded},
            ensure_ascii=False,
        ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--user-id", default=os.environ.get("DRIVE_AGENT_VERIFY_USER_ID"))
    args = parser.parse_args()
    version, sources = _sources()
    if not args.commit:
        print(json.dumps({
            "mode": "dry_run", "manifest_version": version,
            "sources": [{"name": item["name"], "size": item["size"]} for item in sources],
            "cloud_write": False,
        }, ensure_ascii=False))
        return
    try:
        asyncio.run(_commit(args.user_id, version, sources))
    except HttpError as exc:
        raise SystemExit(f"Google Drive returned HTTP {exc.resp.status}; no token logged") from None


if __name__ == "__main__":
    main()
