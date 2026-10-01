"""At-most-once remote action nonce ledger for PostgreSQL cloud state."""

import hashlib
import time

from sqlalchemy import Column, Integer, MetaData, String, Table, delete, insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.services.relational_state import state_engine, state_transaction
from app.tools.contracts import ToolError

metadata = MetaData()
consumed_actions = Table(
    "consumed_remote_actions",
    metadata,
    Column("nonce_hash", String(64), primary_key=True),
    Column("expires_at", Integer, nullable=False),
    Column("consumed_at", Integer, nullable=False),
)


class RelationalRemoteActionLedger:
    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def create_schema(engine: Engine) -> None:
        metadata.create_all(engine)

    def consume(self, nonce: str, expires_at: int) -> None:
        nonce_hash = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        now = int(time.time())
        try:
            with state_transaction(self.engine) as db:
                db.execute(delete(consumed_actions).where(consumed_actions.c.expires_at < now))
                db.execute(insert(consumed_actions).values(
                    nonce_hash=nonce_hash,
                    expires_at=expires_at,
                    consumed_at=now,
                ))
        except IntegrityError as exc:
            raise ToolError(
                "Thao tác đã được dùng; hãy mở một yêu cầu mới.",
                code="remote_action_replayed",
            ) from exc


def initialize_remote_action_ledger(settings: Settings) -> None:
    if settings.relational_state_url is not None:
        RelationalRemoteActionLedger.create_schema(
            state_engine(settings.relational_state_url.get_secret_value())
        )


def relational_remote_action_ledger(settings: Settings) -> RelationalRemoteActionLedger | None:
    if settings.relational_state_url is None:
        return None
    return RelationalRemoteActionLedger(
        state_engine(settings.relational_state_url.get_secret_value())
    )
