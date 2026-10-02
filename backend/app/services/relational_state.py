"""Bounded connection pools shared by relational state adapters, never by users' keys."""

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_engines: set[Engine] = set()


@lru_cache(maxsize=4)
def state_engine(url: str) -> Engine:
    options = {"pool_size": 2, "max_overflow": 0, "pool_timeout": 10}
    if url.startswith(("postgresql:", "postgresql+psycopg:")):
        # A pool timeout does not bound opening a TCP connection. Keep a lost
        # database from leaving startup or a worker blocked indefinitely.
        options["connect_args"] = {"connect_timeout": 10}
    if url.startswith("sqlite:"):
        options = {}
    engine = create_engine(url, pool_pre_ping=True, **options)
    if engine.dialect.name == "postgresql":
        # Supabase exposes public by default. Product state must never be created
        # there merely because an adapter omitted an explicit schema.
        engine = engine.execution_options(schema_translate_map={None: "veridra_private"})
    _engines.add(engine)
    return engine


def prepare_state_schema(engine: Engine) -> None:
    """Bootstrap our private namespace without granting any new public access."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as db:
        db.execute(text("CREATE SCHEMA IF NOT EXISTS veridra_private"))
        db.execute(text("REVOKE ALL ON SCHEMA veridra_private FROM PUBLIC"))
        for role in ("anon", "authenticated"):
            exists = db.execute(text("SELECT 1 FROM pg_roles WHERE rolname=:role"),
                                {"role": role}).scalar_one_or_none()
            if exists:
                # Names are a closed constant set, never input from a request.
                db.execute(text(f"REVOKE ALL ON SCHEMA veridra_private FROM {role}"))


def close_state_engines() -> None:
    for engine in list(_engines):
        engine.dispose()
    _engines.clear()
    state_engine.cache_clear()


@contextmanager
def state_transaction(engine: Engine):
    """SQLite serializes writes; PostgreSQL adapters use row/advisory locks."""
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
