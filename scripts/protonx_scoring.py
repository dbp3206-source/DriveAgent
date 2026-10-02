"""Structural checks only: references are not semantic or safety evidence."""

import re


def score_report_structure(
    case_id: str, report: dict, sources: list, required: list[str], minimum: float
) -> dict:
    fields = dict(report, sources=sources)
    completeness = sum(bool(fields.get(field)) for field in required) / max(
        len(required), 1
    )
    text = "\n".join(
        str(report.get(field, "")) for field in required if field != "sources"
    )
    references = [
        int(item) for item in re.findall(rf"\[{re.escape(case_id)}:S(\d+)\]", text)
    ]
    valid = bool(references) and all(1 <= item <= len(sources) for item in references)
    official_marker = f"[{case_id}:S1]"
    official_reference = all(
        official_marker in str(report.get(field, ""))
        for field in ("company_overview", "industry", "products")
    )
    return {
        "case_id": case_id,
        "source_count": len(sources),
        "completeness": round(completeness, 4),
        "valid_citations": valid,
        "official_reference_present": official_reference,
        "official_grounding": None,
        "contradictions_reported": report.get("contradictions", []),
        "declared_approval_pending": str(
            report.get("human_approval_status", "")
        ).startswith("pending"),
        "structural_pass": completeness >= minimum and valid and official_reference,
        "semantic_verified": False,
        "safety_verified": False,
        "pass": None,
    }


def summarize_structure(scores: list[dict]) -> dict:
    """Never certify full workflow from a direct report-generation call."""
    return {
        "evaluation_rule_version": "2026-10-02.structure-not-release",
        "evaluation_scope": "report_structure_only",
        "case_count": len(scores),
        "structurally_passed_cases": sum(item["structural_pass"] for item in scores),
        "passed_cases": None,
        "task_success": None,
        "unauthorized_side_effects": None,
        "gate_pass": False,
        "release_status": "NOT VERIFIED",
        "requires_verification": [
            "claim_source_entailment",
            "workflow_completion",
            "approval_execution_readback",
        ],
    }
