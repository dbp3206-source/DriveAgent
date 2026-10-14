"""Validate local acceptance inputs/answer keys without any service/model calls."""

import json
from decimal import Decimal
from pathlib import Path


def validate(root: Path) -> dict:
    data = json.loads((root / "testcases.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    assert [case["id"] for case in cases] == [f"T{i:02d}" for i in range(1, 11)]
    assert set().union(*(set(case["jobs"]) for case in cases)) == {
        "N1", "N2", "N3", "N4", "N5"
    }
    for relative in data["fixtures"]:
        file = (root / relative).resolve()
        assert file.is_relative_to(root.resolve())
        assert file.is_file() and "giả lập" in file.read_text(encoding="utf-8")
        assert "## Đáp án nguồn" not in file.read_text(encoding="utf-8")
    assert "Ghi chú sau họp" not in (root / "inputs/B-hop-du-an.md").read_text(encoding="utf-8")
    for case in cases:
        assert case["input"] and case["expected"] and case["sources"]
        for calculation in case.get("calculations", []):
            total = Decimal(calculation["people"]) * Decimal(calculation["hours_per_person"])
            saved = total * Decimal(calculation["reduction"])
            assert [total, saved, total - saved] == list(map(Decimal, calculation["expected"]))
    calls = sum(case["model_calls_planned"] for case in cases)
    assert calls + data["reserve_calls"] <= data["real_model_call_cap"]
    assert data["real_model_call_cap"] + data["embedding_call_cap"] == data["total_provider_request_cap"]
    return {"dataset_version": data["dataset_version"], "cases": len(cases),
            "fixtures": len(data["fixtures"]), "planned_model_calls": calls,
            "reserve_calls": data["reserve_calls"], "integrity_passed": True,
            "generation_cap": data["real_model_call_cap"],
            "embedding_cap": data["embedding_call_cap"],
            "total_request_cap": data["total_provider_request_cap"],
            "scope": "local dataset only; product acceptance not executed"}


if __name__ == "__main__":
    dataset = Path(__file__).resolve().parents[1] / "docs/verification/internal-assistant"
    print(json.dumps(validate(dataset), ensure_ascii=False, indent=2))
