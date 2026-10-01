import hashlib
import json
from datetime import UTC, datetime, timedelta

from app.services.release_readiness import GATES, WEIGHTS, build_fingerprint, readiness


def make_evidence(tmp_path):
    root = tmp_path / "repo"
    source = root / "backend/app/main.py"
    source.parent.mkdir(parents=True)
    source.write_text("BUILD = 1", encoding="utf-8")
    folder = tmp_path / "evidence"
    folder.mkdir()
    now = datetime(2026, 9, 30, tzinfo=UTC)
    build = build_fingerprint(root)
    manifest = {"build_id": build, "measured_at": now.isoformat(), "gates": {},
                "scores": dict.fromkeys(WEIGHTS, 9.5), "open_p0_p1": 0,
                "holdout_verified": True,
                "live_cases": dict.fromkeys(("companies", "pdfs", "workflows", "freshness"), 6)}
    for gate in GATES:
        artifact = {"gate": gate, "build_id": build, "status": "PASS",
                    "measured_at": now.isoformat(),
                    "cases": [{"id": f"{gate}-1", "status": "PASS", "evidence": "test-output"}]}
        raw = json.dumps(artifact).encode()
        (folder / f"{gate}.json").write_bytes(raw)
        manifest["gates"][gate] = {"status": "PASS", "artifact": f"{gate}.json",
                                   "sha256": hashlib.sha256(raw).hexdigest()}
    return root, folder, now, manifest


def evaluate(root, folder, now, manifest):
    (folder / "release-evidence.json").write_text(json.dumps(manifest), encoding="utf-8")
    return readiness(root, folder, now=now)


def test_complete_matching_evidence_can_pass(tmp_path):
    root, folder, now, manifest = make_evidence(tmp_path)
    manifest["scores"]["unrelated"] = "not a score"
    assert evaluate(root, folder, now, manifest)["verdict"] == "PASS"


def test_source_change_invalidates_evidence_without_restart(tmp_path):
    root, folder, now, manifest = make_evidence(tmp_path)
    assert evaluate(root, folder, now, manifest)["verdict"] == "PASS"
    (root / "backend/app/main.py").write_text("BUILD = 2", encoding="utf-8")
    assert evaluate(root, folder, now, manifest)["verdict"] == "HOLD"


def test_old_evidence_is_not_reused(tmp_path):
    root, folder, now, manifest = make_evidence(tmp_path)
    assert evaluate(root, folder, now + timedelta(days=8), manifest)["verdict"] == "HOLD"


def test_checksum_alone_does_not_prove_gate(tmp_path):
    root, folder, now, manifest = make_evidence(tmp_path)
    (folder / "chat.json").write_bytes(b"{}")
    manifest["gates"]["chat"]["sha256"] = hashlib.sha256(b"{}").hexdigest()
    result = evaluate(root, folder, now, manifest)
    assert result["verdict"] == "HOLD"
    assert "chat" in result["blockers"]


def test_required_gate_cannot_be_excluded(tmp_path):
    root, folder, now, manifest = make_evidence(tmp_path)
    manifest["gates"]["cloud"]["status"] = "EXCLUDED"
    assert evaluate(root, folder, now, manifest)["verdict"] == "HOLD"


def test_traversal_artifact_is_rejected(tmp_path):
    root, folder, now, manifest = make_evidence(tmp_path)
    manifest["gates"]["chat"]["artifact"] = "../outside.json"
    assert evaluate(root, folder, now, manifest)["verdict"] == "HOLD"


def test_missing_live_suite_or_low_score_blocks_release(tmp_path):
    root, folder, now, manifest = make_evidence(tmp_path)
    manifest["live_cases"]["pdfs"] = 5
    assert evaluate(root, folder, now, manifest)["verdict"] == "HOLD"
    manifest["live_cases"]["pdfs"] = 6
    manifest["scores"]["source"] = 8.9
    assert evaluate(root, folder, now, manifest)["verdict"] == "HOLD"


def test_malformed_manifest_fails_closed(tmp_path):
    root, folder, now, _manifest = make_evidence(tmp_path)
    assert evaluate(root, folder, now, [])["verdict"] == "HOLD"


def test_boolean_issue_count_is_not_a_verified_zero(tmp_path):
    root, folder, now, manifest = make_evidence(tmp_path)
    manifest["open_p0_p1"] = False
    assert evaluate(root, folder, now, manifest)["verdict"] == "HOLD"
