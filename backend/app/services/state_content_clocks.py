"""Content clocks for approval/evaluation payloads, never a second payload copy.

Seed legacy rows at their first verified observation, not a fabricated historic
edit date. Startup can reconcile older writers; read-only inventory never repairs
or extends a clock. Identity and anti-replay ledgers retain their own lifecycle.
"""

import hashlib
import json
import math

from sqlalchemy import Column, Float, MetaData, String, Table, insert, select, update

from app.services.retention_policy import RetentionPolicyError

metadata = MetaData()
clocks = Table(
    "state_content_clocks", metadata,
    Column("entity", String(32), primary_key=True),
    Column("record_id", String(36), primary_key=True),
    Column("user_id", String(200), nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("changed_at", Float, nullable=False),
)
FIELDS = {"operations": ("spec", "result", "error_code"),
          "evaluation_jobs": ("checkpoint",)}


def digest(entity, row):
    if entity not in FIELDS:
        raise RetentionPolicyError("retention_state_entity_unknown")
    body = json.dumps([row[field] for field in FIELDS[entity]],
                      ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode()).hexdigest()


def age(entity, row, clock, *, owner_column="user_id"):
    if (clock is None or clock["entity"] != entity or clock["record_id"] != row["id"]
            or clock["user_id"] != row[owner_column]
            or clock["content_hash"] != digest(entity, row)):
        raise RetentionPolicyError("retention_state_clock_mismatch")
    stamp = clock["changed_at"]
    if type(stamp) not in {int, float} or not math.isfinite(stamp) or stamp < 0:
        raise RetentionPolicyError("retention_state_clock_invalid")
    return stamp


def _values(entity, row, old, now, owner_column):
    if type(now) not in {int, float} or not math.isfinite(now) or now < 0:
        raise RetentionPolicyError("retention_state_clock_invalid")
    owner = row[owner_column]
    if old is not None and old["user_id"] != owner:
        raise RetentionPolicyError("retention_state_clock_mismatch")
    hashed = digest(entity, row)
    if old is not None and old["content_hash"] == hashed:
        age(entity, row, old, owner_column=owner_column)
        return None
    return {"entity": entity, "record_id": row["id"], "user_id": owner,
            "content_hash": hashed, "changed_at": now}


def initialize_sqlite(db):
    existed = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='state_content_clocks'",
    ).fetchone() is not None
    db.execute("""CREATE TABLE IF NOT EXISTS state_content_clocks (
        entity TEXT NOT NULL, record_id TEXT NOT NULL, user_id TEXT NOT NULL,
        content_hash TEXT NOT NULL, changed_at REAL NOT NULL,
        PRIMARY KEY(entity, record_id))""")
    return not existed


def record_sqlite(db, entity, row, now, *, owner_column="user_id"):
    old = db.execute("SELECT * FROM state_content_clocks WHERE entity=? AND record_id=?",
                     (entity, row["id"])).fetchone()
    values = _values(entity, row, old, now, owner_column)
    if values is None:
        return
    db.execute("""INSERT INTO state_content_clocks
        (entity, record_id, user_id, content_hash, changed_at) VALUES (?,?,?,?,?)
        ON CONFLICT(entity, record_id) DO UPDATE SET content_hash=excluded.content_hash,
        changed_at=excluded.changed_at""", tuple(values.values()))


def seed_sqlite(db, entity, now, *, table=None, owner_column="user_id"):
    actual = {"operations": "operations", "evaluation_jobs": "jobs"}[entity]
    if table is not None and table != actual:
        raise RetentionPolicyError("retention_state_entity_unknown")
    # Table identifiers come only from the closed mapping above.
    cursor = db.execute(f"SELECT * FROM {actual}")
    while batch := cursor.fetchmany(64):
        for row in batch:
            record_sqlite(db, entity, row, now, owner_column=owner_column)


def record_relational(db, entity, row, now, *, owner_column="user_id"):
    query = select(clocks).where(clocks.c.entity == entity, clocks.c.record_id == row["id"])
    if db.dialect.name == "postgresql":
        query = query.with_for_update()
    old = db.execute(query).mappings().first()
    values = _values(entity, row, old, now, owner_column)
    if values is None:
        return
    if old is None:
        db.execute(insert(clocks).values(**values))
    else:
        db.execute(update(clocks).where(
            clocks.c.entity == entity, clocks.c.record_id == row["id"],
            clocks.c.user_id == row[owner_column],
        ).values(content_hash=values["content_hash"], changed_at=values["changed_at"]))


def seed_relational(db, entity, table, now, *, owner_column="user_id"):
    if table.name != {"operations": "operations", "evaluation_jobs": "evaluation_jobs"}[entity]:
        raise RetentionPolicyError("retention_state_entity_unknown")
    query = select(table)
    if db.dialect.name == "postgresql":
        # These are startup observations, not a user-facing inventory. Serialize
        # with any old writer still completing a deployment handover.
        query = query.with_for_update()
    rows = db.execute(query).mappings()
    for row in rows:
        record_relational(db, entity, row, now, owner_column=owner_column)
