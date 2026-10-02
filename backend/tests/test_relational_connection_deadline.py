from unittest.mock import MagicMock

import pytest

from app.db.session import database_engine_options
from app.services import relational_state


def test_async_database_keeps_private_schema_and_network_deadline():
    options = database_engine_options("postgresql+psycopg://test.invalid/qa")
    assert options["connect_args"]["connect_timeout"] == 10
    assert options["pool_timeout"] == 10
    assert options["pool_size"] == 2 and options["max_overflow"] == 0
    assert options["execution_options"] == {"schema_translate_map": {None: "veridra_private"}}
    assert database_engine_options("sqlite+aiosqlite:///qa.db") == {"future": True}


@pytest.mark.parametrize(
    "url", ["postgresql://test.invalid/qa", "postgresql+psycopg://test.invalid/qa"]
)
def test_postgres_connection_has_network_deadline(monkeypatch, url):
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.execution_options.return_value = engine
    create = MagicMock(return_value=engine)
    monkeypatch.setattr(relational_state, "create_engine", create)
    relational_state.state_engine.cache_clear()
    try:
        assert relational_state.state_engine(url) is engine
        options = create.call_args.kwargs
        assert options["connect_args"]["connect_timeout"] == 10
        assert options["pool_timeout"] == 10
        assert options["pool_size"] == 2 and options["max_overflow"] == 0
        engine.execution_options.assert_called_once_with(
            schema_translate_map={None: "veridra_private"}
        )
    finally:
        relational_state._engines.discard(engine)
        relational_state.state_engine.cache_clear()
