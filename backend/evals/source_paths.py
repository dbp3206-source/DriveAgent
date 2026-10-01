"""Resolve source locations without changing declared hashes or answer keys."""

import os
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]


def source_name(path: str) -> str:
    return PurePosixPath(str(path).replace("\\", "/")).name


def source_path(ref: dict) -> Path:
    path = Path(str(ref["path"]))
    if path.is_file():
        return path
    fixtures = {
        "qa-budget-xlsx": ROOT / "backend/evals/fixtures/budget.xlsx",
        "local-study-fixture": ROOT / "backend/tests/fixtures/local-study-smoke.md",
    }
    if ref.get("source_id") in fixtures:
        return fixtures[ref["source_id"]]
    if ref.get("source_id") == "evaluation-harness":
        configured = os.environ.get("DRIVE_AGENT_EVALUATION_PDF_PATH")
        if configured:
            return Path(configured).expanduser()
    return path  # Missing private source must still fail strict verification.
