"""Repeatable evaluation slices that do not spend quota or touch user data.

The course material separates final task success, trajectory quality, RAG quality,
human feedback and regression testing. This module intentionally labels its small
offline suite as a *routing regression*, not as an overall product score.
"""

import json
from pathlib import Path
from typing import Any

from app.agent.routing import route_request

EVAL_ROOT = Path(__file__).resolve().parents[2] / "evals"
GOLDEN_ROUTES = EVAL_ROOT / "golden_routes.json"


def run_routing_regression(path: Path = GOLDEN_ROUTES) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for case in payload["cases"]:
        route = route_request(case["input"])
        passed = route.tool == case["expected_tool"] and route.direct == case["expected_direct"]
        results.append(
            {
                "id": case["id"],
                "passed": passed,
                "expected_tool": case["expected_tool"],
                "actual_tool": route.tool,
                "expected_direct": case["expected_direct"],
                "actual_direct": route.direct,
            }
        )
    passed_count = sum(item["passed"] for item in results)
    return {
        "suite": "deterministic-routing",
        "version": payload["version"],
        "scope": payload["purpose"],
        "passed": passed_count,
        "total": len(results),
        "pass_rate": round(passed_count / len(results), 4) if results else None,
        "cases": results,
    }
