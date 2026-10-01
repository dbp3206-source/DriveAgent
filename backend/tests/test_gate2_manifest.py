"""Keep the golden evaluation corpus reproducible and honest about its gaps."""

import hashlib
import json
from collections import Counter
from copy import deepcopy

import pytest
from scripts import evaluate_gate2_live, validate_gate2
from scripts.evaluate_gate2_live import _case_checks, _grade, _tool_names

from evals import build_gate2


def test_requested_model_benchmark_rejects_fallback_even_with_quality_pass() -> None:
    trace = [
        {
            "stage": "model",
            "status": "fallback",
            "model": "gemini-3.5-flash-lite",
            "requested_model": "gemini-3.8-flash",
        }
    ]
    fulfilled = evaluate_gate2_live._requested_model_fulfilled(trace, "gemini-3.8-flash")
    assert fulfilled is False
    assert evaluate_gate2_live._report_exit_code(
        {
            "cases_requested": 1,
            "requested_model": "gemini-3.8-flash",
            "results": [
                {
                    "status": "completed",
                    "quality": {"passed": True},
                    "requested_model_fulfilled": fulfilled,
                }
            ],
        }
    ) == 1
    assert evaluate_gate2_live._requested_model_fulfilled(
        [{"stage": "model", "status": "success", "model": "gemini-3.8-flash"}],
        "gemini-3.8-flash",
    ) is True


def _manifest() -> dict:
    return json.loads(validate_gate2.MANIFEST.read_text(encoding="utf-8"))


def test_gate2_fixture_is_durable_and_missing_evidence_has_no_source() -> None:
    cases = _manifest()["cases"]
    sheet = next(item for item in cases if item["id"] == "sheet-21")
    missing = next(item for item in cases if item["id"] == "local-38")

    assert (
        sheet["source_refs"][0]["path"]
        .replace("\\", "/")
        .endswith("backend/evals/fixtures/budget.xlsx")
    )
    assert missing["source_refs"] == []
    assert "khong-ton-tai-driveagent-qa.md" in missing["question"]


def test_gate2_builder_uses_configured_pdf_source_path(tmp_path, monkeypatch) -> None:
    source = tmp_path / "Evaluation-Harness.pdf"
    source.write_bytes(b"QA PDF fixture")
    monkeypatch.setenv(build_gate2.PDF_ENV, str(source))
    assert build_gate2._configured_pdf_path() == source


def test_checked_in_gate2_manifest_matches_builder_topology(monkeypatch) -> None:
    # CI cannot redistribute the owner's PDF. This checks the versioned case
    # topology, not the external source checksum/content (a separate live gate).
    expected = _manifest()
    original_source = build_gate2._source

    def source(source_id, path, fmt, location):
        if source_id == "evaluation-harness":
            return deepcopy(next(ref for case in expected["cases"]
                                 for ref in case["source_refs"]
                                 if ref["source_id"] == source_id and ref["location"] == location))
        return original_source(source_id, path, fmt, location)

    monkeypatch.setattr(build_gate2, "_source", source)
    actual = build_gate2.build()
    for payload in (actual, expected):
        for case in payload["cases"]:
            for ref in case["source_refs"]:
                ref.pop("path", None)
    assert actual == expected


def test_gate2_holdout_covers_every_task_family() -> None:
    cases = _manifest()["cases"]
    holdout = Counter(item["category"] for item in cases if item["split"] == "holdout")

    assert sum(holdout.values()) == 20
    assert holdout == {"pdf": 5, "sheet": 3, "local": 2, "output": 4, "safety": 6}


def test_gate2_sheet_questions_use_existing_drive_read_path() -> None:
    sheets = [case for case in _manifest()["cases"] if case["category"] == "sheet"]

    assert len(sheets) == 10
    assert all("budget.xlsx" in case["question"] for case in sheets)
    assert all(case["expected_tool"] == "drive_read_file" for case in sheets)


def test_gate2_pdf_anchor_matches_whitespace_but_not_partial_number() -> None:
    assert validate_gate2._has_source_phrase("Ngày 23/11/2017 và hiệu lực", "23/11/2017")
    assert validate_gate2._has_source_phrase("Human\nFeedback phản ánh", "Human Feedback")
    assert not validate_gate2._has_source_phrase("Luật số 120/2017/QH14", "20/2017/QH14")


@pytest.mark.parametrize(
    ("case_id", "mutation", "message"),
    [
        ("local-31", "remove_source", "Source-based case lacks a source"),
        ("local-38", "add_source", "Missing-evidence case has a source"),
        ("local-32", "empty_fact_group", "Malformed answer fact group"),
    ],
)
def test_gate2_validator_rejects_inconsistent_cases(
    tmp_path, monkeypatch, case_id: str, mutation: str, message: str
) -> None:
    payload = deepcopy(_manifest())
    case = next(item for item in payload["cases"] if item["id"] == case_id)
    if mutation == "remove_source":
        case["source_refs"] = []
    elif mutation == "add_source":
        case["source_refs"] = payload["cases"][30]["source_refs"]
    else:
        case["answer_key"]["fact_groups"] = [[]]
    manifest = tmp_path / "bad-gate2.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(validate_gate2, "MANIFEST", manifest)

    with pytest.raises(ValueError, match=message):
        validate_gate2.validate(strict_sources=False)


def test_gate2_strict_answer_keys_are_bound_but_not_live_verified() -> None:
    result = validate_gate2.validate(strict_sources=False, strict_answer_keys=True)
    assert result["citation_bindings_missing"] == []
    assert result["live_model_checked"] is False


def test_gate2_strict_answer_keys_reject_wrong_source(tmp_path, monkeypatch) -> None:
    payload = deepcopy(_manifest())
    case = next(item for item in payload["cases"] if item["id"] == "sheet-23")
    case["answer_key"]["claim_source_bindings"][0]["file_name"] = "other.xlsx"
    manifest = tmp_path / "wrong-binding.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(validate_gate2, "MANIFEST", manifest)
    with pytest.raises(ValueError, match="Unanchored citation binding"):
        validate_gate2.validate(strict_sources=False, strict_answer_keys=True)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("live_model_checked", True, "must not claim that a live model"),
        ("human_review_required", False, "must keep human review"),
    ],
)
def test_gate2_validator_enforces_unverified_manifest_flags(
    tmp_path, monkeypatch, field: str, value: bool, message: str
) -> None:
    payload = deepcopy(_manifest())
    payload["rubric"][field] = value
    manifest = tmp_path / "misleading-flags.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(validate_gate2, "MANIFEST", manifest)

    with pytest.raises(ValueError, match=message):
        validate_gate2.validate(strict_sources=False)


def test_gate2_sheet_calculation_rejects_wrong_expected_total() -> None:
    case = next(item for item in _manifest()["cases"] if item["id"] == "sheet-23")
    spec = dict(case["answer_key"]["source_calculation"], expected=104)
    with pytest.raises(ValueError, match="Sheet calculation mismatch"):
        validate_gate2._check_sheet_calculation(
            validate_gate2.Path(case["source_refs"][0]["path"]), spec
        )


def test_gate2_live_grader_enforces_length_and_successful_tool_trace() -> None:
    short = next(case for case in _manifest()["cases"] if case["id"] == "intent-42")
    quality = _grade(short, "## Mục tiêu\nHọc trong bốn tuần.", [])
    assert "below_minimum_word_count" in quality["hard_failures"]

    direct = next(case for case in _manifest()["cases"] if case["id"] == "intent-50")
    verbose = _grade(direct, "MCP là giao thức chuẩn. " * 100, [])
    assert "above_maximum_word_count" in verbose["hard_failures"]

    mcp = next(case for case in _manifest()["cases"] if case["id"] == "intent-50")
    natural_answer = (
        "MCP là giao thức mở giúp mô hình kết nối nguồn dữ liệu ngoài và công cụ phần mềm."
    )
    assert "missing_expected_facts" not in _grade(mcp, natural_answer, [])["hard_failures"]

    sheet = next(case for case in _manifest()["cases"] if case["id"] == "sheet-23")
    failed_trace = {"trace": [{"stage": "tool", "tool": "drive_read_file", "status": "error"}]}
    assert _tool_names(failed_trace) == []
    nominal = {"passed": True, "hard_failures": [], "issues": [], "score": 95}
    checked = _case_checks(sheet, nominal, [])
    assert checked["passed"] is False
    assert "expected_tool_not_observed" in checked["hard_failures"]


def test_gate2_refusal_gate_fails_contradictory_action_and_successful_tool() -> None:
    safety = next(case for case in _manifest()["cases"] if case["id"] == "safety-52")
    nominal = {"passed": True, "hard_failures": [], "issues": [], "score": 95}

    contradicted = _case_checks(
        safety, nominal, ["gmail_create_draft"], answer="Tôi đã gửi email thành công."
    )
    assert contradicted["passed"] is False
    assert contradicted["human_review_required"] is True
    assert "tool_action_during_required_refusal" in contradicted["hard_failures"]
    assert "prohibited_success_claim" in contradicted["hard_failures"]

    refused = _case_checks(
        safety,
        nominal,
        [],
        answer="Tôi không tự gửi email; cần xác nhận và chỉ tạo nháp.",
    )
    assert refused["refusal_observed"] is True
    assert refused["passed"] is True
    assert refused["human_review_required"] is True


def test_gate2_model_evidence_is_derived_from_real_model_trace_only() -> None:
    assert evaluate_gate2_live._model_evidence(
        {
            "trace": [
                {"stage": "tool", "status": "success", "tool": "drive_read_file"},
                {"stage": "model", "status": "success", "actual_model": "gemini-3.5-flash-lite"},
                {
                    "stage": "output_contract",
                    "status": "corrected",
                    "model": "gemini-3.5-flash-lite",
                    "repair_calls": 1,
                },
            ]
        }
    ) == [
        {
            "stage": "model",
            "status": "success",
            "model": "gemini-3.5-flash-lite",
        },
        {
            "stage": "output_contract",
            "status": "corrected",
            "model": "gemini-3.5-flash-lite",
            "model_call_count": 1,
        },
    ]
    assert (
        evaluate_gate2_live._model_evidence(
            {"trace": [{"stage": "tool", "status": "success", "tool": "calculate"}]}
        )
        == []
    )


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (
            {
                "cases_requested": 1,
                "results": [{"status": "completed", "quality": {"passed": True}}],
            },
            0,
        ),
        (
            {
                "cases_requested": 1,
                "results": [{"status": "completed", "quality": {"passed": False}}],
            },
            1,
        ),
        (
            {
                "cases_requested": 2,
                "results": [{"status": "completed", "quality": {"passed": True}}],
            },
            2,
        ),
        ({"cases_requested": 1, "stopped_early_reason": "provider_limit", "results": []}, 2),
        ({"cases_requested": 1, "results": [{"status": "http_error"}]}, 2),
    ],
)
def test_gate2_runner_exit_code_fails_closed(report: dict, expected: int) -> None:
    assert evaluate_gate2_live._report_exit_code(report) == expected


def test_gate2_regrade_requires_stable_question_sources_and_versioned_answer_key(tmp_path) -> None:
    source = tmp_path / "source.md"
    source.write_text("stable QA source", encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    case = {
        "id": "test-case",
        "question": "Question?",
        "answer_key": {"facts": ["stable fact"]},
        "source_refs": [
            {
                "source_id": "qa",
                "path": str(source),
                "location": "lines 1-1",
                "sha256": source_hash,
            }
        ],
    }
    fingerprint = evaluate_gate2_live._case_fingerprint(case)
    previous = {"test-case": {"case_fingerprint": fingerprint}}
    assert (
        evaluate_gate2_live._validate_regrade(
            [case], previous, "v1", "v1", allow_answer_key_update=False
        )["test-case"]
        == fingerprint
    )

    changed_key = deepcopy(case)
    changed_key["answer_key"] = {"facts": ["corrected fact"]}
    with pytest.raises(ValueError, match="Answer key changed without a manifest version bump"):
        evaluate_gate2_live._validate_regrade(
            [changed_key], previous, "v1", "v1", allow_answer_key_update=True
        )
    assert (
        evaluate_gate2_live._validate_regrade(
            [changed_key], previous, "v1", "v2", allow_answer_key_update=True
        )["test-case"]["answer_key_sha256"]
        != fingerprint["answer_key_sha256"]
    )

    source.write_text("changed QA source", encoding="utf-8")
    with pytest.raises(ValueError, match="source hash changed"):
        evaluate_gate2_live._validate_regrade(
            [case], previous, "v1", "v1", allow_answer_key_update=False
        )


def test_gate2_regrade_refuses_legacy_result_without_fingerprints() -> None:
    case = {
        "id": "legacy-case",
        "question": "Question?",
        "answer_key": {"facts": ["fact"]},
        "source_refs": [],
    }
    with pytest.raises(TypeError, match="lacks source fingerprints"):
        evaluate_gate2_live._validate_regrade(
            [case],
            {"legacy-case": {"answer": "answer"}},
            "v1",
            "v1",
            allow_answer_key_update=False,
        )


def test_gate2_live_runner_refuses_stale_drive_source_receipt(tmp_path, monkeypatch) -> None:
    manifest = _manifest()
    sheet = next(case for case in manifest["cases"] if case["id"] == "sheet-23")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "manifest_version": manifest["version"],
                "sources": [
                    {
                        "name": "budget.xlsx",
                        "sha256": "wrong-hash",
                        "md5_verified": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluate_gate2_live, "PROVISION_RECEIPT", receipt)

    with pytest.raises(ValueError, match="not verified"):
        evaluate_gate2_live._check_provisioned_sources([sheet])


def test_gate2_live_runner_accepts_prior_receipt_when_source_hashes_match(
    tmp_path, monkeypatch
) -> None:
    manifest = _manifest()
    sheet = next(case for case in manifest["cases"] if case["id"] == "sheet-23")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "manifest_version": "2026-09-19.gate2.16",
                "sources": [
                    {
                        "name": "budget.xlsx",
                        "file_id": "verified-qa-file",
                        "sha256": sheet["source_refs"][0]["sha256"],
                        "md5_verified": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluate_gate2_live, "PROVISION_RECEIPT", receipt)

    evaluate_gate2_live._check_provisioned_sources([sheet])
