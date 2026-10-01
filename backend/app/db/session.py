"""Khởi tạo SQLAlchemy async và cung cấp session cho FastAPI."""

from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.migrations import apply_postgres_migrations, apply_sqlite_migrations
from app.db.models import Base

settings = get_settings()
engine_options: dict = {"future": True}
if settings.resolved_database_url.startswith("postgresql+psycopg"):
    engine_options.update(pool_size=2, max_overflow=0, pool_timeout=10, pool_pre_ping=True)
    engine_options["execution_options"] = {
        "schema_translate_map": {None: "veridra_private"}
    }
engine = create_async_engine(settings.resolved_database_url, **engine_options)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(engine.sync_engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    """SQLite tắt foreign key mặc định, nên bật để user isolation không bị dữ liệu mồ côi."""

    if settings.resolved_database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


async def init_database() -> None:
    async with engine.begin() as connection:
        if settings.resolved_database_url.startswith("postgresql+psycopg"):
            # Raw DDL intentionally precedes schema translation. All ORM tables
            # are then created in the non-PostgREST private namespace.
            await connection.execute(text("CREATE SCHEMA IF NOT EXISTS veridra_private"))
            await connection.execute(text("REVOKE ALL ON SCHEMA veridra_private FROM PUBLIC"))
            for role in ("anon", "authenticated"):
                exists = await connection.scalar(
                    text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}
                )
                if exists:
                    await connection.execute(
                        text(f"REVOKE ALL ON SCHEMA veridra_private FROM {role}")
                    )
        await connection.run_sync(Base.metadata.create_all)
        if settings.resolved_database_url.startswith("sqlite"):
            await connection.run_sync(apply_sqlite_migrations)
        else:
            await connection.run_sync(apply_postgres_migrations)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
