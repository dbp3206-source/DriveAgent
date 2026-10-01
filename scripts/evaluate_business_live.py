"""Run synthetic, read-only multi-step business probes through the real chat API.

The output records model/tool metadata and full QA answers locally. Automated
checks are only screening signals; a blind human review must still establish
correctness, completeness, and business usefulness.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
from pathlib import Path

from evaluate_gate2_live import (
    _case_checks,
    _grade,
    _model_evidence,
    _post_chat,
    _requested_model_fulfilled,
    _session_cookie,
    _tool_names,
)

from app.core.config import APPROVED_GEMINI_MODELS

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "backend" / "evals" / "business_live.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--user-id", default=os.environ.get("DRIVE_AGENT_VERIFY_USER_ID")
    )
    parser.add_argument(
        "--ids", required=True, help="Explicit comma-separated QA case IDs"
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--model", choices=sorted(APPROVED_GEMINI_MODELS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.user_id:
        raise SystemExit("Provide an approved QA --user-id.")
    if args.output.exists():
        raise SystemExit("Output already exists; preserve previous evidence.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
    cases = [case for case in manifest["cases"] if case["id"] in wanted]
    if not wanted or {case["id"] for case in cases} != wanted:
        raise SystemExit("Unknown or empty QA case selection.")

    cookie = _session_cookie(args.user_id)
    results = []
    for index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        result = {
            "id": case["id"],
            "question": case["question"],
            "status": "unknown",
        }
        try:
            payload = _post_chat(
                args.base_url, cookie, case["question"], args.timeout, model=args.model
            )
            answer = str(payload.get("answer") or "")
            citations = payload.get("citations") or []
            tools = _tool_names(payload)
            screening = _case_checks(
                case, _grade(case, answer, citations), tools, answer=answer
            )
            # A deterministic answer-key screen cannot adjudicate whether a
            # proposed business action is feasible or factually entailed.
            screening["human_review_required"] = True
            model_trace = _model_evidence(payload)
            result.update(
                {
                    "status": "completed",
                    "answer": answer,
                    "citations": citations,
                    "trace_tools": tools,
                    "model_trace": model_trace,
                    "requested_model_fulfilled": _requested_model_fulfilled(
                        model_trace, args.model
                    ),
                    "proposal_kinds": [
                        str(item.get("kind"))
                        for item in (payload.get("proposals") or [])
                        if isinstance(item, dict) and item.get("kind")
                    ],
                    "quality": screening,
                    "message_id": payload.get("message_id"),
                }
            )
        except urllib.error.HTTPError as exc:
            result.update(
                {
                    "status": "http_error",
                    "http_status": exc.code,
                    "detail": exc.read().decode("utf-8", errors="replace")[:500],
                }
            )
        except (OSError, ValueError, TypeError, KeyError) as exc:
            result.update(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "detail": str(exc)[:500],
                }
            )
        result["latency_ms"] = round((time.perf_counter() - started) * 1000)
        results.append(result)
        print(f"[{index}/{len(cases)}] {case['id']}: {result['status']}", flush=True)

    report = {
        "manifest_version": manifest["version"],
        "scope": "synthetic_read_only_development_not_release_score",
        "base_url": args.base_url,
        "requested_model": args.model,
        "cases_requested": len(cases),
        "completed": sum(item["status"] == "completed" for item in results),
        "quality_passed": sum(
            bool(item.get("quality", {}).get("passed")) for item in results
        ),
        "requested_model_fulfilled_cases": sum(
            item.get("requested_model_fulfilled") is True for item in results
        ) if args.model else None,
        "human_review_required": True,
        "cloud_write_approval_submitted": False,
        "local_chat_history_may_be_written": True,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "cases_requested", "completed", "quality_passed",
                    "requested_model_fulfilled_cases",
                )
            }
        )
    )
    return (
        0
        if report["completed"] == len(cases)
        and report["quality_passed"] == len(cases)
        and (not args.model or report["requested_model_fulfilled_cases"] == len(cases))
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
