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
            columns = {row[1] for row in db.execute("PRAGMA table_info(operations)")}
            if "archived" not in columns:
                db.execute(
                    "ALTER TABLE operations ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
                )
            if "updated" not in columns:
                db.execute("ALTER TABLE operations ADD COLUMN updated REAL")
                db.execute("UPDATE operations SET updated=created WHERE updated IS NULL")
            db.execute(
                "CREATE INDEX IF NOT EXISTS ix_operations_user_state_created "
                "ON operations(user_id, archived, state, created DESC)"
            )

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

    def list_status(self, user_id: str, *, limit: int = 50) -> dict:
        """Return a redacted per-user operational ledger for support and recovery.

        The original ``spec`` may contain document text, spreadsheet values or
        email recipients, so it must never leave this service through a status
        endpoint.  A user can still see whether an attempt is waiting, failed,
        or uncertain and whether provider read-back recovery is available.
        """

        safe_limit = max(1, min(int(limit), 200))
        with self.connect() as db:
            db.execute(
                "UPDATE operations SET state='expired', updated=? "
                "WHERE user_id=? AND state='pending' AND created<?",
                (time.time(), user_id, time.time() - 1800),
            )
            rows = db.execute(
                """SELECT id, capability, state, created, resource_id, error_code
                FROM operations WHERE user_id=? AND archived=0
                ORDER BY created DESC LIMIT ?""",
                (user_id, safe_limit),
            ).fetchall()
        items = [dict(row) for row in rows]
        summary: dict[str, int] = {}
        for item in items:
            state = str(item["state"])
            summary[state] = summary.get(state, 0) + 1
            item["reconcilable"] = bool(
                state == "uncertain"
                and item["resource_id"]
                and item["capability"]
                in {
                    "sheets_create",
                    "sheets_edit",
                    "docs_create",
                    "docs_edit",
                    "gmail_draft_create",
                }
            )
        return {
            "items": items,
            "summary": summary,
            "attention_count": sum(
                count for state, count in summary.items() if state in {"running", "uncertain"}
            ),
            "pending_previews": summary.get("pending", 0),
        }

    def claim(self, user_id: str, operation_id: str, approved_digest: str) -> dict:
        expired = False
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
                db.execute(
                    "UPDATE operations SET state='expired', updated=? WHERE id=? AND user_id=?",
                    (time.time(), operation_id, user_id),
                )
                expired = True
            else:
                db.execute(
                    "UPDATE operations SET state='running', updated=? WHERE id=?",
                    (time.time(), operation_id),
                )
        if expired:
            raise ToolError("Bản xem trước đã quá 30 phút; hãy tạo lại.", code="approval_expired")
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

    def finish_reconciliation(self, user_id: str, operation_id: str, result: dict):
        """Mark an uncertain write verified after a read-only reconciliation."""

        with self.connect() as db:
            changed = db.execute(
                """UPDATE operations
                SET state='succeeded', result=?, error_code=NULL, updated=?
                WHERE id=? AND user_id=? AND state='uncertain' AND resource_id IS NOT NULL""",
                (json.dumps(result, ensure_ascii=False), time.time(), operation_id, user_id),
            ).rowcount
            if changed != 1:
                raise ToolError(
                    "Thao tác không thể đối soát ở trạng thái hiện tại.",
                    code="operation_state_conflict",
                )

    def archive(self, user_id: str, operation_id: str) -> None:
        """Hide only terminal/abandoned work; active writes remain visible."""

        with self.connect() as db:
            changed = db.execute(
                """UPDATE operations SET archived=1, updated=?
                WHERE id=? AND user_id=? AND state NOT IN ('running')""",
                (time.time(), operation_id, user_id),
            ).rowcount
            if changed != 1:
                raise ToolError(
                    "Không thể lưu trữ thao tác đang chạy hoặc không tồn tại.",
                    code="operation_state_conflict",
                )

    def acknowledge_uncertain(self, user_id: str, operation_id: str) -> None:
        """Close a warning after the user manually checked the provider.

        ``reviewed`` deliberately does not mean succeeded. It only records that
        the ambiguous attempt was handled and must still never be auto-retried.
        """

        with self.connect() as db:
            changed = db.execute(
                """UPDATE operations SET state='reviewed', updated=?
                WHERE id=? AND user_id=? AND state='uncertain'""",
                (time.time(), operation_id, user_id),
            ).rowcount
            if changed != 1:
                raise ToolError(
                    "Chỉ có thể đóng cảnh báo của thao tác chưa xác định.",
                    code="operation_state_conflict",
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
                f"UPDATE operations SET {clause}, updated=? "
                "WHERE id=? AND user_id=? AND state='running'",
                (*values, time.time(), operation_id, user_id),
            ).rowcount
            if changed != 1:
                raise ToolError(
                    "Thao tác không ở trạng thái đang chạy.", code="operation_state_conflict"
                )
