"""Read-only, bounded inventories of Veridra's owned PDF copies.

The Storage schema is metadata only and MUST NOT be modified. Physical deletion
belongs to PdfObjectStorage.delete_verified (Storage API on cloud). An inventory
or metadata disappearance alone never proves physical removal or backup erasure.
Call under the coordinator's owner fence; no age/consent is established here.
"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import CleanupJob, PdfIngestionJob
from app.services.cleanup_jobs import CleanupPlan, PurgeReference
from app.services.object_storage import (
    OBJECT_ID,
    LocalPdfObjectStorage,
    SupabasePdfObjectStorage,
)
from app.services.owner_admission import joined_thread
from app.services.retention_policy import (
    RetentionCandidate,
    RetentionKind,
    RetentionPolicyError,
    content_fingerprint,
    utc,
)

MAX_OBJECTS = 10_000
MAX_PLANS = 1_000
MAX_PLAN_BYTES = 1_000_000
TERMINAL = frozenset({"completed", "failed", "needs_attention"})


@dataclass(frozen=True)
class ObjectInventory:
    owner_id: str
    mode: str
    candidates: tuple[RetentionCandidate, ...]
    references: tuple[PurgeReference, ...]
    existing_job_ids: tuple[str, ...]


def _identity(value: str) -> None:
    if not isinstance(value, str) or not OBJECT_ID.fullmatch(value):
        raise RetentionPolicyError("retention_object_identity_invalid")


def _clock(value) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            pass
    if not isinstance(value, datetime):
        raise RetentionPolicyError("retention_object_age_unknown")
    return utc(value)


def _candidate(owner_id, job_id, stamp, metadata, *, active=False):
    record_id = f"pdf_objects:{job_id}"
    return RetentionCandidate(
        owner_id=owner_id, kind=RetentionKind.SOURCE, record_id=record_id,
        changed_at=stamp, fingerprint=content_fingerprint(
            owner_id=owner_id, kind=RetentionKind.SOURCE, record_id=record_id,
            changed_at=stamp, values={"copies": metadata},
        ), active=active,
    )


def _copy_fingerprint(owner_id, job_id, stamp, metadata):
    # Include the namespace, owner, identity and every physical metadata field.
    # An unchanged survivor can be resumed after the other approved copy was
    # unlinked; a replacement or newly introduced copy is never added to scope.
    return content_fingerprint(
        owner_id=owner_id, kind=RetentionKind.SOURCE, record_id=f"pdf_objects:{job_id}",
        changed_at=stamp, values={"copy": metadata},
    )


async def _jobs(db, owner_id, maximum):
    rows = await db.stream(select(PdfIngestionJob.id, PdfIngestionJob.status).where(
        PdfIngestionJob.user_id == owner_id,
    ).limit(maximum + 1).execution_options(yield_per=64))
    jobs = {}
    async for identity, status in rows:
        _identity(identity)
        if len(jobs) >= maximum:
            raise RetentionPolicyError("retention_object_inventory_too_large")
        jobs[identity] = status
    return jobs


async def _legacy_owners(db, identities):
    """Resolve root-file owners from IDs/digests only, never source content.

    Metadata from other owners is necessary to exclude their legacy root files.
    A plan is accepted only when its entire typed scope and stored digest agree.
    Unknown or conflicting ownership fails closed instead of guessing ownership.
    """
    if not identities:
        return {}
    ownership = {}
    ordered = sorted(identities)
    for start in range(0, len(ordered), 128):
        rows = await db.execute(select(PdfIngestionJob.id, PdfIngestionJob.user_id).where(
            PdfIngestionJob.id.in_(ordered[start:start + 128]),
        ))
        for identity, owner in rows:
            _identity(owner)
            ownership[identity] = owner
    if set(ownership) == set(identities):
        return ownership
    # No document bodies live in this ledger. Bound each fetched plan and the
    # number of plans; do not declare a truncated scan complete.
    query = select(
        CleanupJob.user_id, CleanupJob.approval_id, CleanupJob.plan_hash,
        func.substr(CleanupJob.plan_json, 1, MAX_PLAN_BYTES + 1),
    ).limit(MAX_PLANS + 1).execution_options(yield_per=8)
    rows = await db.stream(query)
    seen = 0
    async for owner, approval_id, plan_hash, body in rows:
        seen += 1
        if seen > MAX_PLANS or not isinstance(body, str) or len(body) > MAX_PLAN_BYTES:
            raise RetentionPolicyError("retention_object_inventory_too_large")
        try:
            plan = CleanupPlan.model_validate_json(body)
            if (hashlib.sha256(body.encode()).hexdigest() != plan_hash
                    or plan.snapshot.owner_id != owner
                    or plan.snapshot.approval_id != approval_id):
                raise ValueError
        except ValueError:
            raise RetentionPolicyError("retention_object_ownership_unverified") from None
        for ref in plan.external:
            if ref.kind != "pdf" or ref.object_id not in identities:
                continue
            if ref.object_id in ownership and ownership[ref.object_id] != ref.owner_id:
                raise RetentionPolicyError("retention_object_ownership_unverified")
            ownership[ref.object_id] = ref.owner_id
    if set(ownership) != set(identities):
        raise RetentionPolicyError("retention_object_ownership_unverified")
    return ownership


def _regular(path: Path, *, directory=False):
    if path.resolve() != path:
        raise RetentionPolicyError("retention_object_path_unsafe")
    metadata = path.lstat()
    if (stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            or getattr(metadata, "st_reparse_tag", 0)):
        raise RetentionPolicyError("retention_object_path_unsafe")
    if directory:
        if not stat.S_ISDIR(metadata.st_mode):
            raise RetentionPolicyError("retention_object_path_unsafe")
    elif not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise RetentionPolicyError("retention_object_path_unsafe")
    return metadata


def _file_name(name):
    if not isinstance(name, str) or not name.endswith(".pdf"):
        raise RetentionPolicyError("retention_object_path_unsafe")
    identity = name[:-4]
    _identity(identity)
    return identity


def _native_names(root, owner_id, maximum):
    try:
        _regular(root, directory=True)
    except FileNotFoundError:
        return (), ()
    own, legacy = [], []
    seen = 0
    with os.scandir(root) as entries:
        for entry in entries:
            seen += 1
            if seen > maximum:
                raise RetentionPolicyError("retention_object_inventory_too_large")
            if entry.name == owner_id:
                directory = root / owner_id
                _regular(directory, directory=True)
                with os.scandir(directory) as files:
                    for file in files:
                        if len(own) >= maximum:
                            raise RetentionPolicyError("retention_object_inventory_too_large")
                        own.append(_file_name(file.name))
            elif entry.name.endswith(".pdf"):
                legacy.append(_file_name(entry.name))
            else:
                # Only inspect root entry names. Other owners' directories are
                # not entered, stat'ed or read; malformed unknown files fail.
                _identity(entry.name)
                if not entry.is_dir(follow_symlinks=False):
                    raise RetentionPolicyError("retention_object_path_unsafe")
    return tuple(own), tuple(legacy)


def _native_metadata(storage, owner_id, own, legacy):
    copies = {}
    for identities, namespace in ((own, owner_id), (legacy, "")):
        for identity in identities:
            path = storage.root / namespace / f"{identity}.pdf"
            row = _regular(path)
            try:
                stamp = datetime.fromtimestamp(row.st_mtime, UTC)
            except (ValueError, OSError, OverflowError):
                raise RetentionPolicyError("retention_object_age_unknown") from None
            copies.setdefault(identity, []).append((stamp, {
                "namespace": namespace, "size": row.st_size, "device": row.st_dev,
                "inode": row.st_ino, "mtime_ns": row.st_mtime_ns, "ctime_ns": row.st_ctime_ns,
            }))
    return copies


async def _native(db, storage, owner_id, maximum):
    own, legacy = await joined_thread(_native_names, storage.root, owner_id, maximum)
    ownership = await _legacy_owners(db, set(legacy))
    if any(identity in own and ownership[identity] != owner_id for identity in legacy):
        # Existing delete_verified removes both current and legacy copies.
        raise RetentionPolicyError("retention_object_ownership_unverified")
    owned_legacy = tuple(identity for identity in legacy if ownership[identity] == owner_id)
    return await joined_thread(_native_metadata, storage, owner_id, own, owned_legacy)


async def _private_bucket(storage):
    try:
        async with httpx.AsyncClient(timeout=4, follow_redirects=False) as client:
            response = await client.get(
                f"{storage.base_url}/bucket/{quote(storage.bucket, safe='')}",
                headers=storage._headers(),
            )
        if response.status_code != 200 or response.json().get("public") is not False:
            raise RetentionPolicyError("retention_object_bucket_unverified")
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise RetentionPolicyError("retention_object_bucket_unverified") from None


async def _cloud(db, storage, owner_id, maximum):
    await _private_bucket(storage)
    # Only read Storage metadata. Owner IDs cannot contain LIKE wildcards; the
    # exact trailing slash prevents matching another owner's prefix.
    rows = await db.stream(text(
        "SELECT id, name, bucket_id, created_at, updated_at FROM storage.objects "
        "WHERE bucket_id=:bucket AND name LIKE :prefix ORDER BY name LIMIT :maximum"
    ).execution_options(yield_per=64), {
        "bucket": storage.bucket, "prefix": f"{owner_id}/%", "maximum": maximum + 1,
    })
    copies = {}
    seen = 0
    async for row in rows.mappings():
        seen += 1
        if seen > maximum:
            raise RetentionPolicyError("retention_object_inventory_too_large")
        name = row["name"]
        if (not isinstance(name, str) or not name.startswith(f"{owner_id}/")
                or row["bucket_id"] != storage.bucket):
            raise RetentionPolicyError("retention_object_path_unsafe")
        identity = _file_name(name[len(owner_id) + 1:])
        if identity in copies or not row["id"]:
            raise RetentionPolicyError("retention_object_inventory_invalid")
        created, updated = _clock(row["created_at"]), _clock(row["updated_at"])
        copies[identity] = [(max(created, updated), {
            "id": str(row["id"]), "name": name, "bucket_id": storage.bucket,
            "created_at": created, "updated_at": updated,
        })]
    return copies


async def object_inventory(db, storage, owner_id: str, *, max_objects=MAX_OBJECTS
                           ) -> ObjectInventory:
    """Complete metadata inventory, or error; no physical deletion or truncation.

    Existing owner job IDs let the coordinator require dependency-closed batches.
    Orphan namespace objects remain candidates: their owner is unambiguous from
    the exact owner/job.pdf path. Native legacy files instead need SQL/plan proof.
    Native current+legacy copies of one job share one candidate and newest age.
    """
    _identity(owner_id)
    if type(max_objects) is not int or not 1 <= max_objects <= MAX_OBJECTS:
        raise RetentionPolicyError("retention_object_bound_invalid")
    try:
        jobs = await _jobs(db, owner_id, max_objects)
        if isinstance(storage, LocalPdfObjectStorage):
            copies = await _native(db, storage, owner_id, max_objects)
            mode = "local"
        elif isinstance(storage, SupabasePdfObjectStorage):
            copies = await _cloud(db, storage, owner_id, max_objects)
            mode = "supabase"
        else:
            raise RetentionPolicyError("retention_object_backend_unsupported")
        if len(copies) > max_objects:
            raise RetentionPolicyError("retention_object_inventory_too_large")
        candidates, references = [], []
        for identity, records in sorted(copies.items()):
            stamp = max(record[0] for record in records)
            metadata = sorted((record[1] for record in records), key=lambda r: str(r))
            candidate = _candidate(owner_id, identity, stamp, metadata,
                                   active=identity in jobs and jobs[identity] not in TERMINAL)
            candidates.append(candidate)
            references.append(PurgeReference(
                kind="pdf", owner_id=owner_id, object_id=identity,
                fingerprint=candidate.fingerprint,
                copy_fingerprints=tuple(sorted(_copy_fingerprint(
                    owner_id, identity, copy_stamp, copy_metadata,
                ) for copy_stamp, copy_metadata in records)),
            ))
        return ObjectInventory(owner_id, mode, tuple(candidates), tuple(references),
                               tuple(sorted(jobs)))
    except RetentionPolicyError:
        raise
    except (OSError, SQLAlchemyError, ValueError, TypeError):
        raise RetentionPolicyError("retention_object_inventory_unavailable") from None


def validate_object_reference(reference: PurgeReference, current: ObjectInventory) -> bool:
    """Check a freshly inventoried snapshot under the owner fence, before API I/O.

    False means metadata is already absent, NOT proof of physical removal.
    Always finish with storage.delete_verified, including when this returns False.
    Re-inventory after SQL purge is supported: fingerprints contain file metadata
    only, not the job row that the critical transaction just removed. A crash
    between the two native unlinks may leave an unchanged subset of the approved
    copies. The frozen per-copy proofs permit only those survivors. Older refs
    without per-copy proofs retain the strict aggregate-fingerprint rule.
    """
    if reference.kind != "pdf" or reference.owner_id != current.owner_id:
        raise RetentionPolicyError("retention_object_snapshot_invalid")
    for actual in current.references:
        if actual.object_id == reference.object_id:
            if reference.fingerprint is None:
                raise RetentionPolicyError("retention_object_snapshot_changed")
            if reference.copy_fingerprints and actual.copy_fingerprints:
                if not set(actual.copy_fingerprints).issubset(reference.copy_fingerprints):
                    raise RetentionPolicyError("retention_object_snapshot_changed")
            elif actual.fingerprint != reference.fingerprint:
                raise RetentionPolicyError("retention_object_snapshot_changed")
            return True
    return False
