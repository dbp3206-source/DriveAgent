"""Durable SQLite queue for side-effect-free offline evaluation, not chat replay."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from time import monotonic, time
from uuid import uuid4


class LeaseLostError(ValueError):
    """A replaced or expired worker must not publish progress or completion."""


class EvaluationQueue:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "evaluation_jobs.db"
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, status TEXT NOT NULL,
                checkpoint TEXT NOT NULL DEFAULT '{}', attempts INTEGER NOT NULL DEFAULT 0,
                lease_until REAL, created_at REAL NOT NULL)""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, owner: str, now: float) -> str:
        job_id = str(uuid4())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "DELETE FROM jobs WHERE status NOT IN ('queued','running') AND created_at<?",
                (now - 30 * 86400,),
            )
            count = db.execute(
                "SELECT count(*) FROM jobs WHERE owner=? AND status IN ('queued','running')",
                (owner,),
            ).fetchone()[0]
            if count >= 2:
                raise ValueError("At most two pending evaluation jobs per user")
            db.execute(
                "INSERT INTO jobs(id,owner,status,created_at) VALUES(?,?,?,?)",
                (job_id, owner, "queued", now),
            )
        return job_id

    def get(self, owner: str, job_id: str):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE id=? AND owner=?", (job_id, owner)
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data.pop("owner")
        data["checkpoint"] = json.loads(data["checkpoint"])
        return data

    def recent(self, owner: str):
        with self.connect() as db:
            rows = db.execute(
                "SELECT id FROM jobs WHERE owner=? ORDER BY created_at DESC LIMIT 10", (owner,)
            ).fetchall()
        return [self.get(owner, row["id"]) for row in rows]

    def claim(self, now: float):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE jobs SET status='failed' WHERE status='running' "
                "AND lease_until<? AND attempts>=3",
                (now,),
            )
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' OR "
                "(status='running' AND lease_until<? AND attempts<3) "
                "ORDER BY created_at LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE jobs SET status='running',attempts=attempts+1,lease_until=? WHERE id=?",
                (now + 120, row["id"]),
            )
            claimed = dict(row)
            claimed.update(status="running", attempts=row["attempts"] + 1, lease_until=now + 120)
            return claimed

    def checkpoint(self, job_id: str, result: dict, now: float, *, attempt: int):
        with self.connect() as db:
            changed = db.execute(
                "UPDATE jobs SET checkpoint=?,lease_until=? WHERE id=? "
                "AND status='running' AND attempts=? AND lease_until>?",
                (json.dumps(result), now + 120, job_id, attempt, now),
            ).rowcount
            if changed != 1:
                raise LeaseLostError("Evaluation worker no longer owns the lease")

    def finish(self, job_id: str, status: str, *, attempt: int, now: float):
        if status not in {"completed", "quality_failed", "failed"}:
            raise ValueError("Invalid terminal evaluation state")
        with self.connect() as db:
            changed = db.execute(
                "UPDATE jobs SET status=?,lease_until=NULL WHERE id=? "
                "AND status='running' AND attempts=? AND lease_until>?",
                (status, job_id, attempt, now),
            ).rowcount
            if changed != 1:
                raise LeaseLostError("Evaluation worker no longer owns the lease")


def execute_one(queue: EvaluationQueue, now: float) -> bool:
    from app.services.evaluation import (
        run_adversarial_mutation_regression,
        run_answer_contract_benchmark,
        run_output_quality_regression,
        run_routing_regression,
    )

    started = monotonic()
    job = queue.claim(now)
    if not job:
        return False
    functions = {
        "routing": run_routing_regression,
        "output": run_output_quality_regression,
        "contract": run_answer_contract_benchmark,
        "mutation": run_adversarial_mutation_regression,
    }
    results = json.loads(job["checkpoint"])
    try:
        for step, function in functions.items():
            if step not in results:
                result = function()
                results[step] = {
                    key: result[key] for key in ("passed", "total", "pass_rate") if key in result
                }
                queue.checkpoint(
                    job["id"], results, now + monotonic() - started, attempt=job["attempts"]
                )
        queue.finish(
            job["id"],
            "completed"
            if all(row.get("pass_rate") == 1 for row in results.values())
            else "quality_failed",
            attempt=job["attempts"],
            now=now + monotonic() - started,
        )
    except Exception:
        # Lease expiry recovers from the last checkpoint, max three attempts.
        return True
    return True


async def worker(root: Path, *, queue=None):
    import asyncio

    queue = queue if queue is not None else EvaluationQueue(root)
    while True:
        try:
            await asyncio.to_thread(execute_one, queue, time())
        except Exception:
            # A transient SQLite/IO failure must not permanently kill the worker.
            # Keep diagnostics metadata-only: no owner, source data or exception body.
            logging.getLogger(__name__).warning("Offline evaluation worker will retry")
        await asyncio.sleep(2)
