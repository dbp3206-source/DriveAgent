from app.services.durable_evaluation import EvaluationQueue, execute_one


def test_checkpoint_resume_owner_isolation_and_retry_limit(tmp_path):
    queue = EvaluationQueue(tmp_path)
    job_id = queue.enqueue("owner", 1)
    assert queue.get("other", job_id) is None
    claimed = queue.claim(2)
    assert claimed["id"] == job_id
    queue.checkpoint(job_id, {"routing": {"pass_rate": 1}}, 3, attempt=claimed["attempts"])
    assert queue.claim(4) is None
    recovered = EvaluationQueue(tmp_path).claim(124)
    assert recovered["checkpoint"] == '{"routing": {"pass_rate": 1}}'
    queue.claim(245)
    assert queue.claim(366) is None
    assert queue.get("owner", job_id)["status"] == "failed"


def test_evaluation_worker_completes_without_model_or_cloud_calls(tmp_path):
    queue = EvaluationQueue(tmp_path)
    job_id = queue.enqueue("owner", 1)
    assert execute_one(queue, 2)
    result = queue.get("owner", job_id)
    assert result["status"] == "completed"
    assert len(result["checkpoint"]) == 4
    assert all(row["pass_rate"] == 1 for row in result["checkpoint"].values())
