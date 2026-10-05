"""Publish a validated automated business benchmark summary for the local cockpit.

The publisher never grades answers itself. It accepts only a complete report
created by ``evaluate_business_live.py`` whose curated answer-key screens all
passed, then stores a hash-linked summary without copying private answer text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "backend" / "evals" / "business_live.json"
OUTPUT = ROOT / "backend" / "evals" / "results" / "business_live_latest.json"


def validate_report(report: dict, manifest: dict) -> list[dict]:
    """Reject stale, duplicated or unmeasured input before publishing metrics."""
    cases = manifest["cases"]
    expected = {case["id"]: case for case in cases}
    if not expected or len(expected) != len(cases):
        raise SystemExit("Dataset must have nonempty, unique case IDs.")
    results = report.get("results")
    if (
        not isinstance(results, list)
        or len(results) != len(expected)
        or any(not isinstance(item, dict) for item in results)
        or {item.get("id") for item in results} != set(expected)
    ):
        raise SystemExit("Report must cover every curated business benchmark case exactly once.")
    if report.get("manifest_version") != manifest.get("version"):
        raise SystemExit("Report manifest version does not match the current dataset.")
    if not isinstance(report.get("requested_model"), str) or not report["requested_model"].strip():
        raise SystemExit("Report must identify the model actually requested for measurement.")
    if report.get("completed") != len(expected) or report.get("quality_passed") != len(expected):
        raise SystemExit("Every case must complete and pass before publication.")
    for item in results:
        quality = item.get("quality") or {}
        if (
            not isinstance(quality, dict)
            or item.get("question") != expected[item["id"]]["question"]
            or item.get("status") != "completed"
            or quality.get("passed") is not True
            or (quality.get("hard_failures") or [])
            or not isinstance(quality.get("fact_checks"), dict)
            or quality["fact_checks"].get("checked") is not True
            or item.get("requested_model_fulfilled") is not True
        ):
            raise SystemExit(f"Case {item.get('id')} is not publishable.")
        for field, value, maximum in (
            ("score", quality.get("score"), 100),
            ("latency_ms", item.get("latency_ms"), None),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
                or (maximum is not None and value > maximum)
            ):
                raise SystemExit(f"Case {item['id']} lacks a valid measured {field}.")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    source = args.input.resolve()
    report_bytes = source.read_bytes()
    report = json.loads(report_bytes.decode("utf-8"))
    manifest_bytes = MANIFEST.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    results = validate_report(report, manifest)
    summary = {
        "schema_version": 1,
        "published_at_utc": datetime.now(UTC).isoformat(),
        "manifest_version": manifest.get("version"),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "source_report": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else source.name,
        "requested_model": report.get("requested_model"),
        "sample_size": len(results),
        "passed": len(results),
        "pass_rate": 1.0,
        "average_screening_score": round(
            sum(float(item["quality"]["score"]) for item in results)
            / len(results),
            1,
        ),
        "cases": [
            {
                "id": item["id"],
                "score": (item.get("quality") or {}).get("score"),
                "latency_ms": item.get("latency_ms"),
                "message_id": item.get("message_id"),
            }
            for item in results
        ],
        "scope": (
            "Ba tác vụ giả lập có answer key: ngân hàng, giáo dục và tồn kho. "
            "Đo ràng buộc, dữ kiện mong đợi và cấu trúc hành động; không suy rộng "
            "thành độ đúng cho mọi nghiệp vụ hoặc entailment ngữ nghĩa độc lập."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"published": str(OUTPUT), "sample_size": len(results), "pass_rate": 1.0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
