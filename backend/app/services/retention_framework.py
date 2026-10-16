"""ADK inventory/old-row purge from a configured DB and explicit namespace.

The caller must not open/create a missing SQLite DB to prove an empty store.
LangGraph/checkpoint files are separate and are not covered by this adapter.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite

from sqlalchemy import JSON, MetaData, Table, delete, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retention_policy import (
    CONTENT_RETENTION_DAYS,
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


def _candidate(owner_id, table, row, scope):
    identity = [_value(row[column.key]) for column in table.primary_key.columns]
    identity_hash = hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":"), default=str,
    ).encode()).hexdigest()
    record_id = f"adk:{scope}:{table.name}:{identity_hash}"
    stamp = _stamp(row["timestamp" if table.name == "events" else "update_time"])
    return RetentionCandidate(
        owner_id=owner_id, kind=RetentionKind.FRAMEWORK, record_id=record_id,
        changed_at=stamp, fingerprint=content_fingerprint(
            owner_id=owner_id, kind=RetentionKind.FRAMEWORK, record_id=record_id,
            changed_at=stamp, values={key: _value(value) for key, value in row.items()},
        ),
    )


async def adk_inventory(db: AsyncSession, owner_id: str,
                        *, namespace: str | None, lock=False) -> AdkInventory:
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
        query = select(table).where(
            table.c.user_id == owner_id,
        )
        if lock and db.bind.dialect.name == "postgresql":
            query = query.with_for_update()
        rows = await db.stream(query.execution_options(yield_per=64))
        async for row in rows.mappings():
            if row["app_name"] not in SUPPORTED_APPS:
                raise RetentionPolicyError("retention_unsupported_framework_app")
            if name == "user_states" and _empty_shared_state(row["state"]):
                continue  # An empty SDK placeholder is not aged work content.
            candidates.append(_candidate(owner_id, table, row, scope))
    return AdkInventory(scope, tuple(candidates))


async def purge_adk(db, owner_id, approved, *, namespace, now):
    """Exact old rows only; no commit, SDK replay, shared-state deletion or consent.

    Cache resets for newly dated derived context are a distinct coordinator duty;
    deleting these aged rows is NOT proof that all conversation memory is gone.
    """
    if type(now) not in {int, float} or not isfinite(now) or now < 0:
        raise RetentionPolicyError("invalid_retention_time")
    approved = tuple(approved)
    cutoff = datetime.fromtimestamp(now, UTC) - timedelta(days=CONTENT_RETENTION_DAYS)
    keys = {(item.kind.value, item.record_id) for item in approved}
    if len(keys) != len(approved) or any(utc(item.changed_at) > cutoff for item in approved):
        raise RetentionPolicyError("retention_preview_changed")
    tables = await db.run_sync(_tables, namespace)
    if db.bind.dialect.name == "sqlite":
        table = tables["user_states"]
        await db.execute(update(table).where(table.c.user_id == owner_id).values(
            state=table.c.state,
        ))
    inventory = await adk_inventory(db, owner_id, namespace=namespace, lock=True)
    current = {item.key: item for item in inventory.candidates}
    for item in approved:
        row = current.get((item.kind.value, item.record_id))
        if (row is None or row.fingerprint != item.fingerprint
                or utc(row.changed_at) != utc(item.changed_at)):
            raise RetentionPolicyError("retention_preview_changed")
    scope = namespace or "local"
    selected = {name: [] for name in ("events", "sessions", "user_states")}
    # Reconstruct identities from the still-locked live rows, not an opaque ID
    # supplied by a browser. No private framework state leaves this method.
    events = []
    for name in selected:
        table = tables[name]
        rows = await db.stream(select(table).where(table.c.user_id == owner_id))
        async for row in rows.mappings():
            key = _candidate(owner_id, table, row, scope).key
            if name == "events":
                events.append((row["app_name"], row["session_id"], key))
            if key in keys:
                selected[name].append({column.key: row[column.key]
                                       for column in table.primary_key.columns})
    parents = {(row["app_name"], row["id"]) for row in selected["sessions"]}
    if any((app, session) in parents and key not in keys for app, session, key in events):
        raise RetentionPolicyError("retention_dependency_not_selected")
    count = 0
    for name in ("events", "sessions", "user_states"):
        table = tables[name]
        for identity in selected[name]:
            predicates = (
                table.c.user_id == owner_id,
                *(table.c[field] == value for field, value in identity.items()),
            )
            if name == "user_states" and await db.scalar(select(tables["sessions"].c.id).where(
                tables["sessions"].c.user_id == owner_id,
                tables["sessions"].c.app_name == identity["app_name"],
            ).limit(1)) is not None:
                # The SDK requires a user-state row even for remaining fresh
                # sessions. Erase the approved old contents, not that invariant.
                empty = {} if isinstance(table.c.state.type, JSON) else "{}"
                result = await db.execute(update(table).where(*predicates).values(
                    state=empty, update_time=datetime.fromtimestamp(now, UTC).replace(tzinfo=None),
                ))
            else:
                result = await db.execute(delete(table).where(*predicates))
            if result.rowcount != 1:
                raise RetentionPolicyError("retention_preview_changed")
            count += 1
    if count != len(approved):
        raise RetentionPolicyError("retention_preview_changed")
    return count
