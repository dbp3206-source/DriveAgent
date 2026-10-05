from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.db.framework_sessions import (
    _private_transaction,
    framework_engine_options,
    protect_framework_engine,
)


def test_local_session_options_and_events_are_unchanged():
    assert framework_engine_options("sqlite+aiosqlite:///local.db") == {}
    engine = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    with patch("app.db.framework_sessions.event.listen") as listen:
        protect_framework_engine(engine)
    listen.assert_not_called()


def test_cloud_session_connections_are_bounded_and_explicitly_private():
    options = framework_engine_options("postgresql+psycopg://user@localhost/veridra_ci")
    assert options["pool_size"] == 2
    assert options["max_overflow"] == 0
    assert options["connect_args"] == {"connect_timeout": 10}
    assert options["execution_options"] == {"schema_translate_map": {None: "veridra_private"}}
    sync_engine = object()
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), sync_engine=sync_engine)
    with patch("app.db.framework_sessions.event.listen") as listen:
        protect_framework_engine(engine)
    listen.assert_called_once_with(sync_engine, "begin", _private_transaction)


def test_every_transaction_selects_private_schema_without_moving_data():
    connection = MagicMock()
    _private_transaction(connection)
    connection.exec_driver_sql.assert_called_once_with(
        "SET LOCAL search_path TO veridra_private"
    )
