"""Real isolated container gate, no personal data, Gemini calls or cloud writes."""

import argparse
import json
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "veridra-packaging-qa"
VOLUME = "veridra-packaging-qa-state"
BASE = "http://127.0.0.1:8010"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker", required=True)
    parser.add_argument("--image", default="veridra:qa-20260930")
    args = parser.parse_args()

    def docker(*parts):
        return subprocess.check_output([args.docker, *parts], text=True).strip()

    existing = docker(
        "ps", "-a", "--filter", f"name=^{NAME}$", "--format", "{{.Names}}"
    )
    if existing:
        raise SystemExit(
            "Existing QA container preserved; remove/reuse explicitly, not overwritten"
        )
    docker("volume", "create", VOLUME)
    secret = secrets.token_hex(32)
    options = [
        "--name",
        NAME,
        "--publish",
        "127.0.0.1:8010:8000",
        "--memory",
        "1g",
        "--env",
        "DRIVE_AGENT_STATE_DIR=/app/data",
        "--env",
        "DRIVE_AGENT_DATABASE_URL=sqlite+aiosqlite:////app/data/drive_agent.db",
        "--env",
        "DRIVE_AGENT_QDRANT_PATH=/app/data/qdrant",
        "--env",
        f"DRIVE_AGENT_APP_SECRET={secret}",
        "--env",
        "DRIVE_AGENT_PUBLIC_BASE_URL=http://localhost:8010",
        "--env",
        "DRIVE_AGENT_FRONTEND_ORIGIN=http://localhost:8010",
        "--env",
        "DRIVE_AGENT_ENABLE_DEMO_LOGIN=false",
        "--env",
        "DRIVE_AGENT_CONTAINER_LOCAL_GATEWAY=172.17.0.1",
        "--mount",
        f"type=volume,source={VOLUME},target=/app/data",
    ]

    def start():
        docker("run", "--detach", *options, args.image)
        for _ in range(120):
            try:
                with urllib.request.urlopen(
                    BASE + "/api/health", timeout=2
                ) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.5)
        raise RuntimeError("Container health did not become ready")

    start()
    script = """
import asyncio,json
from app.db.session import SessionFactory
from app.db.models import User
from sqlalchemy import select
from app.core.config import get_settings
from itsdangerous import TimestampSigner
async def create():
 async with SessionFactory() as db:
  users=[]
  for email,name in [('qa-a@veridra.invalid','QA A'),('qa-b@veridra.invalid','QA B')]:
   user=await db.scalar(select(User).where(User.email==email))
   if user is None:
    user=User(email=email,display_name=name,role='editor');db.add(user)
   users.append(user)
  await db.commit()
  return [u.id for u in users]
print(json.dumps(asyncio.run(create())))
"""
    owners = json.loads(docker("exec", NAME, "python", "-c", script))
    # Starlette SessionMiddleware signed JSON session, identical to the application.
    from base64 import b64encode

    from itsdangerous import TimestampSigner

    cookies = [
        TimestampSigner(secret)
        .sign(b64encode(json.dumps({"user_id": user}).encode()))
        .decode()
        for user in owners
    ]

    def api(path, cookie=None, method="GET"):
        headers = {
            "Origin": "http://localhost:8010",
            "Content-Type": "application/json",
        }
        if cookie:
            headers["Cookie"] = "drive_agent_session=" + cookie
        req = urllib.request.Request(
            BASE + path,
            headers=headers,
            method=method,
            data=b"{}" if method == "POST" else None,
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return (
                    response.status,
                    json.loads(response.read()),
                    {key.lower(): value for key, value in response.headers.items()},
                )
        except urllib.error.HTTPError as exc:
            return exc.code, {}, dict(exc.headers)

    checks = []
    checks.append(
        {"name": "api_requires_auth", "passed": api("/api/evaluation-jobs")[0] == 401}
    )
    status, payload, _ = api("/api/evaluation-jobs", cookies[0], "POST")
    if status != 202:
        raise RuntimeError(f"Evaluation enqueue failed: {status}")
    job = payload["job_id"]
    checks.append(
        {
            "name": "job_owner_isolation",
            "passed": api("/api/evaluation-jobs/" + job, cookies[1])[0] == 404,
        }
    )
    for _ in range(30):
        _, payload, headers = api("/api/evaluation-jobs/" + job, cookies[0])
        if payload.get("status") == "completed":
            break
        time.sleep(0.5)
    checks.append(
        {
            "name": "queue_execution",
            "passed": payload.get("status") == "completed"
            and len(payload.get("checkpoint", {})) == 4
            and headers.get("cache-control") == "no-store",
        }
    )
    docker("stop", "--time", "15", NAME)
    # Remove exactly the named synthetic QA container, never the persistent volume.
    docker("rm", NAME)
    start()
    _, restored, _ = api("/api/evaluation-jobs/" + job, cookies[0])
    checks.append({"name": "recreate_volume_readback", "passed": restored == payload})
    package = json.loads(
        docker(
            "exec",
            NAME,
            "python",
            "-c",
            """
import os,json,pathlib
from app.services.report_exports import export_pdf,export_docx,_pdf_font
print(json.dumps({'uid':os.getuid(),'frontend':pathlib.Path('/app/frontend/dist/index.html').is_file(),
'pdf':export_pdf('Báo cáo','Kiểm thử tiếng Việt').startswith(b'%PDF'),
'docx':export_docx('Báo cáo','Kiểm thử').startswith(b'PK'),
'unicode_font':_pdf_font()!='Helvetica',
'secret_absent':not pathlib.Path('/app/.env').exists() and not pathlib.Path('/app/client_secret.json').exists()}))
""",
        )
    )
    checks.append(
        {
            "name": "packaged_runtime",
            "passed": package["uid"] == 10001
            and all(
                package[k]
                for k in ("frontend", "pdf", "docx", "unicode_font", "secret_absent")
            ),
            "details": package,
        }
    )
    report = {
        "checks": checks,
        "passed": all(row["passed"] for row in checks),
        "image": args.image,
        "container": NAME,
        "volume": VOLUME,
        "scope": "synthetic isolated Linux runtime; not migrated owner OAuth or model QA",
        "model_calls": 0,
        "cloud_writes": 0,
    }
    output = ROOT / "design-work/qa/container-runtime-20260930.json"
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
