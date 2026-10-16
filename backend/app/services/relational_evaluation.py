"""Owner-scoped queue with leased, fenced checkpoints on PostgreSQL/SQLite."""

import hashlib
import json
from time import time
from uuid import uuid4

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    func,
    insert,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.services.durable_evaluation import EvaluationQueue, LeaseLostError
from app.services.relational_state import state_engine, state_transaction
from app.services.state_content_clocks import (
    metadata as clock_metadata,
)
from app.services.state_content_clocks import (
    record_relational,
    seed_relational,
)

metadata = MetaData()
jobs = Table(
    "evaluation_jobs", metadata,
    Column("id", String(36), primary_key=True),
    Column("owner", Text, nullable=False, index=True),
    Column("status", Text, nullable=False),
    Column("checkpoint", Text, nullable=False, default="{}"),
    Column("attempts", Integer, nullable=False, default=0),
    Column("lease_until", Float),
    Column("created_at", Float, nullable=False),
)


def evaluation_queue(settings: Settings) -> EvaluationQueue:
    if settings.relational_state_url is None:
        return EvaluationQueue(settings.data_dir)
    return RelationalEvaluationQueue(state_engine(settings.relational_state_url.get_secret_value()))


def initialize_evaluation_queue(settings: Settings) -> None:
    if settings.relational_state_url is not None:
        RelationalEvaluationQueue.create_schema(
            state_engine(settings.relational_state_url.get_secret_value())
        )
    else:
        EvaluationQueue(settings.data_dir).reconcile_content_clocks()


class RelationalEvaluationQueue(EvaluationQueue):
    def __init__(self, engine: Engine):
        if engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ValueError("Evaluation queue requires SQLite or PostgreSQL")
        self.engine = engine

    @staticmethod
    def create_schema(engine: Engine):
        metadata.create_all(engine)
        clock_metadata.create_all(engine)
        with state_transaction(engine) as db:
            seed_relational(db, "evaluation_jobs", jobs, time(), owner_column="owner")

    @staticmethod
    def _record_content(db, job_id, now):
        row = db.execute(select(jobs).where(jobs.c.id == job_id)).mappings().one()
        record_relational(db, "evaluation_jobs", row, now, owner_column="owner")

    def enqueue(self, owner: str, now: float) -> str:
        job_id = str(uuid4())
        with state_transaction(self.engine) as db:
            if self.engine.dialect.name == "postgresql":
                # Serialize count+insert for this owner, including the empty-queue case.
                scope = int.from_bytes(hashlib.sha256(owner.encode()).digest()[:8],
                                       "big", signed=True)
                db.execute(text("SELECT pg_advisory_xact_lock(:scope)"), {"scope": scope})
            count = db.execute(select(func.count()).select_from(jobs).where(
                jobs.c.owner == owner, jobs.c.status.in_(["queued", "running"]),
            )).scalar_one()
            if count >= 2:
                raise ValueError("At most two pending evaluation jobs per user")
            db.execute(insert(jobs).values(id=job_id, owner=owner, status="queued", created_at=now))
            self._record_content(db, job_id, now)
        return job_id

    def get(self, owner: str, job_id: str):
        with self.engine.connect() as db:
            row = db.execute(select(jobs).where(
                jobs.c.id == job_id, jobs.c.owner == owner,
            )).mappings().first()
        if row is None:
            return None
        result = dict(row)
        result.pop("owner")
        result["checkpoint"] = json.loads(result["checkpoint"])
        return result

    def recent(self, owner: str):
        with self.engine.connect() as db:
            identifiers = db.execute(select(jobs.c.id).where(
                jobs.c.owner == owner,
            ).order_by(jobs.c.created_at.desc()).limit(10)).scalars().all()
        return [self.get(owner, job_id) for job_id in identifiers]

    def claim(self, now: float, *, blocked_owners=()):
        with state_transaction(self.engine) as db:
            db.execute(update(jobs).where(
                jobs.c.status == "running", jobs.c.lease_until < now, jobs.c.attempts >= 3,
                jobs.c.owner.not_in(tuple(blocked_owners)),
            ).values(status="failed", lease_until=None))
            eligible = jobs.c.owner.not_in(tuple(blocked_owners)) & or_(
                jobs.c.status == "queued", and_(
                jobs.c.status == "running", jobs.c.lease_until < now, jobs.c.attempts < 3,
            ))
            query = select(jobs).where(eligible).order_by(jobs.c.created_at).limit(1)
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            row = db.execute(query).mappings().first()
            if row is None:
                return None
            changed = db.execute(update(jobs).where(
                jobs.c.id == row["id"], jobs.c.attempts == row["attempts"], eligible,
            ).values(status="running", attempts=row["attempts"] + 1,
                     lease_until=now + 120)).rowcount
            if changed != 1:
                return None
            result = dict(row)
            result.update(status="running", attempts=row["attempts"] + 1, lease_until=now + 120)
            return result

    def checkpoint(self, job_id: str, result: dict, now: float, *, attempt: int):
        self._fenced(job_id, attempt, now,
                     checkpoint=json.dumps(result), lease_until=now + 120)

    def finish(self, job_id: str, status: str, *, attempt: int, now: float):
        if status not in {"completed", "quality_failed", "failed"}:
            raise ValueError("Invalid terminal evaluation state")
        self._fenced(job_id, attempt, now, status=status, lease_until=None)

    def _fenced(self, job_id: str, attempt: int, now: float, **values):
        with self.engine.begin() as db:
            changed = db.execute(update(jobs).where(
                jobs.c.id == job_id, jobs.c.status == "running",
                jobs.c.attempts == attempt, jobs.c.lease_until > now,
            ).values(**values)).rowcount
            if changed != 1:
                raise LeaseLostError("Evaluation worker no longer owns the lease")
            self._record_content(db, job_id, now)
