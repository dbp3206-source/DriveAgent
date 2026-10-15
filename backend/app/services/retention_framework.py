"""Read-only ADK inventory from a known configured DB and explicit namespace.

The caller must not open/create a missing SQLite DB to prove an empty store.
LangGraph/checkpoint files are separate and are not covered by this adapter.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retention_policy import (
    RetentionCandidate,
    RetentionKind,
    RetentionPolicyError,
    content_fingerprint,
    utc,
)

SUPPORTED_APPS = frozenset({"drive_agent", "drive_compiler"})
TABLE_FIELDS = {
    "sessions": {"app_name", "user_id", "id", "state", "update_time"},
    "events": {"app_name", "user_id", "session_id", "id", "timestamp", "event_data"},
    "user_states": {"app_name", "user_id", "state", "update_time"},
    "app_states": {"app_name", "state"},
}


@dataclass(frozen=True)
class AdkInventory:
    namespace: str
    candidates: tuple[RetentionCandidate, ...]


def _tables(session, namespace):
    connection = session.connection()
    dialect = connection.dialect.name
    if ((dialect == "postgresql" and namespace not in {"public", "veridra_private"})
            or (dialect == "sqlite" and namespace is not None)
            or dialect not in {"sqlite", "postgresql"}):
        raise RetentionPolicyError("invalid_framework_namespace")
    inspector = inspect(connection)
    if not inspector.has_table("adk_internal_metadata", schema=namespace):
        raise RetentionPolicyError("framework_inventory_marker_missing")
    metadata = MetaData()
    tables = {}
    for name, fields in TABLE_FIELDS.items():
        if not inspector.has_table(name, schema=namespace):
            raise RetentionPolicyError("framework_inventory_schema_incomplete")
        table = Table(name, metadata, schema=namespace, autoload_with=connection,
                      resolve_fks=False)
        if not fields.issubset(table.c.keys()) or not table.primary_key.columns:
            raise RetentionPolicyError("framework_inventory_schema_incomplete")
        tables[name] = table
    return tables


def _empty_shared_state(value) -> bool:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return False
    return value is None or value == {}


def _stamp(value) -> datetime:
    try:
        if isinstance(value, datetime):
            return utc(value)
        if isinstance(value, str):
            return utc(datetime.fromisoformat(value))
        if type(value) in {float, int}:
            return datetime.fromtimestamp(value, UTC)
    except (ValueError, OverflowError, OSError):
        pass
    raise RetentionPolicyError("framework_inventory_age_unknown")


def _value(value):
    # Never deserialize opaque framework payloads, particularly not pickle.
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"opaque_sha256": hashlib.sha256(bytes(value)).hexdigest()}
    return value


async def adk_inventory(db: AsyncSession, owner_id: str,
                        *, namespace: str | None) -> AdkInventory:
    if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 200:
        raise RetentionPolicyError("invalid_retention_owner")
    tables = await db.run_sync(_tables, namespace)
    shared = tables["app_states"]
    states = (await db.execute(select(shared.c.state).where(
        shared.c.app_name.in_(SUPPORTED_APPS),
    ))).scalars().all()
    if any(not _empty_shared_state(state) for state in states):
        # No owner predicate exists for shared state. Never erase other users'
        # data or report a complete per-user cleanup when attribution is absent.
        raise RetentionPolicyError("retention_unattributed_framework_state")
    candidates = []
    scope = namespace or "local"
    for name in ("sessions", "events", "user_states"):
        table = tables[name]
        rows = await db.stream(select(table).where(
            table.c.user_id == owner_id,
        ).execution_options(yield_per=64))
        async for row in rows.mappings():
            if row["app_name"] not in SUPPORTED_APPS:
                raise RetentionPolicyError("retention_unsupported_framework_app")
            identity = [_value(row[column.key]) for column in table.primary_key.columns]
            identity_hash = hashlib.sha256(json.dumps(
                identity, sort_keys=True, separators=(",", ":"), default=str,
            ).encode()).hexdigest()
            record_id = f"adk:{scope}:{name}:{identity_hash}"
            stamp = _stamp(row["timestamp" if name == "events" else "update_time"])
            candidates.append(RetentionCandidate(
                owner_id=owner_id, kind=RetentionKind.FRAMEWORK, record_id=record_id,
                changed_at=stamp, fingerprint=content_fingerprint(
                    owner_id=owner_id, kind=RetentionKind.FRAMEWORK, record_id=record_id,
                    changed_at=stamp, values={key: _value(value) for key, value in row.items()},
                ),
            ))
    return AdkInventory(scope, tuple(candidates))
