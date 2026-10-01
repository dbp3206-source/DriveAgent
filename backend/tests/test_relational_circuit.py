from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine

from app.services.relational_circuit import RelationalCircuitStore, metadata
from app.tools.contracts import ToolError


class Failure(Exception):
    code = 503


@pytest.fixture
def engine(tmp_path):
    value = create_engine(f"sqlite:///{tmp_path / 'circuit.db'}")
    metadata.create_all(value)
    yield value
    value.dispose()


def test_concurrent_failures_open_circuit_without_lost_updates(engine):
    circuit = RelationalCircuitStore(engine, "synthetic-secret")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: circuit.failure("generate", Failure(), now=100), range(4)))
    snapshot = circuit.snapshot(now=101)[0]
    assert snapshot["consecutive_failures"] == 4
    assert snapshot["circuit_open"]
    assert snapshot["retry_after_seconds"] == 29
    with pytest.raises(ToolError) as blocked:
        circuit.before_request("generate", now=101)
    assert blocked.value.code == "gemini_circuit_open"
    circuit.before_request("generate", now=131)
    circuit.success("generate", now=132)
    assert circuit.snapshot(now=132)[0]["consecutive_failures"] == 0


def test_key_and_capability_isolation_and_no_secret_persistence(engine, tmp_path):
    secret = "this-is-a-synthetic-secret-not-for-storage"
    first = RelationalCircuitStore(engine, secret)
    second = RelationalCircuitStore(engine, "another-synthetic-secret")
    error = Failure()
    error.code = 429
    assert first.failure("web_grounding", error, now=100) == "quota"
    first.before_request("generate", now=101)
    second.before_request("web_grounding", now=101)
    with pytest.raises(ToolError):
        first.before_request("web_grounding", now=101)
    assert secret.encode() not in (tmp_path / "circuit.db").read_bytes()


def test_authentication_error_is_not_false_quota_cooldown(engine):
    circuit = RelationalCircuitStore(engine, "synthetic-secret")
    error = Failure()
    error.code = 401
    assert circuit.failure("generate", error, now=100) == "authentication"
    assert not circuit.snapshot(now=101)[0]["circuit_open"]
