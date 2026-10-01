from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine

from app.services.durable_evaluation import EvaluationQueue, LeaseLostError, execute_one
from app.services.relational_evaluation import RelationalEvaluationQueue


@pytest.fixture(params=["local", "relational"])
def queue(request, tmp_path):
    if request.param == "local":
        yield EvaluationQueue(tmp_path)
        return
    engine = create_engine(f"sqlite:///{tmp_path / 'queue.db'}")
    RelationalEvaluationQueue.create_schema(engine)
    yield RelationalEvaluationQueue(engine)
    engine.dispose()


def test_owner_limit_and_parallel_claim(queue):
    first = queue.enqueue("alice", 1)
    second = queue.enqueue("alice", 2)
    with pytest.raises(ValueError, match="At most two"):
        queue.enqueue("alice", 3)
    assert queue.get("bob", first) is None
    assert len(queue.recent("alice")) == 2
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: queue.claim(4), range(4)))
    claimed = [row for row in claims if row is not None]
    assert {row["id"] for row in claimed} == {first, second}
    assert len(claimed) == 2
    assert all(row["attempts"] == 1 for row in claimed)


def test_recovery_fences_obsolete_worker_and_keeps_checkpoint(queue):
    job_id = queue.enqueue("alice", 1)
    first = queue.claim(2)
    queue.checkpoint(job_id, {"routing": {"pass_rate": 1}}, 3, attempt=first["attempts"])
    second = queue.claim(124)
    assert second["attempts"] == 2
    assert "routing" in second["checkpoint"]
    with pytest.raises(LeaseLostError):
        queue.checkpoint(job_id, {"wrong": True}, 125, attempt=first["attempts"])
    with pytest.raises(LeaseLostError):
        queue.finish(job_id, "completed", now=125, attempt=first["attempts"])
    assert queue.get("alice", job_id)["checkpoint"] == {"routing": {"pass_rate": 1}}
    queue.finish(job_id, "completed", now=126, attempt=second["attempts"])
    with pytest.raises(LeaseLostError):
        queue.checkpoint(job_id, {"wrong": True}, 127, attempt=second["attempts"])


def test_expired_lease_rejects_publish_even_before_reclaim(queue):
    job_id = queue.enqueue("alice", 1)
    claim = queue.claim(2)
    with pytest.raises(LeaseLostError):
        queue.finish(job_id, "completed", now=123, attempt=claim["attempts"])
    assert queue.get("alice", job_id)["status"] == "running"
    assert queue.claim(123)["attempts"] == 2
    assert queue.claim(244)["attempts"] == 3
    assert queue.claim(365) is None
    assert queue.get("alice", job_id)["status"] == "failed"


def test_real_regression_executor_uses_queue_contract(queue):
    job_id = queue.enqueue("alice", 1)
    assert execute_one(queue, 2)
    result = queue.get("alice", job_id)
    assert result["status"] == "completed"
    assert set(result["checkpoint"]) == {"routing", "output", "contract", "mutation"}


def test_reopen_relational_queue_preserves_checkpoint(tmp_path):
    url = f"sqlite:///{tmp_path / 'persist.db'}"
    engine = create_engine(url)
    RelationalEvaluationQueue.create_schema(engine)
    queue = RelationalEvaluationQueue(engine)
    job_id = queue.enqueue("alice", 1)
    claim = queue.claim(2)
    queue.checkpoint(job_id, {"routing": {"pass_rate": 1}}, 3, attempt=claim["attempts"])
    engine.dispose()
    reopened = create_engine(url)
    try:
        recovered = RelationalEvaluationQueue(reopened).claim(124)
        assert recovered["attempts"] == 2
        assert "routing" in recovered["checkpoint"]
    finally:
        reopened.dispose()
