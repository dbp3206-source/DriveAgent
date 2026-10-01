"""Versioned baseline/candidate regression gate; zero Gemini/Google calls."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def compare(baseline: dict, candidate: dict) -> list[str]:
    if baseline["dataset_sha256"] != candidate["dataset_sha256"]:
        return ["Dataset changed; comparison blocked"]
    failures = []
    if set(baseline["suites"]) != set(candidate["suites"]):
        failures.append("Suite coverage changed")
    for name, result in candidate["suites"].items():
        previous = baseline["suites"].get(name)
        if not previous or result["total"] != previous["total"]:
            failures.append(f"{name}: coverage changed")
        elif result["pass_rate"] < previous["pass_rate"]:
            failures.append(f"{name}: regression")
    return failures


def main():
    from app.services.evaluation import (
        run_adversarial_mutation_regression,
        run_answer_contract_benchmark,
        run_output_quality_regression,
        run_routing_regression,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    files = sorted((ROOT / "backend/evals").glob("golden_*.json"))
    fingerprint = hashlib.sha256(
        b"".join(path.name.encode() + b"\0" + path.read_bytes() for path in files)
    ).hexdigest()
    raw = {
        "routing": run_routing_regression(),
        "output_evaluator": run_output_quality_regression(),
        "answer_contract": run_answer_contract_benchmark(),
        "mutation_guard": run_adversarial_mutation_regression(),
    }
    suites = {
        name: {key: result[key] for key in ("passed", "total", "pass_rate")}
        for name, result in raw.items()
    }
    candidate = {
        "measured_at": datetime.now(UTC).isoformat(),
        "dataset_sha256": fingerprint,
        "scope": "offline regression only; not product correctness or live model quality",
        "suites": suites,
        "model_calls": 0,
        "cloud_writes": 0,
    }
    failures = [name for name, result in suites.items() if result["pass_rate"] != 1]
    if args.baseline:
        failures += compare(json.loads(args.baseline.read_text()), candidate)
    candidate["gate_passed"] = not failures
    candidate["failures"] = failures
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, indent=2), encoding="utf-8")
    print(json.dumps(candidate, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
