"""Dependency-closed bounded approvals; never rely on FK cascades as consent."""

from datetime import timedelta

from sqlalchemy import select

from app.db import models as m
from app.services.retention_inventory import POLICIES
from app.services.retention_policy import (
    CONTENT_RETENTION_DAYS,
    MAX_APPROVAL_ITEMS,
    RetentionPolicyError,
    utc,
)

KINDS = {model.__tablename__: kind.value for model, kind, _clock in POLICIES}


def _key(model, identity):
    return KINDS[model.__tablename__], f"{model.__tablename__}:{identity}"


async def application_dependencies(db, owner_id):
    """IDs only, both sides owner-checked; does not modify content or consent."""
    dependencies = {}
    relations = (
        (m.ChatSession, m.Message, m.Message.session_id),
        (m.ChatSession, m.ChatTask, m.ChatTask.session_id),
        (m.Message, m.ResponseFeedback, m.ResponseFeedback.message_id),
        (m.Message, m.CreationProposalRecord, m.CreationProposalRecord.message_id),
        (m.LocalSource, m.PdfIngestionJob, m.PdfIngestionJob.source_id),
    )
    for parent, child, field in relations:
        rows = await db.stream(select(parent.id, child.id, child.user_id).join(
            child, field == parent.id,
        ).where(parent.user_id == owner_id).execution_options(yield_per=128))
        async for parent_id, child_id, child_owner in rows:
            if child_owner != owner_id:
                raise RetentionPolicyError("retention_foreign_dependency")
            dependencies.setdefault(_key(parent, parent_id), set()).add(_key(child, child_id))
    indexes = (await db.execute(select(m.DriveFileIndex.id, m.DriveFileIndex.drive_file_id).where(
        m.DriveFileIndex.user_id == owner_id,
    ))).all()
    files = {}
    for identity, file_id in indexes:
        files.setdefault(file_id, set()).add(_key(m.DriveFileIndex, identity))
    locals_ = await db.scalars(select(m.LocalSource.id).where(m.LocalSource.user_id == owner_id))
    for identity in locals_:
        files.setdefault(f"local:{identity}", set()).add(_key(m.LocalSource, identity))
    for model in (m.DocumentChunk, m.DriveFileIndex):
        rows = await db.stream(select(model.id, model.drive_file_id).where(
            model.user_id == owner_id, model.drive_file_id.in_(files),
        ).execution_options(yield_per=128))
        async for identity, file_id in rows:
            child = _key(model, identity)
            for parent in files[file_id]:
                if parent != child:
                    # Two index rows for the same logical file are one closure;
                    # avoid making them depend on each other. Local sources do
                    # depend on each matching index/chunk row.
                    if model is m.DriveFileIndex and parent[1].startswith("drive_file_index:"):
                        continue
                    dependencies.setdefault(parent, set()).add(child)
    return {key: frozenset(values) for key, values in dependencies.items()}


def select_batch(candidates, dependencies, *, now, limit=MAX_APPROVAL_ITEMS):
    """Oversized parents wait while their old children are processed in batches.

    A fresh/unselected descendant protects the parent. No implicit cascade,
    newly eligible scope expansion, age change or in-place mutation occurs.
    """
    if type(limit) is not int or not 1 <= limit <= MAX_APPROVAL_ITEMS:
        raise RetentionPolicyError("invalid_retention_batch_size")
    current = {item.key: item for item in candidates}
    if len(current) != len(candidates):
        raise RetentionPolicyError("duplicate_retention_candidate")
    cutoff = utc(now) - timedelta(days=CONTENT_RETENTION_DAYS)
    eligible = {key: item for key, item in current.items()
                if not item.active and utc(item.changed_at) <= cutoff}
    chosen = {}

    def closure(key, visiting, found):
        if key in visiting:
            raise RetentionPolicyError("retention_dependency_cycle")
        if key not in current:
            raise RetentionPolicyError("retention_dependency_not_in_inventory")
        if key not in eligible:
            return False
        if key in found or key in chosen:
            return True
        visiting.add(key)
        for child in sorted(dependencies.get(key, ())):
            if not closure(child, visiting, found):
                return False
        visiting.remove(key)
        found[key] = eligible[key]
        return True

    for item in sorted(eligible.values(), key=lambda row: (utc(row.changed_at), row.key)):
        found = {}
        if closure(item.key, set(), found) and len(chosen) + len(found) <= limit:
            chosen.update(found)
        if len(chosen) == limit:
            break
    return tuple(chosen.values())
