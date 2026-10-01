"""Exercise the actual offline-evaluation API/worker without provider calls."""

import json
import sqlite3
import time
from pathlib import Path
from urllib.request import Request, urlopen

from qa_google_read_smoke import BASE, ROOT, _cookie


def reservation_count():
    path = ROOT / "data/quota.db"
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
        return db.execute("SELECT count(*) FROM quota_reservations").fetchone()[0]


def main():
    cookie = _cookie()
    before = reservation_count()

    def request(path, *, create=False):
        req = Request(BASE + path, data=b"{}" if create else None, headers={
            "Cookie": "drive_agent_session=" + cookie,
            "Content-Type": "application/json",
            "Origin": "http://localhost:8000",
        })
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read()), response.headers.get("Cache-Control")

    created, cache = request("/api/evaluation-jobs", create=True)
    deadline = time.monotonic() + 60
    states = []
    while True:
        job, _ = request("/api/evaluation-jobs/" + created["job_id"])
        if not states or states[-1] != job["status"]:
            states.append(job["status"])
        if job["status"] not in {"queued", "running"}:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Actual evaluation worker did not finish within 60 seconds")
        time.sleep(1)
    evidence = {
        "scope": created["scope"], "status": job["status"], "observed_states": states,
        "attempts": job["attempts"], "cache_control": cache,
        "suite_counts": {name: {key: row.get(key) for key in ("passed", "total", "pass_rate")}
                         for name, row in job["checkpoint"].items()},
        "quota_reservations_delta": reservation_count() - before,
        "cloud_postgres_verified": False,
    }
    output = Path(ROOT) / "design-work/qa/evaluation-queue-live-20260930.json"
    output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence))
    assert evidence["status"] == "completed"
    assert evidence["scope"] == "offline_regression"
    assert evidence["quota_reservations_delta"] == 0
    assert set(evidence["suite_counts"]) == {"routing", "output", "contract", "mutation"}
    assert all(row["pass_rate"] == 1 for row in evidence["suite_counts"].values())


if __name__ == "__main__":
    main()
