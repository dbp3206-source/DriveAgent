"""User-owned reusable procedures stored locally; they are plans, never executable code."""

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.tools.contracts import ToolError


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
            "drive", "rag", "memory", "docs", "slides", "sheets", "visuals", "gmail", "artifacts"
        ]
    ] = Field(default_factory=list, max_length=9)
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

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

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
            changed = db.execute(
                "UPDATE skills SET active=0,updated=? WHERE id=? AND user_id=?",
                (time.time(), skill_id, user_id),
            ).rowcount
        if changed != 1:
            raise ToolError("Không tìm thấy skill.", code="skill_not_found")
        return self.get(user_id, skill_id)

    @staticmethod
    def _decode(row) -> dict:
        spec = json.loads(row["spec"])
        return {"id": row["id"], "revision": row["revision"], "active": bool(row["active"]), **spec}

    def run(self, user_id: str, name: str, inputs: dict[str, str]) -> dict:
        row = self.get(user_id, name)
        if not row["active"]:
            raise ToolError("Skill đã được lưu trữ.", code="skill_archived")
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
