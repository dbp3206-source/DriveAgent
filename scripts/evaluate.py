"""Run the quota-free golden routing regression from the repository root."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.evaluation import run_routing_regression


def main() -> int:
    result = run_routing_regression()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
