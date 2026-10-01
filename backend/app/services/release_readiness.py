"""Fail-closed release decisions, independent from offline suite averages."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

GATES = {
    "chat": ("Chat và chất lượng câu trả lời", "business"),
    "freshness": ("Thông tin cập nhật", "business"),
    # Stable artifact key retained; OCR removed by the owner on 2026-09-30.
    "rag_ocr": ("PDF có lớp văn bản, RAG và citation theo trang", "business"),
    "workflows": ("Workflow phối hợp và bảy Agent", "business"),
    "security": ("Tool Harness, approval, injection và isolation", "governance"),
    "durability": ("Queue, checkpoint, resume và chống trùng", "operations"),
    "ui": ("Light/dark và responsive", "usability"),
    "cloud": ("HTTPS, BYOK, bốn user và persistence", "operations"),
    "release": ("CI, restore, clone sạch và hướng dẫn demo", "regression"),
    "agentops": ("Logs, metrics, traces và dashboard riêng", "operations"),
}
WEIGHTS = {"source": .30, "business": .25, "reliability": .20, "usability": .15,
           "operations": .10}


def build_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    paths = []
    for directory in ("backend/app", "frontend/src", ".github/workflows"):
        paths.extend(p for p in (root / directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts
                     and p.suffix not in {".pyc", ".pyo"})
    paths.extend(root / name for name in ("backend/uv.lock", "frontend/package-lock.json",
                                          "Dockerfile") if (root / name).is_file())
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def readiness(root: Path, evidence_dir: Path, *, now: datetime | None = None) -> dict:
    current = build_fingerprint(root)
    stamp = now or datetime.now(UTC)
    try:
        manifest = json.loads((evidence_dir / "release-evidence.json").read_text("utf-8"))
    except (OSError, ValueError, TypeError):
        manifest = {}
    if not isinstance(manifest, dict):
        manifest = {}
    valid_build = manifest.get("build_id") == current
    try:
        measured = datetime.fromisoformat(manifest.get("measured_at", ""))
        fresh = (measured.tzinfo is not None
                 and timedelta(0) <= stamp - measured <= timedelta(days=7))
    except (ValueError, TypeError):
        fresh = False
    supplied = manifest.get("gates", {})
    if not isinstance(supplied, dict):
        supplied = {}
    rows = []
    for gate, (label, group) in GATES.items():
        item = supplied.get(gate, {})
        item = item if isinstance(item, dict) else {}
        status = item.get("status", "NOT VERIFIED")
        if status not in {"PASS", "FAIL", "NOT VERIFIED", "EXCLUDED"}:
            status = "NOT VERIFIED"
        reason = "Chưa có bằng chứng cùng phiên bản phát hành."
        if not valid_build or not fresh:
            status = "NOT VERIFIED"
        else:
            reason = "Gate chưa đạt."
            artifact = evidence_dir / str(item.get("artifact", ""))
            try:
                safe = artifact.resolve().is_relative_to(evidence_dir.resolve())
                raw = artifact.read_bytes() if safe and artifact.is_file() else b""
                envelope = json.loads(raw) if raw else {}
                cases = envelope.get("cases", []) if isinstance(envelope, dict) else []
                verified = (bool(raw) and hashlib.sha256(raw).hexdigest() == item.get("sha256")
                            and isinstance(envelope, dict)
                            and envelope.get("gate") == gate
                            and envelope.get("build_id") == current
                            and envelope.get("status") == status
                            and envelope.get("measured_at") == manifest.get("measured_at")
                            and isinstance(cases, list) and bool(cases)
                            and all(isinstance(case, dict) and case.get("id")
                                    and case.get("status") in {"PASS", "FAIL"}
                                    and case.get("evidence") for case in cases)
                            and (status != "PASS" or all(case["status"] == "PASS"
                                                         for case in cases)))
            except (OSError, ValueError, TypeError):
                verified = False
            if not verified:
                status, reason = "NOT VERIFIED", "Thiếu artifact hoặc checksum không khớp."
            elif status == "PASS":
                reason = "Có kết quả testcase khớp checksum và build hiện tại."
        # No mandatory gate can disappear via a user-supplied EXCLUDED marker.
        rows.append({"id": gate, "label": label, "group": group,
                     "status": status, "reason": reason, "required": True})
    scores = manifest.get("scores", {})
    scores = scores if isinstance(scores, dict) else {}
    usable_scores = all(type(scores.get(key)) in {int, float} and 0 <= scores[key] <= 10
                        for key in WEIGHTS)
    score = sum(scores[key] * weight for key, weight in WEIGHTS.items()) if usable_scores else None
    live = manifest.get("live_cases", {})
    live = live if isinstance(live, dict) else {}
    coverage = all(type(live.get(key)) is int and live[key] >= 6
                   for key in ("companies", "pdfs", "workflows", "freshness"))
    blockers = [row["id"] for row in rows if row["status"] != "PASS"]
    eligible = (not blockers and valid_build and fresh and usable_scores and coverage
                and score >= 9.2 and min(scores[key] for key in WEIGHTS) >= 9
                and type(manifest.get("open_p0_p1")) is int
                and manifest.get("open_p0_p1") == 0
                and manifest.get("holdout_verified") is True)
    return {"verdict": "PASS" if eligible else "HOLD", "build_id": current,
            "measured_at": manifest.get("measured_at") if fresh and valid_build else None,
            "gates": rows, "blockers": blockers, "score": score if valid_build and fresh else None,
            "threshold": 9.2, "scope": "closed_beta_max_4", "live_coverage_verified": coverage}
