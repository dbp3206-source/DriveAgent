"""Read-only owner inventory of application rows, not a cross-store purge.

No contents are returned. Framework/objects/vector/state/backups require their
own adapters and checks; this inventory cannot authorize deletion by itself.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m
from app.services.retention_policy import (
    REQUIRED_INVENTORIES,
    RetentionCandidate,
    RetentionKind,
    RetentionPolicyError,
    content_fingerprint,
    utc,
)

# Every ORM table is deliberately classified; new tables must not disappear
# silently from retention. Identity/keys are not aged work content.
IDENTITY_TABLES = frozenset({"users", "provider_credentials"})
POLICIES = (
    (m.ChatSession, RetentionKind.CHAT, "updated_at"),
    (m.Message, RetentionKind.CHAT, "created_at"),
    (m.ChatTask, RetentionKind.CHAT, "created_at"),
    (m.ResponseFeedback, RetentionKind.CHAT, "updated_at"),
    (m.CreationProposalRecord, RetentionKind.OPERATION, "created_at"),
    (m.LocalSource, RetentionKind.SOURCE, "created_at"),
    (m.PdfIngestionJob, RetentionKind.SOURCE, "updated_at"),
    (m.DriveFileIndex, RetentionKind.INDEX, "indexed_at"),
    (m.DocumentChunk, RetentionKind.INDEX, "created_at"),
    (m.LongTermMemory, RetentionKind.MEMORY, "content_updated_at"),
    (m.SavedArtifact, RetentionKind.ARTIFACT, "content_updated_at"),
    (m.CompanyProfile, RetentionKind.COMPANY, "content_updated_at"),
    (m.ScheduledJob, RetentionKind.JOB, "updated_at"),
    (m.AuditEvent, RetentionKind.AUDIT, "created_at"),
    (m.GraphCheckpoint, RetentionKind.FRAMEWORK, "created_at"),
)
TERMINAL_MESSAGES = frozenset({"completed", "failed", "cancelled", "error"})
TERMINAL_JOBS = frozenset({"completed", "failed"})


@dataclass(frozen=True)
class ApplicationInventory:
    candidates: tuple[RetentionCandidate, ...]
    owner_busy: bool

    def policy_checks(self) -> dict[str, bool]:
        """Other adapters must positively establish their own coverage."""
        return {name: name == "application" and not self.owner_busy
                for name in REQUIRED_INVENTORIES}


def validate_application_catalog() -> None:
    covered = {model.__tablename__ for model, _kind, _clock in POLICIES}
    if covered & IDENTITY_TABLES or covered | IDENTITY_TABLES != set(m.Base.metadata.tables):
        raise RetentionPolicyError("retention_application_catalog_incomplete")


async def application_inventory(db: AsyncSession, owner_id: str) -> ApplicationInventory:
    """Caller supplies the authenticated owner; no commits, deletes or remote calls.

    A later runner must re-read this under its write fence. Streaming bounds
    raw content buffered at once; no API's list/page limit truncates inventory.
    """
    if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 200:
        raise RetentionPolicyError("invalid_retention_owner")
    validate_application_catalog()
    child_rows = (await db.execute(select(
        m.Message.session_id, func.max(m.Message.created_at),
        func.sum(case((m.Message.status.not_in(TERMINAL_MESSAGES), 1), else_=0)),
        func.count(m.Message.id),
    ).where(m.Message.user_id == owner_id).group_by(m.Message.session_id))).all()
    children = {row[0]: (row[1], bool(row[2]), row[3]) for row in child_rows}
    # Re-extraction may replace an existing LocalSource without changing its
    # created_at. The worker publishes content and job.updated_at in one SQL
    # transaction; the linked job therefore protects newly published text.
    publication_rows = (await db.execute(select(
        m.PdfIngestionJob.source_id, func.max(m.PdfIngestionJob.updated_at),
    ).where(
        m.PdfIngestionJob.user_id == owner_id, m.PdfIngestionJob.source_id.is_not(None),
    ).group_by(m.PdfIngestionJob.source_id))).all()
    publications = {row[0]: row[1] for row in publication_rows}
    candidates = []
    busy = False
    for model, kind, clock in POLICIES:
        rows = await db.stream_scalars(select(model).where(
            model.user_id == owner_id,
        ).execution_options(yield_per=64, populate_existing=True))
        async for row in rows:
            values = {column.key: getattr(row, column.key) for column in model.__table__.columns}
            stamp = getattr(row, clock)
            if stamp is None and clock == "content_updated_at":
                # A rolled-back older release may have created a null clock.
                stamp = row.updated_at or row.created_at
            if not isinstance(stamp, datetime):
                raise RetentionPolicyError("retention_content_age_unknown")
            stamp = utc(stamp)
            active = False
            if model is m.ChatSession:
                newest, active, count = children.get(row.id, (None, False, 0))
                if newest is not None:
                    stamp = max(stamp, utc(newest))
                values["child_summary"] = {"newest": newest, "active": active, "count": count}
            elif model is m.LocalSource:
                published_at = publications.get(row.id)
                if published_at is not None:
                    stamp = max(stamp, utc(published_at))
                    values["last_publication"] = published_at
            elif model is m.Message:
                active = row.status not in TERMINAL_MESSAGES
            elif model in {m.ChatTask, m.ScheduledJob, m.PdfIngestionJob}:
                terminal = (TERMINAL_JOBS | {"needs_attention"} if model is m.PdfIngestionJob
                            else TERMINAL_JOBS)
                active = row.status not in terminal
            elif model is m.AuditEvent and row.completed_at is not None:
                stamp = max(stamp, utc(row.completed_at))
            busy = busy or active
            record_id = f"{model.__tablename__}:{row.id}"
            candidates.append(RetentionCandidate(
                owner_id=owner_id, kind=kind, record_id=record_id, changed_at=stamp,
                fingerprint=content_fingerprint(
                    owner_id=owner_id, kind=kind, record_id=record_id,
                    changed_at=stamp, values=values,
                ), active=active,
            ))
    return ApplicationInventory(tuple(candidates), busy)
