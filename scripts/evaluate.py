"""Run the quota-free golden routing regression from the repository root."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.evaluation import (
    run_adversarial_mutation_regression,
    run_answer_contract_benchmark,
    run_output_quality_regression,
    run_routing_regression,
)


def main() -> int:
    # Windows PowerShell commonly exposes a legacy console encoding. Evaluation
    # fixtures contain Vietnamese, so make the CLI deterministic without asking
    # users to set PYTHONIOENCODING manually.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    suites = [
        run_routing_regression(),
        run_output_quality_regression(),
        run_answer_contract_benchmark(),
        run_adversarial_mutation_regression(),
    ]
    passed = sum(item["passed"] for item in suites)
    total = sum(item["total"] for item in suites)
    result = {
        "summary": {
            "passed": passed,
            "total": total,
            "all_suites_passed": all(item["passed"] == item["total"] for item in suites),
            "warning": (
                "These are deterministic routing, evaluator-regression and reference-answer "
                "contract checks. They are not a live model, retrieval, artifact, usability, "
                "or end-to-end product-accuracy benchmark."
            ),
        },
        "suites": suites,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["summary"]["all_suites_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
