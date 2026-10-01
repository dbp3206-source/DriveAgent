"""Credential/capability-isolated provider cooldowns on durable relational state."""

import hashlib
import sqlite3
import time

from sqlalchemy import Column, Float, Integer, MetaData, Table, Text, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.services.inference_gateway import ProviderCircuitStore, provider_error_class
from app.services.quota import quota_namespace
from app.services.relational_state import state_engine, state_transaction
from app.tools.contracts import ToolError

metadata = MetaData()
circuits = Table(
    "provider_circuits", metadata,
    Column("namespace", Text, primary_key=True),
    Column("capability", Text, primary_key=True),
    Column("consecutive_failures", Integer, nullable=False),
    Column("opened_until", Float),
    Column("last_error_class", Text),
    Column("updated_at", Float, nullable=False),
)


def circuit_store(settings: Settings, credential: str) -> ProviderCircuitStore:
    if settings.relational_state_url is None:
        return ProviderCircuitStore(settings.data_dir / "provider_state.db", credential)
    return RelationalCircuitStore(
        state_engine(settings.relational_state_url.get_secret_value()), credential
    )


def initialize_circuit_store(settings: Settings):
    if settings.relational_state_url is not None:
        metadata.create_all(state_engine(settings.relational_state_url.get_secret_value()))


def open_circuit_count(settings: Settings, *, now: float | None = None) -> int:
    """Return aggregate health without exposing credential namespaces."""

    stamp = time.time() if now is None else now
    if settings.relational_state_url is not None:
        engine = state_engine(settings.relational_state_url.get_secret_value())
        with engine.connect() as db:
            return int(db.execute(select(func.count()).select_from(circuits).where(
                circuits.c.opened_until.is_not(None), circuits.c.opened_until > stamp,
            )).scalar_one())
    path = settings.data_dir / "provider_state.db"
    if not path.exists():
        return 0
    try:
        with sqlite3.connect(path, timeout=3) as db:
            return int(db.execute(
                "SELECT COUNT(*) FROM provider_circuits "
                "WHERE opened_until IS NOT NULL AND opened_until > ?",
                (stamp,),
            ).fetchone()[0])
    except sqlite3.Error:
        return 0


class RelationalCircuitStore(ProviderCircuitStore):
    def __init__(self, engine: Engine, credential: str):
        self.engine = engine
        self.namespace = quota_namespace(credential)

    def _upsert(self, db, capability: str, **values):
        builder = pg_insert if self.engine.dialect.name == "postgresql" else sqlite_insert
        query = builder(circuits).values(namespace=self.namespace, capability=capability, **values)
        db.execute(query.on_conflict_do_update(
            index_elements=[circuits.c.namespace, circuits.c.capability], set_=values,
        ))

    def before_request(self, capability: str, *, now: float | None = None):
        stamp = time.time() if now is None else now
        with self.engine.connect() as db:
            row = db.execute(select(circuits).where(
                circuits.c.namespace == self.namespace, circuits.c.capability == capability,
            )).mappings().first()
        if row and row["opened_until"] and row["opened_until"] > stamp:
            wait = max(1, int(row["opened_until"] - stamp + 0.999))
            raise ToolError(
                f"Gemini đang tạm nghỉ sau lỗi {row['last_error_class'] or 'provider'}; "
                f"thử lại sau {wait} giây. Các chức năng local vẫn dùng được.",
                code="gemini_circuit_open", retryable=True,
            )

    def success(self, capability: str, *, now: float | None = None):
        stamp = time.time() if now is None else now
        with self.engine.begin() as db:
            self._upsert(db, capability, consecutive_failures=0, opened_until=None,
                         last_error_class=None, updated_at=stamp)

    def failure(self, capability: str, exc: Exception, *, now: float | None = None) -> str:
        stamp = time.time() if now is None else now
        error_class, cooldown, transient = provider_error_class(exc)
        with state_transaction(self.engine) as db:
            if self.engine.dialect.name == "postgresql":
                scope = int.from_bytes(hashlib.sha256(
                    ("circuit:" + self.namespace + ":" + capability).encode()
                ).digest()[:8], "big", signed=True)
                db.execute(text("SELECT pg_advisory_xact_lock(:scope)"), {"scope": scope})
            old = db.execute(select(circuits.c.consecutive_failures).where(
                circuits.c.namespace == self.namespace, circuits.c.capability == capability,
            )).scalar_one_or_none()
            failures = (old or 0) + 1
            should_open = error_class == "quota" or (transient and failures >= 3)
            self._upsert(db, capability, consecutive_failures=failures,
                         opened_until=stamp + cooldown if should_open and cooldown else None,
                         last_error_class=error_class, updated_at=stamp)
        return error_class

    def snapshot(self, *, now: float | None = None) -> list[dict]:
        stamp = time.time() if now is None else now
        with self.engine.connect() as db:
            rows = db.execute(select(circuits).where(
                circuits.c.namespace == self.namespace,
            ).order_by(circuits.c.capability)).mappings().all()
        return [{
            "capability": row["capability"], "consecutive_failures": row["consecutive_failures"],
            "circuit_open": bool(row["opened_until"] and row["opened_until"] > stamp),
            "retry_after_seconds": max(0, int(row["opened_until"] - stamp))
            if row["opened_until"] else 0,
            "last_error_class": row["last_error_class"],
        } for row in rows]
