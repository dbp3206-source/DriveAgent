import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.backup_retention import expire_pre_scrub_backups


def test_expiration_is_limited_to_old_encrypted_pre_scrub_files(tmp_path):
    now = datetime(2026, 9, 25, tzinfo=UTC)
    old = tmp_path / "audit-pre-scrub-20260801T120000Z.db.fernet"
    fresh = tmp_path / "telemetry-pre-scrub-20260924T120000Z.db.fernet"
    unrelated = tmp_path / "production-backup-20260801T120000Z.db.fernet"
    for path in (old, fresh, unrelated):
        path.write_bytes(b"encrypted test data")
    assert expire_pre_scrub_backups(tmp_path, now=now) == [old.name]
    assert not old.exists()
    assert fresh.exists() and unrelated.exists()


def test_modified_time_cannot_extend_retention_and_symlink_is_ignored(tmp_path):
    now = datetime(2026, 9, 25, tzinfo=UTC)
    stale_copy = tmp_path / "audit-pre-scrub-20260924T120000Z.db.fernet"
    stale_copy.write_bytes(b"encrypted test data")
    stale = (now - timedelta(days=31)).timestamp()
    os.utime(stale_copy, (stale, stale))
    outside = tmp_path / "outside-backup-canary"
    outside.write_bytes(b"do not remove")
    link = tmp_path / "telemetry-pre-scrub-20260801T120000Z.db.fernet"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pass
    assert expire_pre_scrub_backups(tmp_path, now=now) == [stale_copy.name]
    assert outside.exists()


def test_invalid_stamp_is_ignored_and_symlink_root_is_rejected(tmp_path):
    invalid = tmp_path / "audit-pre-scrub-20269999T120000Z.db.fernet"
    invalid.write_bytes(b"not a valid date")
    assert expire_pre_scrub_backups(tmp_path, now=datetime(2026, 9, 25, tzinfo=UTC)) == []
    assert invalid.exists()
    with patch.object(Path, "is_symlink", return_value=True):
        with pytest.raises(ValueError, match="real local directory"):
            expire_pre_scrub_backups(tmp_path)


def test_migration_archives_expire_without_deleting_other_data(tmp_path):
    folder = tmp_path / "migration-20260930"
    folder.mkdir()
    old = folder / "state-pre-migration-20260801T120000Z.vrd"
    fresh = folder / "code-pre-migration-20260930T120000Z.vrd"
    unrelated = folder / "notes.txt"
    for path in (old, fresh, unrelated):
        path.write_bytes(b"test archive")
    now = datetime(2026, 10, 1, tzinfo=UTC)
    removed = expire_pre_scrub_backups(tmp_path, now=now)
    assert removed == [f"{folder.name}/{old.name}"]
    assert fresh.exists() and unrelated.exists()
