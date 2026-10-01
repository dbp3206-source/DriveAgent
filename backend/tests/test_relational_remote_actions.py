from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine

from app.services.relational_remote_actions import RelationalRemoteActionLedger
from app.tools.contracts import ToolError


def test_remote_action_nonce_is_consumed_once_across_workers(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'remote-actions.db'}")
    RelationalRemoteActionLedger.create_schema(engine)
    ledger = RelationalRemoteActionLedger(engine)

    def consume(_):
        try:
            ledger.consume("a" * 32, 2_000_000_000)
            return "consumed"
        except ToolError as exc:
            return exc.code

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(consume, range(8)))
        assert results.count("consumed") == 1
        assert results.count("remote_action_replayed") == 7
    finally:
        engine.dispose()
