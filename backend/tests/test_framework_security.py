from types import SimpleNamespace
from unittest.mock import MagicMock

from app.db.framework_security import LEGACY_ADK_TABLES, protect_legacy_framework_tables


def connection(*, dialect="postgresql", marker=True, roles=True):
    db = MagicMock()
    db.dialect = SimpleNamespace(name=dialect)

    def execute(sql):
        value = None
        if "to_regclass" in sql:
            value = "table" if marker else None
        elif "pg_roles" in sql:
            value = 1 if roles else None
        return SimpleNamespace(scalar_one_or_none=lambda: value)

    db.exec_driver_sql.side_effect = execute
    return db


def test_local_sqlite_is_not_touched():
    db = connection(dialect="sqlite")
    protect_legacy_framework_tables(db)
    db.exec_driver_sql.assert_not_called()


def test_no_adk_marker_means_no_unrelated_public_table_changes():
    db = connection(marker=False)
    protect_legacy_framework_tables(db)
    assert db.exec_driver_sql.call_count == 1


def test_all_legacy_tables_are_protected_without_deleting_or_moving_rows():
    db = connection()
    protect_legacy_framework_tables(db)
    commands = [call.args[0] for call in db.exec_driver_sql.call_args_list]
    for table in LEGACY_ADK_TABLES:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in commands
        for role in ("PUBLIC", "anon", "authenticated"):
            assert f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM {role}" in commands
    assert not any("DROP " in sql or "DELETE " in sql or "SET SCHEMA" in sql for sql in commands)
    assert not any("FROM postgres" in sql or "FROM service_role" in sql for sql in commands)


def test_non_supabase_postgres_does_not_reference_missing_api_roles():
    db = connection(roles=False)
    protect_legacy_framework_tables(db)
    commands = [call.args[0] for call in db.exec_driver_sql.call_args_list]
    assert any("FROM PUBLIC" in sql for sql in commands)
    assert not any("FROM anon" in sql or "FROM authenticated" in sql for sql in commands)
