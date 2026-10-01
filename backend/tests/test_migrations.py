from sqlalchemy import create_engine

from app.db.migrations import apply_sqlite_migrations


def test_message_lifecycle_migration_upgrades_existing_database_once(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE messages (id VARCHAR(36) PRIMARY KEY, content TEXT NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO messages(id, content) VALUES ('legacy', 'Nội dung cũ')"
        )
        apply_sqlite_migrations(connection)
        apply_sqlite_migrations(connection)

        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(messages)")}
        row = connection.exec_driver_sql(
            "SELECT content, status, request_id FROM messages WHERE id='legacy'"
        ).one()
        versions = connection.exec_driver_sql("SELECT version FROM schema_migrations").all()
        company_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(company_profiles)")
        }
        scheduled_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(scheduled_jobs)")
        }

    assert {"status", "request_id"}.issubset(columns)
    assert tuple(row) == ("Nội dung cũ", "completed", None)
    assert {"user_id", "domain", "source_url", "last_verified_at"}.issubset(company_columns)
    assert {"user_id", "kind", "dedupe_key", "lease_token"}.issubset(scheduled_columns)
    assert versions == [(1,), (2,), (3,), (4,), (5,)]
    engine.dispose()
