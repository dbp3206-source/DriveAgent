"""User-authorized manual key switch, preserving each credential's local ledger."""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from qa_google_read_smoke import _cookie

root = Path(__file__).resolve().parents[1]
cookie = _cookie()
base = "http://127.0.0.1:8000/api/settings/providers/gemini"


def api(path, method="GET"):
    request = Request(
        base + path,
        method=method,
        data=b"{}" if method == "POST" else None,
        headers={
            "Cookie": "drive_agent_session=" + cookie,
            "Origin": "http://127.0.0.1:8000",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read())


parser = argparse.ArgumentParser()
parser.add_argument("--roundtrip", action="store_true")
roundtrip = parser.parse_args().roundtrip
before = api("/status")
available = [
    row
    for row in api("/credentials")
    if not row["is_active"]
    and row["status"] == "ready"
    and (roundtrip or not row["circuit_open"])
    and (roundtrip or row["daily_flash_used"] < 13)
]
if not available:
    print(json.dumps({"status": "no_saved_key_with_conservative_headroom"}))
    sys.exit(2)
select_key = max if roundtrip else min
selected = select_key(available, key=lambda row: row["daily_flash_used"])
started = time.perf_counter()
api("/credentials/" + selected["id"] + "/activate", "POST")
after = api("/status")
selected_after = next(row for row in api("/credentials") if row["id"] == selected["id"])
report = {
    "status": "switched",
    "seconds": round(time.perf_counter() - started, 3),
    "display_name": after["display_name"],
    "local_budget": after["local_budget"],
    "old_local_budget": before["local_budget"],
    "active_key_matches_selected": after["active_credential_id"] == selected["id"],
    "effective_key_matches_selected": after["effective_credential_id"]
    == selected["id"],
    "ledger_preserved": selected_after["daily_flash_used"]
    == selected["daily_flash_used"],
    "selected_key_daily_used": selected_after["daily_flash_used"],
    "failover_active": after["failover_active"],
    "provider_balance_available": after["provider_balance_available"],
}
if roundtrip:
    api("/credentials/" + before["active_credential_id"] + "/activate", "POST")
    restored = api("/status")
    report["restored_original_key"] = (
        restored["active_credential_id"] == before["active_credential_id"]
    )
    report["original_ledger_preserved"] = (
        restored["local_budget"] == before["local_budget"]
    )
    report["model_calls"] = 0
(root / "design-work/qa/key-switch-docker-20260930.json").write_text(
    json.dumps(report, indent=2)
)
print(json.dumps(report, indent=2))
