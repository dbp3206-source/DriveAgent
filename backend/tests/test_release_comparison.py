import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/evaluate_release_offline.py"
spec = importlib.util.spec_from_file_location("release_comparison", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def report(rate=1, total=12, fingerprint="dataset", suites=None):
    return {
        "dataset_sha256": fingerprint,
        "suites": suites or {"routing": {"total": total, "pass_rate": rate}},
    }


def test_same_dataset_and_coverage_pass():
    assert module.compare(report(), report()) == []


def test_regression_and_dataset_change_fail_closed():
    assert "routing: regression" in module.compare(report(), report(rate=0.9))
    assert module.compare(report(), report(fingerprint="changed"))
    assert "routing: coverage changed" in module.compare(report(), report(total=10))


def test_removed_suite_cannot_silently_pass():
    baseline = report(
        suites={"routing": {"total": 12, "pass_rate": 1}, "output": {"total": 12, "pass_rate": 1}}
    )
    assert "Suite coverage changed" in module.compare(baseline, report())
