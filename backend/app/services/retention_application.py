"""Exact application-row purge inside the coordinator's critical transaction.

No commit, file deletion, vector side effects, identity/credential mutation or
Google/model calls. Consent, cross-store completeness, cache reset and the owner
admission fence must be established by the coordinator, never by the model.
"""

from datetime import UTC, datetime, timedelta
from math import isfinite

from sqlalchemy import delete, select, text

from app.db import models as m
from app.services.cleanup_jobs import PurgeReference
from app.services.retention_inventory import POLICIES, application_inventory
from app.services.retention_policy import CONTENT_RETENTION_DAYS, RetentionPolicyError, utc

MODELS = {model.__tablename__: model for model, _kind, _clock in POLICIES}
DELETE_ORDER = (
    m.ResponseFeedback, m.CreationProposalRecord, m.ChatTask, m.Message, m.ChatSession,
    m.DocumentChunk, m.DriveFileIndex, m.PdfIngestionJob, m.LocalSource,
    m.LongTermMemory, m.SavedArtifact, m.CompanyProfile, m.ScheduledJob,
    m.AuditEvent, m.GraphCheckpoint,
)


async def _dependencies(db, owner_id, chosen):
    # Unlike a user's logical relation, a CASCADE FK can erase foreign-owned
    # rows too if corrupt data were inserted elsewhere. Check those IDs without
    # fetching any foreign content, before the first actual deletion.
    relations = (
        (m.ChatSession, m.Message, m.Message.session_id),
        (m.ChatSession, m.ChatTask, m.ChatTask.session_id),
        (m.Message, m.ResponseFeedback, m.ResponseFeedback.message_id),
        (m.Message, m.CreationProposalRecord, m.CreationProposalRecord.message_id),
        (m.LocalSource, m.PdfIngestionJob, m.PdfIngestionJob.source_id),
    )
    for parent, child, field in relations:
        ids = chosen.get(parent.__tablename__, ())
        if not ids:
            continue
        linked = (await db.execute(select(child.id, child.user_id).where(field.in_(ids)))).all()
        for identity, linked_owner in linked:
            if linked_owner != owner_id:
                raise RetentionPolicyError("retention_foreign_dependency")
            if identity not in chosen.get(child.__tablename__, ()):
                raise RetentionPolicyError("retention_dependency_not_selected")
    file_ids = set(await db.scalars(select(m.DriveFileIndex.drive_file_id).where(
        m.DriveFileIndex.user_id == owner_id,
        m.DriveFileIndex.id.in_(chosen.get("drive_file_index", ())),
    )))
    file_ids.update(f"local:{identity}" for identity in chosen.get("local_sources", ()))
    if file_ids:
        for model in (m.DriveFileIndex, m.DocumentChunk):
            identities = await db.scalars(select(model.id).where(
                model.user_id == owner_id, model.drive_file_id.in_(file_ids),
            ))
            if any(identity not in chosen.get(model.__tablename__, ()) for identity in identities):
                raise RetentionPolicyError("retention_dependency_not_selected")


async def application_purge_references(db, owner_id, approved):
    """Derive exact external references BEFORE deleting SQL rows; no side effects."""
    chosen = {}
    for item in approved:
        name, identity = item.record_id.split(":", 1)
        if name not in MODELS:
            raise RetentionPolicyError("retention_application_entity_unknown")
        chosen.setdefault(name, set()).add(identity)
    refs = []
    for identity in await db.scalars(select(m.PdfIngestionJob.id).where(
        m.PdfIngestionJob.user_id == owner_id,
        m.PdfIngestionJob.id.in_(chosen.get("pdf_ingestion_jobs", ())),
    )):
        refs.append(PurgeReference(kind="pdf", owner_id=owner_id, object_id=identity))
    if db.bind.dialect.name == "sqlite":
        for model, kind in ((m.DocumentChunk, "drive_chunks"),
                            (m.LongTermMemory, "agent_memories")):
            for identity in await db.scalars(select(model.id).where(
                model.user_id == owner_id, model.id.in_(chosen.get(model.__tablename__, ())),
            )):
                refs.append(PurgeReference(kind=kind, owner_id=owner_id, object_id=identity))
    return tuple(refs)


async def purge_application(db, owner_id, approved, *, now):
    if type(now) not in {int, float} or not isfinite(now) or now < 0:
        raise RetentionPolicyError("invalid_retention_time")
    approved = tuple(approved)
    cutoff = datetime.fromtimestamp(now, UTC) - timedelta(days=CONTENT_RETENTION_DAYS)
    keys = [(item.kind.value, item.record_id) for item in approved]
    if len(set(keys)) != len(keys) or any(utc(item.changed_at) > cutoff for item in approved):
        raise RetentionPolicyError("retention_preview_changed")
    if db.bind.dialect.name == "sqlite":
        # Force SQLite's actual write transaction, even if this owner has no
        # CleanupJob rows in an isolated contract test. No clocks/counters reset.
        await db.execute(text(
            "UPDATE cleanup_jobs SET attempts=attempts WHERE user_id=:owner"
        ), {"owner": owner_id})
    inventory = await application_inventory(db, owner_id, lock=True)
    if inventory.owner_busy:
        raise RetentionPolicyError("retention_owner_busy")
    current = {item.key: item for item in inventory.candidates}
    chosen = {}
    for item in approved:
        row = current.get((item.kind.value, item.record_id))
        if (row is None or row.fingerprint != item.fingerprint
                or utc(row.changed_at) != utc(item.changed_at)):
            raise RetentionPolicyError("retention_preview_changed")
        name, identity = item.record_id.split(":", 1)
        if name not in MODELS:
            raise RetentionPolicyError("retention_application_entity_unknown")
        chosen.setdefault(name, set()).add(identity)
    await _dependencies(db, owner_id, chosen)
    references = await application_purge_references(db, owner_id, approved)
    sessions = set(chosen.get("chat_sessions", ()))
    for model in (m.Message, m.ChatTask):
        sessions.update(await db.scalars(select(model.session_id).where(
            model.user_id == owner_id, model.id.in_(chosen.get(model.__tablename__, ())),
        )))
    count = 0
    for model in DELETE_ORDER:
        ids = chosen.get(model.__tablename__)
        if not ids:
            continue
        result = await db.execute(delete(model).where(
            model.user_id == owner_id, model.id.in_(ids),
        ).execution_options(synchronize_session=False))
        if result.rowcount != len(ids):
            raise RetentionPolicyError("retention_preview_changed")
        count += result.rowcount
    return {"deleted": count, "external": references, "chat_contexts": tuple(sorted(sessions))}
