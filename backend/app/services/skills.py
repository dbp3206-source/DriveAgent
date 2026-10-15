"""User-owned reusable procedures stored locally; they are plans, never executable code."""

import hashlib
import json
import math
import re
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.tools.contracts import ToolError


def skill_content_hash(spec: str) -> str:
    return hashlib.sha256(spec.encode()).hexdigest()


def skill_content_age(row, clock) -> float:
    """Old app versions can edit a skill without writing the companion clock."""
    if clock is not None and clock["user_id"] != row["user_id"]:
        raise ToolError("Chưa đối chiếu được thời hạn lưu mẫu.", code="retention_clock_mismatch")
    value = (clock["content_changed"] if clock is not None
             and clock["content_hash"] == skill_content_hash(row["spec"])
             else row["updated"])
    if not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ToolError("Chưa đối chiếu được thời hạn lưu mẫu.", code="retention_clock_invalid")
    return float(value)


def skill_retention_candidate(row, clock):
    from app.services.retention_policy import (
        RetentionCandidate,
        RetentionKind,
        content_fingerprint,
    )

    try:
        stamp = datetime.fromtimestamp(skill_content_age(row, clock), UTC)
    except (ValueError, OverflowError, OSError):
        raise ToolError("Chưa đối chiếu được thời hạn lưu mẫu.",
                        code="retention_clock_invalid") from None
    record_id = f"skills:{row['id']}"
    return RetentionCandidate(
        owner_id=row["user_id"], kind=RetentionKind.SKILL, record_id=record_id,
        changed_at=stamp, fingerprint=content_fingerprint(
            owner_id=row["user_id"], kind=RetentionKind.SKILL, record_id=record_id,
            changed_at=stamp, values=dict(row),
        ),
    )


class SkillSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=3, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=3, max_length=500)
    goal: str = Field(min_length=3, max_length=500)
    procedure: list[str] = Field(min_length=1, max_length=20)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    preferred_capabilities: list[
        Literal[
            "drive", "rag", "memory", "docs", "sheets", "gmail", "artifacts"
        ]
    ] = Field(default_factory=list, max_length=7)
    output_format: str = Field(min_length=2, max_length=100)

    @field_validator("procedure", "constraints")
    @classmethod
    def bounded_lines(cls, value: list[str]):
        if any(not line.strip() or len(line) > 500 for line in value):
            raise ValueError("Skill steps must contain 1–500 visible characters")
        return value


class SkillStore:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "skills.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
                spec TEXT NOT NULL, revision INTEGER NOT NULL, active INTEGER NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(user_id,name))""")
            # A companion keeps the original eight-column table compatible with
            # older local versions using positional INSERTs during rollback.
            db.execute("""CREATE TABLE IF NOT EXISTS skill_content_clocks (
                skill_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                content_hash TEXT NOT NULL, content_changed REAL NOT NULL,
                FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE)""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _clock(db, row, *, spec: str, now: float) -> None:
        clock = db.execute(
            "SELECT * FROM skill_content_clocks WHERE skill_id=?", (row["id"],)
        ).fetchone()
        prior_age = skill_content_age(row, clock)
        age = now if spec != row["spec"] else prior_age
        db.execute(
            "INSERT INTO skill_content_clocks VALUES (?, ?, ?, ?) "
            "ON CONFLICT(skill_id) DO UPDATE SET content_hash=excluded.content_hash, "
            "content_changed=excluded.content_changed",
            (row["id"], row["user_id"], skill_content_hash(spec), age),
        )

    def save(self, user_id: str, spec: SkillSpec, expected_revision: int | None = None) -> dict:
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM skills WHERE user_id=? AND name=?", (user_id, spec.name)
            ).fetchone()
            if row:
                if expected_revision is None or row["revision"] != expected_revision:
                    raise ToolError(
                        "Skill đã thay đổi; tải lại trước khi lưu.", code="revision_conflict"
                    )
                self._clock(db, row, spec=spec.model_dump_json(), now=now)
                db.execute(
                    "UPDATE skills SET spec=?,revision=revision+1,active=1,updated=? WHERE id=?",
                    (spec.model_dump_json(), now, row["id"]),
                )
                skill_id = row["id"]
            else:
                if expected_revision not in {None, 0}:
                    raise ToolError("Không tìm thấy phiên bản skill.", code="skill_not_found")
                skill_id = str(uuid4())
                db.execute(
                    "INSERT INTO skills VALUES (?,?,?,?,?,?,?,?)",
                    (skill_id, user_id, spec.name, spec.model_dump_json(), 1, 1, now, now),
                )
                self._clock(db, {"id": skill_id, "user_id": user_id,
                                 "spec": spec.model_dump_json(), "updated": now},
                            spec=spec.model_dump_json(), now=now)
        return self.get(user_id, skill_id)

    def list(self, user_id: str, include_archived: bool = False) -> list[dict]:
        query = "SELECT * FROM skills WHERE user_id=?"
        args: list[object] = [user_id]
        if not include_archived:
            query += " AND active=1"
        query += " ORDER BY updated DESC"
        with self.connect() as db:
            rows = db.execute(query, args).fetchall()
        return [self._decode(row) for row in rows]

    def get(self, user_id: str, skill_id_or_name: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM skills WHERE user_id=? AND (id=? OR name=?)",
                (user_id, skill_id_or_name, skill_id_or_name),
            ).fetchone()
        if row is None:
            raise ToolError("Không tìm thấy skill.", code="skill_not_found")
        return self._decode(row)

    def archive(self, user_id: str, skill_id: str) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM skills WHERE id=? AND user_id=?",
                             (skill_id, user_id)).fetchone()
            if row is None:
                raise ToolError("Không tìm thấy skill.", code="skill_not_found")
            self._clock(db, row, spec=row["spec"], now=time.time())
            changed = db.execute(
                "UPDATE skills SET active=0,updated=? WHERE id=? AND user_id=?",
                (time.time(), skill_id, user_id),
            ).rowcount
        if changed != 1:
            raise ToolError("Không tìm thấy skill.", code="skill_not_found")
        return self.get(user_id, skill_id)

    def retention_candidates(self, user_id: str):
        """Read all owned skills, including archived; never return their text."""
        with self.connect() as db:
            rows = db.execute("SELECT * FROM skills WHERE user_id=?", (user_id,)).fetchall()
            return [skill_retention_candidate(row, db.execute(
                "SELECT * FROM skill_content_clocks WHERE skill_id=?", (row["id"],)
            ).fetchone()) for row in rows]

    @staticmethod
    def _decode(row) -> dict:
        spec = json.loads(row["spec"])
        return {"id": row["id"], "revision": row["revision"], "active": bool(row["active"]), **spec}

    def run(self, user_id: str, name: str, inputs: dict[str, str]) -> dict:
        row = self.get(user_id, name)
        if not row["active"]:
            raise ToolError("Skill đã được lưu trữ.", code="skill_archived")
        retired = {"slides", "visuals"} & set(row.get("preferred_capabilities", []))
        if retired:
            raise ToolError(
                "Skill cũ dùng Slides/Visual đã rút khỏi sản phẩm. "
                "Hãy tạo phiên bản mới bằng Docs, Sheets hoặc Gmail.",
                code="skill_capability_retired",
            )
        placeholders = set(re.findall(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}", json.dumps(row)))
        missing = placeholders - inputs.keys()
        if missing:
            raise ToolError(
                "Thiếu đầu vào cho skill: " + ", ".join(sorted(missing)), code="skill_input_missing"
            )

        def expand(value):
            if isinstance(value, str):
                return re.sub(
                    r"\{([a-zA-Z][a-zA-Z0-9_]*)\}",
                    lambda match: inputs[match.group(1)],
                    value,
                )
            if isinstance(value, list):
                return [expand(item) for item in value]
            return value

        return {
            "skill_id": row["id"],
            "name": row["name"],
            "revision": row["revision"],
            "goal": expand(row["goal"]),
            "procedure": expand(row["procedure"]),
            "constraints": expand(row["constraints"]),
            "preferred_capabilities": row["preferred_capabilities"],
            "output_format": expand(row["output_format"]),
            "fresh_context_required": True,
        }
