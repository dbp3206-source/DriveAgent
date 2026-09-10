"""Durable, user-bound approval ledger for external side effects.

Claim before sending: a crash or lost response must never trigger a blind resend.
``running`` after a crash requires reconciliation, not an automatic retry. This
provides at-most-one local attempt, not an impossible exactly-once network promise.
"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from app.tools.contracts import ToolError


class OperationStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, request_key TEXT NOT NULL,
                capability TEXT NOT NULL, spec TEXT NOT NULL, digest TEXT NOT NULL,
                state TEXT NOT NULL, created REAL NOT NULL, resource_id TEXT,
                result TEXT, error_code TEXT,
                UNIQUE(user_id, request_key))""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def prepare(self, user_id: str, request_key: str, capability: str, spec: dict) -> dict:
        canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256((capability + "\n" + canonical).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT * FROM operations WHERE user_id=? AND request_key=?", (user_id, request_key)
            ).fetchone()
            if old:
                if old["digest"] != digest:
                    raise ToolError(
                        "Mã yêu cầu đã gắn với một bản khác.", code="idempotency_conflict"
                    )
                return dict(old)
            operation_id = str(uuid4())
            db.execute(
                """INSERT INTO operations
                (id,user_id,request_key,capability,spec,digest,state,created)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    operation_id,
                    user_id,
                    request_key,
                    capability,
                    canonical,
                    digest,
                    "pending",
                    time.time(),
                ),
            )
        return self.get(user_id, operation_id)

    def get(self, user_id: str, operation_id: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM operations WHERE id=? AND user_id=?", (operation_id, user_id)
            ).fetchone()
        if row is None:
            raise ToolError("Không tìm thấy thao tác.", code="operation_not_found")
        return dict(row)

    def claim(self, user_id: str, operation_id: str, approved_digest: str) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM operations WHERE id=? AND user_id=?", (operation_id, user_id)
            ).fetchone()
            if row is None:
                raise ToolError("Không tìm thấy thao tác.", code="operation_not_found")
            if row["digest"] != approved_digest:
                raise ToolError("Nội dung được duyệt không khớp bản chờ.", code="approval_mismatch")
            if row["state"] != "pending":
                raise ToolError(
                    "Thao tác đã được nhận; kiểm tra kết quả, không gửi lại.",
                    code="operation_already_claimed",
                )
            if time.time() - row["created"] > 1800:
                raise ToolError(
                    "Bản xem trước đã quá 30 phút; hãy tạo lại.", code="approval_expired"
                )
            db.execute("UPDATE operations SET state='running' WHERE id=?", (operation_id,))
        return dict(row)

    def checkpoint(self, user_id: str, operation_id: str, resource_id: str):
        self._update(user_id, operation_id, "resource_id=?", (resource_id,))

    def finish(self, user_id: str, operation_id: str, result: dict):
        self._update(
            user_id,
            operation_id,
            "state='succeeded', result=?",
            (json.dumps(result, ensure_ascii=False),),
        )

    def uncertain(self, user_id: str, operation_id: str, error_code: str):
        # Store a safe code only, never raw provider errors/headers/tokens.
        self._update(user_id, operation_id, "state='uncertain', error_code=?", (error_code,))

    def fail(self, user_id: str, operation_id: str, error_code: str):
        """Record a confirmed pre-side-effect failure that may be prepared again safely."""

        self._update(user_id, operation_id, "state='failed', error_code=?", (error_code,))

    def _update(self, user_id: str, operation_id: str, clause: str, values: tuple):
        with self.connect() as db:
            changed = db.execute(
                f"UPDATE operations SET {clause} WHERE id=? AND user_id=? AND state='running'",
                (*values, operation_id, user_id),
            ).rowcount
            if changed != 1:
                raise ToolError(
                    "Thao tác không ở trạng thái đang chạy.", code="operation_state_conflict"
                )
