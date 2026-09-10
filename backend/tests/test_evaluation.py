import json

from app.services.evaluation import run_routing_regression


def test_golden_routing_regression_is_versioned_and_passes():
    result = run_routing_regression()
    assert result["version"]
    assert result["total"] >= 10
    assert result["passed"] == result["total"], json.dumps(result, ensure_ascii=False, indent=2)
    assert "does not measure answer correctness" in result["scope"]
