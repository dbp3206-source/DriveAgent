"""Inventory and transactional purge of skill/operation/evaluation payloads.

Only operates on an already configured, initialized store. Does not open missing
files, authenticate a user, establish consent, commit, or call a provider. The
coordinator must hold its owner admission fence and commit progress atomically.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite

from sqlalchemy import MetaData, Table, case, delete, inspect, select, update

from app.services.retention_policy import (
    CONTENT_RETENTION_DAYS,
    RetentionCandidate,
    RetentionKind,
    RetentionPolicyError,
    content_fingerprint,
    utc,
)
from app.services.skills import skill_retention_candidate
from app.services.state_content_clocks import age
from app.tools.contracts import ToolError

ENTITIES = frozenset({"skills", "operations", "evaluation_jobs"})
KINDS = {"skills": RetentionKind.SKILL, "operations": RetentionKind.OPERATION,
         "evaluation_jobs": RetentionKind.JOB}
OPERATIONS_IDLE = frozenset({"pending", "expired", "succeeded", "failed", "reviewed"})
EVALUATIONS_IDLE = frozenset({"completed", "quality_failed", "failed"})


@dataclass(frozen=True)
class StateInventory:
    candidates: tuple[RetentionCandidate, ...]
    owner_busy: bool


def _tables(session, entities, native):
    if not entities or not set(entities).issubset(ENTITIES):
        raise RetentionPolicyError("retention_state_entity_unknown")
    connection = session.connection()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"} or native and dialect != "sqlite":
        raise RetentionPolicyError("retention_state_profile_unknown")
    schema = "veridra_private" if dialect == "postgresql" else None
    inspector, metadata = inspect(connection), MetaData()
    names = set(entities)
    if "skills" in entities:
        names.add("skill_content_clocks")
    if set(entities) - {"skills"}:
        names.add("state_content_clocks")
    result = {}
    for name in names:
        actual = "jobs" if native and name == "evaluation_jobs" else name
        if not inspector.has_table(actual, schema=schema):
            raise RetentionPolicyError("retention_state_schema_incomplete")
        table = Table(actual, metadata, schema=schema, autoload_with=connection, resolve_fks=False)
        expected = {
            "skills": {"id", "user_id", "spec", "updated"},
            "operations": {"id", "user_id", "spec", "result", "error_code", "state", "updated",
                           "request_key", "digest", "resource_id", "archived"},
            "evaluation_jobs": {"id", "owner", "checkpoint", "created_at", "status"},
            "state_content_clocks": {"entity", "record_id", "user_id", "content_hash",
                                     "changed_at"},
            "skill_content_clocks": {"skill_id", "user_id", "content_hash", "content_changed"},
        }[name]
        if not expected.issubset(table.c.keys()) or not table.primary_key.columns:
            raise RetentionPolicyError("retention_state_schema_incomplete")
        result[name] = table
    return result


def _cleared_operation(row):
    return (row["state"] in OPERATIONS_IDLE - {"pending"} and row["spec"] == "{}"
            and row["result"] is None and row["error_code"] is None and row["archived"] == 1)


async def state_inventory(db, owner_id, *, entities=ENTITIES, native=False, lock=False):
    if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 200:
        raise RetentionPolicyError("invalid_retention_owner")
    tables = await db.run_sync(_tables, entities, native)
    candidates, busy = [], False
    for entity in sorted(entities):
        table = tables[entity]
        owner_field = "owner" if entity == "evaluation_jobs" else "user_id"
        query = select(table).where(table.c[owner_field] == owner_id)
        if lock and db.bind.dialect.name == "postgresql":
            query = query.with_for_update()
        rows = await db.stream(query.execution_options(yield_per=64))
        async for row in rows.mappings():
            if entity == "operations" and _cleared_operation(row):
                continue  # Keep the anti-replay tombstone, not a work-content candidate.
            clock_table = tables["skill_content_clocks" if entity == "skills"
                                 else "state_content_clocks"]
            clock_query = select(clock_table).where(
                clock_table.c.skill_id == row["id"] if entity == "skills" else (
                    (clock_table.c.entity == entity) & (clock_table.c.record_id == row["id"])
                ),
            )
            if lock and db.bind.dialect.name == "postgresql":
                clock_query = clock_query.with_for_update()
            clock = (await db.execute(clock_query)).mappings().first()
            if entity == "skills":
                try:
                    candidate = skill_retention_candidate(row, clock)
                except ToolError:
                    raise RetentionPolicyError("retention_state_clock_mismatch") from None
            else:
                try:
                    stamp = datetime.fromtimestamp(age(entity, row, clock,
                                                       owner_column=owner_field), UTC)
                except (ValueError, OverflowError, OSError):
                    raise RetentionPolicyError("retention_state_clock_mismatch") from None
                active = (row["state"] not in OPERATIONS_IDLE if entity == "operations"
                          else row["status"] not in EVALUATIONS_IDLE)
                identity = f"{entity}:{row['id']}"
                candidate = RetentionCandidate(
                    owner_id=owner_id, kind=KINDS[entity], record_id=identity,
                    changed_at=stamp, active=active, fingerprint=content_fingerprint(
                        owner_id=owner_id, kind=KINDS[entity], record_id=identity,
                        changed_at=stamp, values={"row": dict(row), "clock": dict(clock)},
                    ),
                )
            busy = busy or candidate.active
            candidates.append(candidate)
    return StateInventory(tuple(candidates), busy)


async def purge_state(db, owner_id, approved, *, entities=ENTITIES, native=False, now):
    """No commit or provider calls. Caller supplies an authenticated frozen approval."""
    if type(now) not in {int, float} or not isfinite(now) or now < 0:
        raise RetentionPolicyError("invalid_retention_time")
    approved = tuple(approved)
    keys = [(item.kind.value, item.record_id) for item in approved]
    cutoff = datetime.fromtimestamp(now, UTC) - timedelta(days=CONTENT_RETENTION_DAYS)
    if len(set(keys)) != len(keys) or any(utc(item.changed_at) > cutoff for item in approved):
        raise RetentionPolicyError("retention_preview_changed")
    tables = await db.run_sync(_tables, entities, native)
    if db.bind.dialect.name == "sqlite":
        # Force a real SQLite write transaction BEFORE validating payloads.
        # A SELECT on legacy sqlite3 transaction mode alone does not fence writes.
        clock_table = tables.get("state_content_clocks")
        if clock_table is None:
            clock_table = tables["skill_content_clocks"]
        field = "changed_at" if "changed_at" in clock_table.c else "content_changed"
        await db.execute(update(clock_table).where(
            clock_table.c.user_id == owner_id,
        ).values({field: clock_table.c[field]}))
    inventory = await state_inventory(db, owner_id, entities=entities, native=native, lock=True)
    if inventory.owner_busy:
        raise RetentionPolicyError("retention_owner_busy")
    current = {item.key: item for item in inventory.candidates}
    for item in approved:
        row = current.get((item.kind.value, item.record_id))
        if (row is None or row.fingerprint != item.fingerprint
                or utc(row.changed_at) != utc(item.changed_at)):
            raise RetentionPolicyError("retention_preview_changed")
    deleted, redacted = 0, 0
    for item in approved:
        entity, identity = item.record_id.split(":", 1)
        if entity not in entities or item.kind != KINDS[entity]:
            raise RetentionPolicyError("retention_state_entity_unknown")
        table = tables[entity]
        owner_column = "owner" if entity == "evaluation_jobs" else "user_id"
        scope = (table.c.id == identity) & (table.c[owner_column] == owner_id)
        if entity == "operations":
            result = await db.execute(update(table).where(scope).values(
                spec="{}", result=None, error_code=None, archived=1, updated=now,
                state=case((table.c.state == "pending", "expired"), else_=table.c.state),
            ))
            redacted += 1
        else:
            if entity == "skills":
                clock_table = tables["skill_content_clocks"]
                await db.execute(delete(clock_table).where(
                    clock_table.c.skill_id == identity, clock_table.c.user_id == owner_id,
                ))
            result = await db.execute(delete(table).where(scope))
            deleted += 1
        if result.rowcount != 1:
            raise RetentionPolicyError("retention_preview_changed")
        if entity != "skills":
            clock_table = tables["state_content_clocks"]
            await db.execute(delete(clock_table).where(
                clock_table.c.entity == entity, clock_table.c.record_id == identity,
                clock_table.c.user_id == owner_id,
            ))
    return {"deleted": deleted, "redacted": redacted}
