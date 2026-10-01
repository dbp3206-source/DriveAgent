"""Read-only local endpoint smoke check for an explicitly approved QA user.

The script never stores a credential or prints a secret.  It signs a short-lived
local session cookie using the configured APP_SECRET and requires the user ID to
be supplied at invocation time.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request

import itsdangerous

from app.core.config import Settings

BASE_URL = "http://127.0.0.1:8000"


def main() -> None:
    user_id = os.environ.get("DRIVE_AGENT_VERIFY_USER_ID")
    if not user_id:
        raise SystemExit(
            "Set DRIVE_AGENT_VERIFY_USER_ID to an approved local QA user "
            "before running this script."
        )
    secret = Settings().app_secret
    signer = itsdangerous.TimestampSigner(secret)
    cookie_payload = base64.b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
    cookie_value = signer.sign(cookie_payload).decode("utf-8")
    headers = {"Cookie": f"drive_agent_session={cookie_value}"}

    def get(path: str) -> dict:
        request = urllib.request.Request(f"{BASE_URL}{path}", headers=headers)
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    print("=== VERIFYING DRIVEAGENT READ-ONLY ENDPOINTS ===")
    health = get("/api/health")
    print(
        f"[OK] Health: status={health['status']}, db={health['database']}, "
        f"model={health['gemini_chat_model']}"
    )

    sessions = get("/api/chat/sessions?limit=5")
    print(f"[OK] Sessions limit=5: returned {len(sessions)} sessions")
    for item in sessions[:2]:
        print(f"     - {item['id']}: updated_at={item['updated_at']}")

    harness = get("/api/harness/overview")
    print(f"[OK] Harness overview: {len(harness['recent_runs'])} recent runs parsed cleanly")
    for run in harness["recent_runs"][:2]:
        print(
            f"     - msg={run['message_id']}, created_at={run['created_at']}, "
            f"score={run['output_quality']['score']}"
        )

    operations = get("/api/operations/status")
    print(
        f"[OK] Operations: {len(operations['items'])} items, "
        f"attention={operations['attention_count']}"
    )

    roles = get("/api/admin/roles")
    print(
        f"[OK] Roles: super_admin={len(roles.get('super_admin', []))} perms, "
        f"editor={len(roles.get('editor', []))} perms"
    )
    print(f"     - editor has drive:write: {'drive:write' in roles.get('editor', [])}")
    print("\nALL READ-ONLY VERIFICATIONS PASSED!")


if __name__ == "__main__":
    main()
