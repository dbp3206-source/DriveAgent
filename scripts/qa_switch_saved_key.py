"""Activate one already validated saved local key for authorized benchmarking.

Does not create/reset a key or quota ledger. Only safe metadata is written.
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from evaluate_gate2_live import _session_cookie
from qa_google_read_smoke import _connected_owner_id

BASE = "http://127.0.0.1:8000/api/settings/providers/gemini"


def main() -> int:
    cookie = _session_cookie(_connected_owner_id())

    def request(path, method="GET"):
        req = Request(BASE + path, method=method, headers={
            "Cookie": f"drive_agent_session={cookie}",
            "X-Requested-With": "XMLHttpRequest", "Origin": "http://localhost:8000",
        })
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read())

    before = request("/credentials")
    candidates = [item for item in before if not item["is_active"]
                  and item["status"] == "ready" and item["last_validated_at"]
                  and item["daily_flash_used"] < 13 and not item["circuit_open"]
                  and not item["retry_after_seconds"]]
    if not candidates:
        print(json.dumps({"status": "no_validated_available_key", "passed": False}))
        return 1
    chosen = min(candidates, key=lambda item: item["daily_flash_used"])
    started = time.perf_counter()
    activated = request(f"/credentials/{chosen['id']}/activate", "POST")
    elapsed = time.perf_counter() - started
    after = request("/credentials")
    selected = next(item for item in after if item["id"] == chosen["id"])
    unchanged = ({item["id"]: item["daily_flash_used"] for item in before}
                 == {item["id"]: item["daily_flash_used"] for item in after})
    passed = activated["is_active"] and selected["is_active"] and unchanged and elapsed < 3
    report = {"run_at": datetime.now(UTC).isoformat(), "passed": passed,
              "activation_seconds": round(elapsed, 3), "ledger_unchanged": unchanged,
              "selected_used_before": chosen["daily_flash_used"],
              "selected_used_after": selected["daily_flash_used"],
              "scope": "one_local_validated_key_switch_not_cloud_or_google_quota_balance"}
    folder = Path(__file__).resolve().parents[1] / "design-work/qa/RELEASE-20261002"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"saved-key-switch-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({**report, "report": path.name}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
