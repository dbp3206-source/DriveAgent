from sqlalchemy import create_engine

from app.db.migrations import apply_sqlite_migrations


def test_message_lifecycle_migration_upgrades_existing_database_once(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO users(id) VALUES ('legacy-user')")
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
        assert connection.exec_driver_sql(
            "SELECT auth_version FROM users WHERE id='legacy-user'"
        ).scalar_one() == ""
        company_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(company_profiles)")
        }
        scheduled_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(scheduled_jobs)")
        }
        user_schedule_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(users)")
        }
        schedule_defaults = connection.exec_driver_sql(
            "SELECT scheduled_morning_enabled, scheduled_pre_meeting_enabled "
            "FROM users WHERE id='legacy-user'"
        ).one()

    assert {"status", "request_id"}.issubset(columns)
    assert tuple(row) == ("Nội dung cũ", "completed", None)
    assert {"user_id", "domain", "source_url", "last_verified_at"}.issubset(company_columns)
    assert {"user_id", "kind", "dedupe_key", "lease_token"}.issubset(scheduled_columns)
    assert {"scheduled_morning_enabled", "scheduled_pre_meeting_enabled"}.issubset(
        user_schedule_columns
    )
    assert tuple(schedule_defaults) == (0, 0)
    assert versions == [(index,) for index in range(1, 12)]
    engine.dispose()


def test_automatic_cleanup_migration_upgrades_existing_queue_without_rewriting_jobs(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cleanup-legacy.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE cleanup_jobs (id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36), "
            "approval_id VARCHAR(36), plan_hash VARCHAR(64), plan_json TEXT, "
            "remaining_json TEXT, completed_json TEXT, status VARCHAR(24), attempts INTEGER, "
            "lease_token VARCHAR(36), lease_until FLOAT, critical_started_at DATETIME, "
            "sql_completed_at DATETIME, error_code VARCHAR(64), created_at DATETIME, "
            "updated_at DATETIME)"
        )
        connection.exec_driver_sql(
            "INSERT INTO cleanup_jobs (id, status) VALUES ('legacy-job', 'queued')"
        )
        connection.exec_driver_sql(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO schema_migrations(version, applied_at) "
            "SELECT value, 'legacy' FROM (SELECT 1 AS value UNION ALL SELECT 2 UNION ALL "
            "SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL "
            "SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10)"
        )
        apply_sqlite_migrations(connection)
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(cleanup_jobs)")}
        automatic, status = connection.exec_driver_sql(
            "SELECT automatic, status FROM cleanup_jobs WHERE id='legacy-job'"
        ).one()

    assert "automatic" in columns
    assert (automatic, status) == (0, "queued")
    engine.dispose()
