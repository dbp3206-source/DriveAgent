"""Validate the Gate 2 golden manifest without calling a model or provider."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from evals.source_paths import source_name, source_path

MANIFEST = ROOT / "backend" / "evals" / "golden_gate2.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _has_source_phrase(text: str, phrase: str) -> bool:
    words = phrase.split()
    if not words:
        return False
    return bool(
        re.search(
            r"(?<!\w)" + r"\s+".join(re.escape(word) for word in words) + r"(?!\w)",
            text,
            re.IGNORECASE,
        )
    )


def _check_sheet_calculation(path: Path, spec: dict[str, object]) -> None:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook[str(spec["sheet"])]
        cells = sheet[str(spec["range"])]
        values = [cell.value for row in cells for cell in row]
        if not values or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in values
        ):
            raise ValueError("Sheet calculation requires a nonempty numeric range")
        operation = spec["operation"]
        if operation not in {"sum", "mean"}:
            raise ValueError(f"Unsupported Sheet operation: {operation}")
        actual = sum(values) if operation == "sum" else statistics.mean(values)
        if actual != spec["expected"]:
            raise ValueError(
                f"Sheet calculation mismatch: expected {spec['expected']}, got {actual}"
            )
    finally:
        workbook.close()


def validate(
    *, strict_sources: bool, strict_answer_keys: bool = False
) -> dict[str, object]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rubric = payload.get("rubric") or {}
    if rubric.get("live_model_checked") is not False:
        raise ValueError(
            "Static Gate 2 manifest must not claim that a live model was checked"
        )
    if rubric.get("human_review_required") is not True:
        raise ValueError(
            "Static Gate 2 manifest must keep human review explicitly required"
        )
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 60:
        raise ValueError("Gate 2 manifest must contain exactly 60 cases")
    ids = [item.get("id") for item in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Gate 2 case IDs must be unique")
    splits = {
        split: sum(item.get("split") == split for item in cases)
        for split in ("development", "holdout")
    }
    if splits != {"development": 40, "holdout": 20}:
        raise ValueError(f"Unexpected split counts: {splits}")
    format_cases = sum(item.get("category") in {"pdf", "sheet"} for item in cases)
    refusal_cases = sum(item.get("intent") == "refusal" for item in cases)
    if format_cases < 20 or refusal_cases < 10:
        raise ValueError("Gate 2 format/refusal coverage is below the plan")
    for case in cases:
        refs = case.get("source_refs") or []
        if case.get("category") in {"pdf", "sheet", "local"}:
            if case.get("risk") == "missing_evidence" and refs:
                raise ValueError(
                    f"Missing-evidence case has a source: {case.get('id')}"
                )
            if case.get("risk") != "missing_evidence" and not refs:
                raise ValueError(f"Source-based case lacks a source: {case.get('id')}")
        for group in case.get("answer_key", {}).get("fact_groups", []):
            if (
                not isinstance(group, list)
                or not group
                or not all(isinstance(value, str) and value.strip() for value in group)
            ):
                raise ValueError(f"Malformed answer fact group: {case.get('id')}")
    citation_cases = [
        item for item in cases if item.get("answer_key", {}).get("citation_required")
    ]
    unbound_citation_cases = [
        str(item.get("id"))
        for item in citation_cases
        if not item.get("answer_key", {}).get("claim_source_bindings")
    ]
    if strict_answer_keys and unbound_citation_cases:
        raise ValueError(
            "Citation claim-source bindings missing for: "
            + ", ".join(unbound_citation_cases)
        )
    if strict_answer_keys:
        for case in citation_cases:
            filenames = {
                source_name(ref["path"]) for ref in case.get("source_refs", [])
            }
            for binding in case["answer_key"]["claim_source_bindings"]:
                if binding.get("file_name") not in filenames or not binding.get(
                    "evidence_fact"
                ):
                    raise ValueError(f"Unanchored citation binding: {case['id']}")
                if case.get("category") == "pdf":
                    declared_page = int(case["source_refs"][0]["location"].split()[-1])
                    if binding.get("page_number") != declared_page:
                        raise ValueError(f"Wrong PDF citation page: {case['id']}")
    sources: dict[tuple[str, str], dict[str, object]] = {}
    missing: list[str] = []
    stale: list[str] = []
    for case in cases:
        for ref in case.get("source_refs", []):
            key = (str(ref.get("source_id")), str(ref.get("path")))
            sources[key] = ref
    for ref in sources.values():
        path = source_path(ref)
        if not path.is_file():
            missing.append(str(path))
            continue
        if _sha256(path) != ref.get("sha256"):
            stale.append(str(path))
    if strict_sources and (missing or stale):
        raise ValueError(
            f"Source verification failed: missing={missing}, stale={stale}"
        )
    if strict_sources:
        import pdfplumber

        pages: dict[tuple[str, int], str] = {}
        for case in cases:
            if case.get("category") != "pdf":
                continue
            ref = case["source_refs"][0]
            page_number = int(str(ref["location"]).removeprefix("page "))
            key = (str(source_path(ref)), page_number)
            if key not in pages:
                with pdfplumber.open(key[0]) as pdf:
                    pages[key] = " ".join(
                        (pdf.pages[page_number - 1].extract_text() or "").split()
                    )
            for binding in case.get("answer_key", {}).get("claim_source_bindings", []):
                fact = binding.get("evidence_fact")
                if not isinstance(fact, str) or not _has_source_phrase(
                    pages[key], fact
                ):
                    raise ValueError(
                        f"PDF evidence anchor not on declared page: {case['id']}"
                    )
        for case in cases:
            spec = case.get("answer_key", {}).get("source_calculation")
            if spec:
                try:
                    _check_sheet_calculation(source_path(case["source_refs"][0]), spec)
                except (KeyError, ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Invalid Sheet answer key: {case['id']}: {exc}"
                    ) from exc
    result = {
        "manifest": str(MANIFEST),
        "version": payload.get("version"),
        "cases": len(cases),
        "splits": splits,
        "pdf_or_sheet": format_cases,
        "refusal_or_ask_back": refusal_cases,
        "citation_required": len(citation_cases),
        "citation_bindings_missing": unbound_citation_cases,
        "sources": len(sources),
        "missing_sources": missing,
        "stale_sources": stale,
        "live_model_checked": rubric.get("live_model_checked"),
        "human_review_required": rubric.get("human_review_required"),
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-sources", action="store_true")
    parser.add_argument("--strict-answer-keys", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            validate(
                strict_sources=args.strict_sources,
                strict_answer_keys=args.strict_answer_keys,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
