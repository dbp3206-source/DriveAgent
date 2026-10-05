"""Published metrics require actual, current measurements rather than defaults."""

from copy import deepcopy

import pytest

from scripts.publish_business_benchmark import validate_report


def fixture():
    manifest = {"version": "qa-v1", "cases": [{"id": "one", "question": "Question"}]}
    report = {
        "manifest_version": "qa-v1", "requested_model": "qa-model",
        "completed": 1, "quality_passed": 1,
        "results": [{
            "id": "one", "question": "Question", "status": "completed",
            "requested_model_fulfilled": True, "latency_ms": 123,
            "quality": {"passed": True, "score": 91, "hard_failures": [],
                        "fact_checks": {"checked": True}},
        }],
    }
    return report, manifest


def test_valid_measurements_are_preserved_without_invented_defaults():
    report, manifest = fixture()
    original = deepcopy(report)
    assert validate_report(report, manifest) == report["results"]
    assert report == original


def test_duplicate_case_cannot_inflate_sample_size():
    report, manifest = fixture()
    report["results"].append(deepcopy(report["results"][0]))
    with pytest.raises(SystemExit, match="exactly once"):
        validate_report(report, manifest)


def test_empty_dataset_cannot_create_a_vacuous_perfect_score():
    report, manifest = fixture()
    manifest["cases"] = []
    report.update(results=[], completed=0, quality_passed=0)
    with pytest.raises(SystemExit, match="nonempty"):
        validate_report(report, manifest)


@pytest.mark.parametrize("field,value", [("manifest_version", "old"), ("requested_model", None)])
def test_missing_model_or_stale_dataset_is_not_publishable(field, value):
    report, manifest = fixture()
    report[field] = value
    with pytest.raises(SystemExit):
        validate_report(report, manifest)


def test_changed_question_is_not_relabelled_as_current_evidence():
    report, manifest = fixture()
    report["results"][0]["question"] = "Different question"
    with pytest.raises(SystemExit, match="not publishable"):
        validate_report(report, manifest)


@pytest.mark.parametrize("value", [None, True, "91", float("nan"), float("inf"), -1, 101])
def test_score_must_be_finite_measured_number(value):
    report, manifest = fixture()
    report["results"][0]["quality"]["score"] = value
    with pytest.raises(SystemExit, match="measured score"):
        validate_report(report, manifest)


@pytest.mark.parametrize("value", [None, True, "123", float("nan"), -1])
def test_missing_latency_is_not_published_as_zero(value):
    report, manifest = fixture()
    report["results"][0]["latency_ms"] = value
    with pytest.raises(SystemExit, match="measured latency_ms"):
        validate_report(report, manifest)
