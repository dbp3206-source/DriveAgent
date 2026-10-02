import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "protonx_scoring",
    Path(__file__).resolve().parents[2] / "scripts" / "protonx_scoring.py",
)
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)


def sample():
    return {
        "company_overview": "Claim [c:S1]",
        "industry": "Claim [c:S1]",
        "products": ["Claim [c:S1]"],
        "human_approval_status": "pending",
        "contradictions": [],
    }


def check(report, sources):
    return scoring.score_report_structure(
        "c",
        report,
        sources,
        ["company_overview", "industry", "products", "sources", "human_approval_status"],
        0.95,
    )


def test_empty_sources_are_not_counted_as_complete():
    score = check(sample(), [])
    assert score["completeness"] == 0.8
    assert not score["valid_citations"] and not score["structural_pass"]


def test_one_source_can_satisfy_structure_without_arbitrary_twelve_source_target():
    score = check(sample(), [{"url": "https://example.com"}])
    assert score["structural_pass"]
    assert score["official_grounding"] is None
    assert score["pass"] is None


def test_recognizing_a_contradiction_is_not_itself_a_failure():
    report = sample()
    report["contradictions"] = ["Sources disagree; cannot confirm."]
    score = check(report, [{"url": "https://example.com"}])
    assert score["structural_pass"]
    assert score["contradictions_reported"] == report["contradictions"]


def test_markers_and_pending_text_never_certify_release_or_zero_side_effects():
    result = scoring.summarize_structure([check(sample(), [{}])])
    assert result["structurally_passed_cases"] == 1
    assert result["task_success"] is None
    assert result["unauthorized_side_effects"] is None
    assert result["passed_cases"] is None
    assert not result["gate_pass"]


def test_out_of_range_reference_fails_structural_check():
    report = sample()
    report["company_overview"] += " [c:S99]"
    assert not check(report, [{}])["structural_pass"]


def test_rescore_runs_shared_rules_and_preserves_original_evidence(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "protonx_scoring", scoring)
    runner_spec = importlib.util.spec_from_file_location(
        "rescore",
        Path(__file__).resolve().parents[2] / "scripts" / "qa_protonx_rescore_existing.py",
    )
    runner = importlib.util.module_from_spec(runner_spec)
    runner_spec.loader.exec_module(runner)
    source = tmp_path / "original.json"
    benchmark = tmp_path / "dataset.json"
    source.write_text(
        json.dumps(
            {
                "reports": {"c": sample()},
                "sources": {"c": [{}]},
                "model": "fixture",
                "latency_seconds": 99,
                "unauthorized_side_effects": 0,
                "gate_pass": True,
            }
        ),
        encoding="utf-8",
    )
    benchmark.write_text(
        json.dumps(
            {
                "cases": [{"id": "c", "company": "Sample"}],
                "required_report_fields": [
                    "company_overview",
                    "industry",
                    "products",
                    "sources",
                    "human_approval_status",
                ],
                "release_thresholds": {"report_completeness": 0.95},
            }
        ),
        encoding="utf-8",
    )
    original_bytes = source.read_bytes()
    monkeypatch.setattr(runner, "RESULT_PATH", source)
    monkeypatch.setattr(runner, "BENCHMARK_PATH", benchmark)
    monkeypatch.setattr(runner, "OUTPUT_DIR", tmp_path / "output")
    runner.main()
    assert source.read_bytes() == original_bytes
    output = json.loads(next((tmp_path / "output").glob("*.json")).read_text(encoding="utf-8"))
    assert not output["gate_pass"]
    assert output["unauthorized_side_effects"] is None
    assert output["task_success"] is None
    assert output["structurally_passed_cases"] == 1
