"""Small, versioned SQLite migrations for the local production database.

``create_all`` creates a fresh schema but never upgrades an existing laptop.  The
project deliberately keeps migrations dependency-free; every migration is
idempotent, recorded, and executed inside the startup transaction.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, MetaData, Table, insert, select
from sqlalchemy.engine import Connection

Migration = Callable[[Connection], None]

postgres_metadata = MetaData()
postgres_schema_migrations = Table(
    "schema_migrations",
    postgres_metadata,
    Column("version", Integer, primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False),
)


def _columns(connection: Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}


def _message_lifecycle(connection: Connection) -> None:
    columns = _columns(connection, "messages")
    if "status" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE messages ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'completed'"
        )
    if "request_id" not in columns:
        connection.exec_driver_sql("ALTER TABLE messages ADD COLUMN request_id VARCHAR(64)")
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_messages_request_id ON messages(request_id)"
    )


def _company_profiles(connection: Connection) -> None:
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS company_profiles ("
        "id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL, "
        "name VARCHAR(240) NOT NULL, normalized_name VARCHAR(240) NOT NULL, "
        "domain VARCHAR(253) NOT NULL, industry VARCHAR(240), "
        "products_json TEXT NOT NULL DEFAULT '[]', contacts_json TEXT NOT NULL DEFAULT '[]', "
        "notes TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL, "
        "source_kind VARCHAR(32) NOT NULL DEFAULT 'official', "
        "last_verified_at DATETIME NOT NULL, created_at DATETIME NOT NULL, "
        "updated_at DATETIME NOT NULL, "
        "FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)"
    )


def _enable_existing_provider_failover(connection: Connection) -> None:
    """Adopt the documented zero-downtime BYOK policy for existing local keys.

    The switch remains user-controllable in Settings after this one-time
    migration. New credentials default to enabled at the model/API boundary.
    """

    if "provider_credentials" not in {
        str(row[0])
        for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }:
        return
    columns = _columns(connection, "provider_credentials")
    if "failover_enabled" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE provider_credentials ADD COLUMN failover_enabled "
            "BOOLEAN NOT NULL DEFAULT 1"
        )
    connection.exec_driver_sql(
        "UPDATE provider_credentials SET failover_enabled = 1 "
        "WHERE provider = 'gemini'"
    )
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_company_user_domain "
        "ON company_profiles(user_id, domain)"
    )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_company_user_name "
        "ON company_profiles(user_id, normalized_name)"
    )


def _pdf_ingestion_jobs(connection: Connection) -> None:
    from app.db.models import PdfIngestionJob

    PdfIngestionJob.__table__.create(connection, checkfirst=True)


def _scheduled_jobs(connection: Connection) -> None:
    from app.db.models import ScheduledJob

    ScheduledJob.__table__.create(connection, checkfirst=True)


def _chat_tasks(connection: Connection) -> None:
    from app.db.models import ChatTask

    ChatTask.__table__.create(connection, checkfirst=True)


MIGRATIONS: tuple[tuple[int, Migration], ...] = (
    (1, _message_lifecycle),
    (2, _company_profiles),
    (3, _enable_existing_provider_failover),
    (4, _pdf_ingestion_jobs),
    (5, _scheduled_jobs),
    (6, _chat_tasks),
)


def apply_sqlite_migrations(connection: Connection) -> None:
    """Apply each not-yet-recorded migration exactly once."""

    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {
        int(row[0])
        for row in connection.exec_driver_sql("SELECT version FROM schema_migrations")
    }
    for version, migration in MIGRATIONS:
        if version in applied:
            continue
        migration(connection)
        connection.exec_driver_sql(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, datetime.now(UTC).isoformat()),
        )


def apply_postgres_migrations(connection: Connection) -> None:
    """Record the clean PostgreSQL baseline for forward-only cloud upgrades.

    The initial cloud schema is created from the current ORM metadata. Future
    schema changes append explicit migrations here instead of relying on
    ``create_all`` to alter existing projects.
    """

    postgres_schema_migrations.create(connection, checkfirst=True)
    applied = set(connection.execute(select(postgres_schema_migrations.c.version)).scalars())
    from app.db.framework_security import protect_legacy_framework_tables
    from app.services.pgvector import migrate_pgvector

    migrations: tuple[tuple[int, Migration], ...] = (
        (1, lambda _connection: None), (2, _scheduled_jobs), (3, _chat_tasks),
        (4, migrate_pgvector), (5, protect_legacy_framework_tables),
    )
    for version, migration in migrations:
        if version in applied:
            continue
        migration(connection)
        connection.execute(
            insert(postgres_schema_migrations).values(
                version=version, applied_at=datetime.now(UTC)
            )
        )
