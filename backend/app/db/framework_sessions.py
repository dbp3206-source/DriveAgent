"""Keep ADK persistence private even when a pooler ignores startup options."""

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine


def framework_engine_options(url: str) -> dict:
    if not url.startswith("postgresql+psycopg"):
        return {}
    return {
        "pool_size": 2,
        "max_overflow": 0,
        "pool_timeout": 10,
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 10},
        "execution_options": {"schema_translate_map": {None: "veridra_private"}},
    }


def _private_transaction(connection: Connection) -> None:
    # The SDK also inspects tables and reads its version with raw SQL. Schema
    # translation alone cannot cover those reads. SET LOCAL applies to each
    # transaction, unlike startup URL options that some poolers ignore.
    connection.exec_driver_sql("SET LOCAL search_path TO veridra_private")


def protect_framework_engine(engine: AsyncEngine) -> None:
    if engine.dialect.name == "postgresql":
        event.listen(engine.sync_engine, "begin", _private_transaction)
