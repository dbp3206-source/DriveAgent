"""Validate the locked oracle structure; no claim of live task success."""

import json
import re
from decimal import Decimal
from pathlib import Path


def test_all_six_originals_and_six_live_questions_are_locked():
    path = Path(__file__).parents[1] / "evals/pdf_acceptance.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    sources = {source["id"]: source for source in manifest["sources"]}
    assert len(sources) == 6
    assert sum(source["pages"] for source in sources.values()) == 133
    for source in sources.values():
        assert re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
        assert Path(source["filename"]).name == source["filename"]
        assert source["redistribution"] == "Không được phép mặc định"
    assert len(manifest["cases"]) == 6
    assert len({case["id"] for case in manifest["cases"]}) == 6
    for case in [*manifest["cases"], *manifest["conditional_cases"]]:
        assert case["status"] == "NOT VERIFIED"
        assert case["question"] and case["expected"]
        for reference in case["sources"]:
            assert reference["id"] in sources
            page_count = sources[reference["id"]]["pages"]
            assert all(1 <= page <= page_count for page in reference["pages"])
        for calculation in case.get("calculations", []):
            # Restrict the source-derived oracle to binary decimal arithmetic.
            match = re.fullmatch(r"(\d+(?:\.\d+)?)([+-])(\d+(?:\.\d+)?)", calculation["expression"])
            assert match
            left, operation, right = match.groups()
            result = (
                Decimal(left) + Decimal(right)
                if operation == "+" else Decimal(left) - Decimal(right)
            )
            assert result == Decimal(str(calculation["expected"]))
    assert all(ref["id"] != "governance" for case in manifest["cases"] for ref in case["sources"])
