"""Exact, owner-scoped reset of derived context, with no commit or consent.

The coordinator must hold its exclusive owner fence through validation and
commit, and explicitly approve the returned digest: these are *all* temporary
context rows, including fresh ones, not just content older than 30 days. Recent
canonical messages, sources and saved memory are deliberately not touched.

Pass an AsyncSession for the already configured store. No engine, database file,
SDK state or tables are created here. On any error the caller must roll back its
transaction. PostgreSQL row locks do not replace the caller's admission fence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from uuid import UUID

from sqlalchemy import MetaData, Table, delete, func, inspect, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import GraphCheckpoint
from app.services.retention_framework import SUPPORTED_APPS, _empty_shared_state, _tables
from app.services.retention_policy import RetentionPolicyError

_UUID_GREGORIAN_OFFSET_100NS = 0x01B21DD213814000


@dataclass(frozen=True)
class ContextInventory:
    """Approval metadata only; neither raw content nor thread/session IDs leave."""

    scope: str
    digest: str
    row_count: int
    table_counts: tuple[tuple[str, int], ...]


def _safe_store(action):
    @wraps(action)
    async def call(*args, **kwargs):
        try:
            return await action(*args, **kwargs)
        except SQLAlchemyError:
            # Driver messages can contain SQL parameters or document content.
            raise RetentionPolicyError("retention_context_store_unavailable") from None
    return call


def _owner(owner_id: str) -> None:
    if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 200:
        raise RetentionPolicyError("invalid_retention_owner")


def _existing_store(db) -> None:
    """Reject a missing local file before SQLAlchemy could silently create it."""
    engine = db.bind
    if engine is None:
        raise RetentionPolicyError("retention_context_store_unavailable")
    if engine.dialect.name != "sqlite":
        return
    location = engine.url.database
    if location == ":memory:":
        return  # No filesystem is created; the reflected schema must still exist.
    try:
        valid = (isinstance(location, str) and bool(location)
                 and not location.startswith("file:") and Path(location).is_file())
    except OSError:
        valid = False
    if not valid:
        raise RetentionPolicyError("retention_context_store_unavailable")


def _value(value):
    # Type tags prevent an opaque-byte digest from colliding with a literal JSON
    # object of the same shape. Never invoke a pickle/framework deserializer.
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, float) and math.isfinite(value):
        return ["float", value.hex()]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, datetime):
        return ["datetime", value.isoformat()]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return ["bytes", len(value), hashlib.sha256(bytes(value)).hexdigest()]
    if isinstance(value, (list, tuple)):
        return ["list", [_value(item) for item in value]]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return ["dict", [[key, _value(value[key])] for key in sorted(value)]]
    raise RetentionPolicyError("retention_context_value_unsupported")


def _encoded(value) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise RetentionPolicyError("retention_context_value_unsupported") from None


async def _inventory(db, owner_id, scope, tables, predicate, *, lock=False,
                     validate_row=None):
    _owner(owner_id)
    digest = hashlib.sha256(_encoded(["veridra-context-v1", scope, owner_id]))
    counts = []
    for table in tables:
        count = 0
        query = select(table).where(predicate(table)).order_by(*table.primary_key.columns)
        if lock and db.bind.dialect.name == "postgresql":
            query = query.with_for_update()
        rows = await db.stream(query.execution_options(yield_per=64))
        async for row in rows.mappings():
            if validate_row:
                validate_row(row)
            encoded = _encoded([table.name, [[key, _value(row[key])]
                                            for key in sorted(row.keys())]])
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
            count += 1
        # Bind even empty table identities into the digest.
        digest.update(_encoded(["table-end", table.name, count]))
        counts.append((table.name, count))
    return ContextInventory(scope, digest.hexdigest(), sum(count for _, count in counts),
                            tuple(counts))


def _expected(expected_digest, actual: ContextInventory) -> None:
    if (not isinstance(expected_digest, str) or len(expected_digest) != 64
            or any(char not in "0123456789abcdef" for char in expected_digest)):
        raise RetentionPolicyError("invalid_retention_context_digest")
    if not hmac.compare_digest(expected_digest, actual.digest):
        raise RetentionPolicyError("retention_preview_changed")


async def _shared_empty(db, tables, *, lock=False):
    table = tables["app_states"]
    query = select(table.c.state).where(table.c.app_name.in_(SUPPORTED_APPS))
    if lock and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    states = await db.scalars(query)
    if any(not _empty_shared_state(state) for state in states):
        raise RetentionPolicyError("retention_unattributed_framework_state")


def _adk_row(row):
    if row["app_name"] not in SUPPORTED_APPS:
        raise RetentionPolicyError("retention_unsupported_framework_app")


@_safe_store
async def adk_context_inventory(db, owner_id: str, *, namespace: str | None,
                                lock=False) -> ContextInventory:
    """Digest every owned ADK row, including empty SDK user-state placeholders."""
    _owner(owner_id)
    _existing_store(db)
    tables = await db.run_sync(_tables, namespace)
    await _shared_empty(db, tables, lock=lock)
    return await _inventory(
        db, owner_id, f"adk:{namespace or 'local'}",
        [tables[name] for name in ("events", "sessions", "user_states")],
        lambda table: table.c.user_id == owner_id, lock=lock, validate_row=_adk_row,
    )


@_safe_store
async def reset_adk_context(db, owner_id: str, expected_digest: str, *,
                            namespace: str | None) -> int:
    """Reset exactly the approved owned context; shared app/metadata rows stay."""
    _owner(owner_id)
    _existing_store(db)
    tables = await db.run_sync(_tables, namespace)
    if db.bind.dialect.name == "sqlite":
        table = tables["user_states"]
        await db.execute(update(table).where(table.c.user_id == owner_id).values(
            state=table.c.state,
        ))
    actual = await adk_context_inventory(db, owner_id, namespace=namespace, lock=True)
    _expected(expected_digest, actual)
    count = 0
    for name in ("events", "sessions", "user_states"):
        result = await db.execute(delete(tables[name]).where(
            tables[name].c.user_id == owner_id,
            tables[name].c.app_name.in_(SUPPORTED_APPS),
        ))
        count += result.rowcount
    if count != actual.row_count:
        raise RetentionPolicyError("retention_preview_changed")
    await _shared_empty(db, tables, lock=True)
    return count


@_safe_store
async def graph_context_inventory(db, owner_id: str, *, lock=False) -> ContextInventory:
    """Application UI snapshots only, not the independent LangGraph store."""
    _owner(owner_id)
    _existing_store(db)
    table = await db.run_sync(_graph_table)
    return await _inventory(db, owner_id, "application:graph_checkpoints", [table],
                            lambda table: table.c.user_id == owner_id, lock=lock)


def _graph_table(session):
    connection = session.connection()
    # Inspector reflection does not apply the engine's schema_translate_map to
    # its has_table probes. Name this namespace explicitly: a same-named public
    # table must never stand in for the private application's context store.
    schema = "veridra_private" if connection.dialect.name == "postgresql" else None
    inspector = inspect(connection)
    if not inspector.has_table(GraphCheckpoint.__tablename__, schema=schema):
        raise RetentionPolicyError("retention_context_graph_schema_incomplete")
    table = Table(GraphCheckpoint.__tablename__, MetaData(), schema=schema,
                  autoload_with=connection, resolve_fks=False)
    if (set(table.c.keys()) != set(GraphCheckpoint.__table__.c.keys())
            or tuple(column.key for column in table.primary_key.columns) != ("id",)):
        raise RetentionPolicyError("retention_context_graph_schema_incomplete")
    return table


@_safe_store
async def reset_graph_context(db, owner_id: str, expected_digest: str) -> int:
    _owner(owner_id)
    _existing_store(db)
    table = await db.run_sync(_graph_table)
    if db.bind.dialect.name == "sqlite":
        await db.execute(update(table).where(table.c.user_id == owner_id).values(
            state_json=table.c.state_json,
        ))
    actual = await graph_context_inventory(db, owner_id, lock=True)
    _expected(expected_digest, actual)
    result = await db.execute(delete(table).where(table.c.user_id == owner_id))
    if result.rowcount != actual.row_count:
        raise RetentionPolicyError("retention_preview_changed")
    return result.rowcount


_LANGGRAPH_FIELDS = {
    "checkpoints": {"thread_id", "checkpoint_ns", "checkpoint_id", "parent_checkpoint_id",
                    "type", "checkpoint", "metadata"},
    "writes": {"thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx",
               "channel", "type", "value"},
}
_LANGGRAPH_PK = {
    "checkpoints": ("thread_id", "checkpoint_ns", "checkpoint_id"),
    "writes": ("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"),
}


def _langgraph_tables(session):
    connection = session.connection()
    if connection.dialect.name != "sqlite":
        raise RetentionPolicyError("retention_context_langgraph_dialect_unsupported")
    inspector = inspect(connection)
    # This adapter targets the actual pinned AsyncSqliteSaver schema, not other
    # saver versions that could carry content in additional uninspected tables.
    if set(inspector.get_table_names()) != set(_LANGGRAPH_FIELDS):
        raise RetentionPolicyError("retention_context_langgraph_schema_incomplete")
    metadata = MetaData()
    result = {}
    for name, fields in _LANGGRAPH_FIELDS.items():
        table = Table(name, metadata, autoload_with=connection)
        primary_key = tuple(column.key for column in table.primary_key.columns)
        if set(table.c.keys()) != fields or primary_key != _LANGGRAPH_PK[name]:
            raise RetentionPolicyError("retention_context_langgraph_schema_incomplete")
        result[name] = table
    return result


def _thread_predicate(owner_id):
    if ":" in owner_id:
        raise RetentionPolicyError("invalid_retention_context_owner")
    prefix = f"{owner_id}:"
    # Equality over substrings is literal: owner IDs containing SQL LIKE's '%' or
    # '_' never expand to other owners. The row validator rejects malformed IDs.
    return lambda table: func.substr(table.c.thread_id, 1, len(prefix)) == prefix


def _thread_row(owner_id):
    def validate(row):
        value = row["thread_id"]
        if (not isinstance(value, str) or value.partition(":")[0] != owner_id
                or not value.partition(":")[2]):
            raise RetentionPolicyError("retention_context_thread_invalid")
    return validate


def _checkpoint_timestamp(checkpoint_id: str) -> datetime:
    """Decode LangGraph's UUIDv6 time without opening its opaque payloads.

    The pinned checkpoint implementation creates IDs with uuid6(). Python's
    UUID.time property interprets the older UUIDv1 field order, so UUIDv6 needs
    its own field reconstruction. Unknown/legacy IDs fail closed instead of
    falling back to a shared SQLite file's modification time.
    """
    try:
        value = UUID(checkpoint_id)
    except (TypeError, ValueError, AttributeError):
        raise RetentionPolicyError("retention_context_checkpoint_age_unknown") from None
    if value.version != 6:
        raise RetentionPolicyError("retention_context_checkpoint_age_unknown")
    gregorian_ticks = (value.time_low << 28) | (value.time_mid << 12) | (
        value.time_hi_version & 0x0FFF
    )
    unix_ticks = gregorian_ticks - _UUID_GREGORIAN_OFFSET_100NS
    if unix_ticks < 0:
        raise RetentionPolicyError("retention_context_checkpoint_age_unknown")
    try:
        # Flooring sub-microsecond ticks is conservative at the exact cutoff.
        return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=unix_ticks // 10)
    except (OverflowError, ValueError):
        raise RetentionPolicyError("retention_context_checkpoint_age_unknown") from None


@_safe_store
async def langgraph_context_inventory(db, owner_id: str, *, lock=False) -> ContextInventory:
    """Opaque rows in the explicit existing pinned native SQLite checkpoint DB."""
    _owner(owner_id)
    _existing_store(db)
    predicate = _thread_predicate(owner_id)
    tables = await db.run_sync(_langgraph_tables)
    return await _inventory(db, owner_id, "langgraph:sqlite",
                            [tables["writes"], tables["checkpoints"]], predicate,
                            lock=lock, validate_row=_thread_row(owner_id))


@_safe_store
async def langgraph_context_oldest_at(db, owner_id: str, *, lock=False) -> datetime | None:
    """Return the oldest owned checkpoint/write timestamp, never the shared DB mtime.

    The retention unit is the owner-scoped derived context store: once its
    oldest entry reaches the 30-day review point, the UI explicitly warns that
    approving cleanup resets all of that owner's derived context. Canonical
    chat history and other users' checkpoints are not part of this reset.
    """
    _owner(owner_id)
    _existing_store(db)
    predicate = _thread_predicate(owner_id)
    tables = await db.run_sync(_langgraph_tables)
    stamps = []
    for name in ("writes", "checkpoints"):
        table = tables[name]
        query = select(table.c.thread_id, table.c.checkpoint_id).where(predicate(table))
        if lock and db.bind.dialect.name == "postgresql":
            query = query.with_for_update()
        rows = await db.stream(query.execution_options(yield_per=128))
        async for thread_id, checkpoint_id in rows:
            _thread_row(owner_id)({"thread_id": thread_id})
            stamps.append(_checkpoint_timestamp(checkpoint_id))
    return min(stamps) if stamps else None


@_safe_store
async def reset_langgraph_context(db, owner_id: str, expected_digest: str) -> int:
    """Delete only exact owned thread rows, without SDK commit or deserialization."""
    _owner(owner_id)
    _existing_store(db)
    predicate = _thread_predicate(owner_id)
    tables = await db.run_sync(_langgraph_tables)
    table = tables["checkpoints"]
    await db.execute(update(table).where(predicate(table)).values(type=table.c.type))
    actual = await langgraph_context_inventory(db, owner_id, lock=True)
    _expected(expected_digest, actual)
    count = 0
    for name in ("writes", "checkpoints"):
        table = tables[name]
        result = await db.execute(delete(table).where(predicate(table)))
        count += result.rowcount
    if count != actual.row_count:
        raise RetentionPolicyError("retention_preview_changed")
    return count
