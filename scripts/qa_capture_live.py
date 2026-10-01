"""Bounded existing live probes, retain private answers locally, print counts only."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
environment = {
    **os.environ,
    "PYTHONPATH": str(root / "backend") + os.pathsep + str(root / "scripts"),
    "PYTHONIOENCODING": "utf-8",
}
parser = argparse.ArgumentParser()
parser.add_argument("--daily-retry", action="store_true")
retry = parser.parse_args().daily_retry
checks = []
scripts = (
    ("qa_live_daily_skill.py",)
    if retry
    else ("qa_live_daily_skill.py", "qa_live_chat_depth.py")
)
for script in scripts:
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / script)]
        + (["--model", "gemini-3.8-flash"] if retry else []),
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=420,
        check=False,
    )
    output = (
        root
        / "design-work/qa"
        / (
            script.removesuffix(".py")
            + ("-retry38" if retry else "")
            + "-docker-20260930.json"
        )
    )
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        payload = {"status": "probe_error", "exit_code": result.returncode}
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    checks.append(
        {
            "script": script,
            "exit_code": result.returncode,
            "status": payload.get("status"),
            "answer_chars": payload.get("answer_chars"),
            "result_count": len(payload.get("results", [])),
            "local_report": output.name,
        }
    )
    print(json.dumps(checks[-1]), flush=True)
print(
    json.dumps(
        {
            "checks": checks,
            "all_probes_completed": all(c["exit_code"] == 0 for c in checks),
        }
    )
)
