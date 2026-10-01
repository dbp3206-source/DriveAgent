"""Portable, owner-scoped approval ledger for Google side effects.

The local product keeps the existing SQLite file.  Cloud deployments use the
same contract on PostgreSQL so an approval, checkpoint, or ambiguous provider
write survives process restarts and Render redeploys.
"""

import hashlib
import json
import time
from uuid import uuid4

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.services.operations import OperationStore
from app.services.relational_state import state_engine, state_transaction
from app.tools.contracts import ToolError

metadata = MetaData()
operations = Table(
    "operations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", Text, nullable=False, index=True),
    Column("request_key", Text, nullable=False),
    Column("capability", Text, nullable=False),
    Column("spec", Text, nullable=False),
    Column("digest", String(64), nullable=False),
    Column("state", Text, nullable=False),
    Column("created", Float, nullable=False),
    Column("resource_id", Text),
    Column("result", Text),
    Column("error_code", Text),
    Column("archived", Integer, nullable=False, default=0),
    Column("updated", Float, nullable=False),
)
operation_request_index = Index(
    "uq_operations_user_request",
    operations.c.user_id,
    operations.c.request_key,
    unique=True,
)
operation_status_index = Index(
    "ix_operations_user_state_created",
    operations.c.user_id,
    operations.c.archived,
    operations.c.state,
    operations.c.created.desc(),
)


def operation_store_for(settings: Settings) -> OperationStore:
    relational_url = getattr(settings, "relational_state_url", None)
    if relational_url is None:
        return OperationStore(settings.data_dir / "operations.db")
    return RelationalOperationStore(state_engine(relational_url.get_secret_value()))


def initialize_operation_store(settings: Settings) -> None:
    if settings.relational_state_url is not None:
        RelationalOperationStore.create_schema(
            state_engine(settings.relational_state_url.get_secret_value())
        )


class RelationalOperationStore(OperationStore):
    """The OperationStore contract implemented with transactional row locks."""

    def __init__(self, engine: Engine):
        if engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ValueError("Operation ledger requires SQLite or PostgreSQL")
        self.engine = engine

    @staticmethod
    def create_schema(engine: Engine) -> None:
        metadata.create_all(engine)

    @staticmethod
    def _digest(capability: str, spec: dict) -> tuple[str, str]:
        canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256((capability + "\n" + canonical).encode()).hexdigest()
        return canonical, digest

    def prepare(self, user_id: str, request_key: str, capability: str, spec: dict) -> dict:
        canonical, digest = self._digest(capability, spec)
        stamp = time.time()
        operation_id = str(uuid4())
        with state_transaction(self.engine) as db:
            if self.engine.dialect.name == "postgresql":
                lock_key = ("operation:" + user_id + ":" + request_key).encode()
                scope = int.from_bytes(
                    hashlib.sha256(lock_key).digest()[:8],
                    "big",
                    signed=True,
                )
                db.execute(text("SELECT pg_advisory_xact_lock(:scope)"), {"scope": scope})
            old = db.execute(select(operations).where(
                operations.c.user_id == user_id,
                operations.c.request_key == request_key,
            )).mappings().first()
            if old is not None:
                if old["digest"] != digest:
                    raise ToolError(
                        "Mã yêu cầu đã gắn với một bản khác.", code="idempotency_conflict"
                    )
                return dict(old)
            db.execute(insert(operations).values(
                id=operation_id,
                user_id=user_id,
                request_key=request_key,
                capability=capability,
                spec=canonical,
                digest=digest,
                state="pending",
                created=stamp,
                archived=0,
                updated=stamp,
            ))
        return self.get(user_id, operation_id)

    def get(self, user_id: str, operation_id: str) -> dict:
        with self.engine.connect() as db:
            row = db.execute(select(operations).where(
                operations.c.id == operation_id,
                operations.c.user_id == user_id,
            )).mappings().first()
        if row is None:
            raise ToolError("Không tìm thấy thao tác.", code="operation_not_found")
        return dict(row)

    def list_status(self, user_id: str, *, limit: int = 50) -> dict:
        safe_limit = max(1, min(int(limit), 200))
        stamp = time.time()
        with state_transaction(self.engine) as db:
            db.execute(update(operations).where(
                operations.c.user_id == user_id,
                operations.c.state == "pending",
                operations.c.created < stamp - 1800,
            ).values(state="expired", updated=stamp))
            rows = db.execute(select(
                operations.c.id,
                operations.c.capability,
                operations.c.state,
                operations.c.created,
                operations.c.resource_id,
                operations.c.error_code,
            ).where(
                operations.c.user_id == user_id,
                operations.c.archived == 0,
            ).order_by(operations.c.created.desc()).limit(safe_limit)).mappings().all()
        items = [dict(row) for row in rows]
        summary: dict[str, int] = {}
        reconcilable = {
            "sheets_create", "sheets_edit", "docs_create", "docs_edit", "gmail_draft_create"
        }
        for item in items:
            state = str(item["state"])
            summary[state] = summary.get(state, 0) + 1
            item["reconcilable"] = bool(
                state == "uncertain"
                and item["resource_id"]
                and item["capability"] in reconcilable
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
        stamp = time.time()
        expired = False
        with state_transaction(self.engine) as db:
            query = select(operations).where(
                operations.c.id == operation_id,
                operations.c.user_id == user_id,
            )
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update()
            row = db.execute(query).mappings().first()
            if row is None:
                raise ToolError("Không tìm thấy thao tác.", code="operation_not_found")
            if row["digest"] != approved_digest:
                raise ToolError("Nội dung được duyệt không khớp bản chờ.", code="approval_mismatch")
            if row["state"] != "pending":
                raise ToolError(
                    "Thao tác đã được nhận; kiểm tra kết quả, không gửi lại.",
                    code="operation_already_claimed",
                )
            if stamp - row["created"] > 1800:
                db.execute(update(operations).where(
                    operations.c.id == operation_id,
                    operations.c.user_id == user_id,
                    operations.c.state == "pending",
                ).values(state="expired", updated=stamp))
                expired = True
            else:
                changed = db.execute(update(operations).where(
                    operations.c.id == operation_id,
                    operations.c.user_id == user_id,
                    operations.c.state == "pending",
                ).values(state="running", updated=stamp)).rowcount
                if changed != 1:
                    raise ToolError(
                        "Thao tác đã được nhận; kiểm tra kết quả, không gửi lại.",
                        code="operation_already_claimed",
                    )
        if expired:
            raise ToolError("Bản xem trước đã quá 30 phút; hãy tạo lại.", code="approval_expired")
        return dict(row)

    def checkpoint(self, user_id: str, operation_id: str, resource_id: str) -> None:
        self._running_update(user_id, operation_id, resource_id=resource_id)

    def finish(self, user_id: str, operation_id: str, result: dict) -> None:
        self._running_update(
            user_id,
            operation_id,
            state="succeeded",
            result=json.dumps(result, ensure_ascii=False),
        )

    def uncertain(self, user_id: str, operation_id: str, error_code: str) -> None:
        self._running_update(user_id, operation_id, state="uncertain", error_code=error_code)

    def fail(self, user_id: str, operation_id: str, error_code: str) -> None:
        self._running_update(user_id, operation_id, state="failed", error_code=error_code)

    def _running_update(self, user_id: str, operation_id: str, **values) -> None:
        with self.engine.begin() as db:
            changed = db.execute(update(operations).where(
                operations.c.id == operation_id,
                operations.c.user_id == user_id,
                operations.c.state == "running",
            ).values(**values, updated=time.time())).rowcount
        if changed != 1:
            raise ToolError(
                "Thao tác không ở trạng thái đang chạy.", code="operation_state_conflict"
            )

    def finish_reconciliation(self, user_id: str, operation_id: str, result: dict) -> None:
        with self.engine.begin() as db:
            changed = db.execute(update(operations).where(
                operations.c.id == operation_id,
                operations.c.user_id == user_id,
                operations.c.state == "uncertain",
                operations.c.resource_id.is_not(None),
            ).values(
                state="succeeded",
                result=json.dumps(result, ensure_ascii=False),
                error_code=None,
                updated=time.time(),
            )).rowcount
        if changed != 1:
            raise ToolError(
                "Thao tác không thể đối soát ở trạng thái hiện tại.",
                code="operation_state_conflict",
            )

    def archive(self, user_id: str, operation_id: str) -> None:
        with self.engine.begin() as db:
            changed = db.execute(update(operations).where(
                operations.c.id == operation_id,
                operations.c.user_id == user_id,
                operations.c.state != "running",
            ).values(archived=1, updated=time.time())).rowcount
        if changed != 1:
            raise ToolError(
                "Không thể lưu trữ thao tác đang chạy hoặc không tồn tại.",
                code="operation_state_conflict",
            )

    def acknowledge_uncertain(self, user_id: str, operation_id: str) -> None:
        with self.engine.begin() as db:
            changed = db.execute(update(operations).where(
                operations.c.id == operation_id,
                operations.c.user_id == user_id,
                operations.c.state == "uncertain",
            ).values(state="reviewed", updated=time.time())).rowcount
        if changed != 1:
            raise ToolError(
                "Chỉ có thể đóng cảnh báo của thao tác chưa xác định.",
                code="operation_state_conflict",
            )
