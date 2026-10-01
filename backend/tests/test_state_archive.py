import socket
import sqlite3
from pathlib import Path

import pytest
from scripts.state_archive import _safe_relative, backup_state, restore_state


def _fixture_state(root: Path) -> None:
    root.mkdir()
    db = sqlite3.connect(root / "drive_agent.db")
    db.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
    db.execute("INSERT INTO sentinel VALUES (?)", ("private-sentinel-for-qa",))
    db.commit()
    db.close()
    (root / "qdrant").mkdir()
    (root / "qdrant" / "vectors.bin").write_bytes(b"vector-state-qa")
    (root / "skills.db").write_bytes(b"skill-state-qa")


def test_encrypted_state_archive_roundtrip_and_wrong_passphrase(tmp_path):
    source = tmp_path / "state"
    _fixture_state(source)
    archive = tmp_path / "private.vstate"
    restored = tmp_path / "restored"
    assert backup_state(source, archive, "test-passphrase-long-enough", port=None) == 3
    encrypted = archive.read_bytes()
    assert b"private-sentinel-for-qa" not in encrypted
    assert b"vector-state-qa" not in encrypted
    assert restore_state(archive, restored, "test-passphrase-long-enough") == 3
    assert (restored / "qdrant" / "vectors.bin").read_bytes() == b"vector-state-qa"
    db = sqlite3.connect(restored / "drive_agent.db")
    assert db.execute("SELECT value FROM sentinel").fetchone()[0] == "private-sentinel-for-qa"
    db.close()

    wrong_target = tmp_path / "wrong-target"
    with pytest.raises(ValueError, match="Wrong passphrase"):
        restore_state(archive, wrong_target, "wrong-passphrase-long-enough")
    assert not wrong_target.exists()
    assert not list(tmp_path.glob(".wrong-target.restore-*"))


def test_explicit_operational_store_exclusion_keeps_application_state(tmp_path):
    source = tmp_path / "state"
    _fixture_state(source)
    (source / "prometheus-native").mkdir()
    (source / "prometheus-native" / "metrics").write_bytes(b"independent runtime")
    archive = tmp_path / "application.vstate"
    assert backup_state(source, archive, "test-passphrase-long-enough", port=None,
                        excluded_top_dirs=frozenset({"prometheus-native"})) == 3
    target = tmp_path / "restored"
    restore_state(archive, target, "test-passphrase-long-enough")
    assert (target / "drive_agent.db").is_file()
    assert not (target / "prometheus-native").exists()
    with pytest.raises(ValueError, match="Invalid excluded"):
        backup_state(source, tmp_path / "bad.vstate", "test-passphrase-long-enough", port=None,
                     excluded_top_dirs=frozenset({"../state"}))


def test_archive_refuses_overwrite_and_corruption(tmp_path):
    source = tmp_path / "state"
    _fixture_state(source)
    archive = tmp_path / "private.vstate"
    backup_state(source, archive, "test-passphrase-long-enough", port=None)
    with pytest.raises(ValueError, match="new and outside"):
        backup_state(source, archive, "test-passphrase-long-enough", port=None)
    restored = tmp_path / "existing"
    restored.mkdir()
    (restored / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="new directory"):
        restore_state(archive, restored, "test-passphrase-long-enough")
    assert (restored / "keep.txt").read_text(encoding="utf-8") == "keep"

    damaged = tmp_path / "damaged.vstate"
    payload = bytearray(archive.read_bytes())
    payload[len(payload) // 2] ^= 1
    damaged.write_bytes(payload)
    with pytest.raises((ValueError, OSError, EOFError)):
        restore_state(damaged, tmp_path / "damaged-target", "test-passphrase-long-enough")
    assert not (tmp_path / "damaged-target").exists()

    truncated = tmp_path / "truncated.vstate"
    truncated.write_bytes(archive.read_bytes()[:-4])
    with pytest.raises(ValueError, match="footer"):
        restore_state(truncated, tmp_path / "truncated-target", "test-passphrase-long-enough")
    assert not (tmp_path / "truncated-target").exists()


def test_archive_path_validation_and_running_service_guard(tmp_path):
    for name in ("state/../escape", "../../escape", "/state/escape", "state/C:/escape"):
        with pytest.raises(ValueError, match="Unsafe"):
            _safe_relative(name)
    source = tmp_path / "state"
    _fixture_state(source)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(RuntimeError, match="Stop Veridra"):
            backup_state(
                source, tmp_path / "blocked.vstate", "test-passphrase-long-enough",
                port=listener.getsockname()[1],
            )
    assert not (tmp_path / "blocked.vstate").exists()


def test_archive_rejects_symlink_and_broad_source(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="Unsafe broad backup source"):
        backup_state(
            Path.cwd(), tmp_path / "broad.vstate", "test-passphrase-long-enough", port=None
        )
    source = tmp_path / "state"
    _fixture_state(source)
    linked = source / "linked"
    linked.write_text("fixture", encoding="utf-8")
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path, "is_symlink", lambda path: path == linked or original_is_symlink(path)
    )
    with pytest.raises(ValueError, match="symlinks"):
        backup_state(source, tmp_path / "linked.vstate", "test-passphrase-long-enough", port=None)
    assert not (tmp_path / "linked.vstate").exists()
