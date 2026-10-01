"""Bounded retention for encrypted, pre-redaction AgentOps snapshots only."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

BACKUP_RETENTION_DAYS = 30
BACKUP_NAME = re.compile(r"(?:audit|telemetry)-pre-scrub-(\d{8}T\d{6}Z)\.db\.fernet\Z")
MIGRATION_FOLDER = re.compile(r"migration-\d{8}\Z")
MIGRATION_ARCHIVE = re.compile(r"(?:state|code)-pre-migration-(\d{8}T\d{6}Z)\.vrd\Z")


def expire_pre_scrub_backups(root: Path, *, now: datetime | None = None) -> list[str]:
    """Remove only expired files with our exact encrypted backup naming contract.

    Only dedicated migration folders are inspected one level deep. Symlinks,
    junctions and unrelated production backups are never followed or removed.
    The older of the filename timestamp and modification time is used
    so copying a stale snapshot cannot silently extend its retention period.
    """

    if not root.exists():
        return []
    # Path.is_junction was added in Python 3.12; the backend also supports 3.11.
    is_junction = getattr(root, "is_junction", lambda: False)
    if root.is_symlink() or is_junction():
        raise ValueError("Encrypted backup root must be a real local directory")
    root = root.resolve(strict=True)
    cutoff = (now or datetime.now(UTC)).astimezone(UTC) - timedelta(
        days=BACKUP_RETENTION_DAYS
    )
    removed: list[str] = []
    for candidate in root.iterdir():
        if MIGRATION_FOLDER.fullmatch(candidate.name) and candidate.is_dir():
            if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
                continue
            for archive in candidate.iterdir():
                stamped_archive = MIGRATION_ARCHIVE.fullmatch(archive.name)
                if not stamped_archive or archive.is_symlink() or not archive.is_file():
                    continue
                try:
                    stamped = datetime.strptime(stamped_archive.group(1), "%Y%m%dT%H%M%SZ")
                    stamped = stamped.replace(tzinfo=UTC)
                except ValueError:
                    continue
                modified = datetime.fromtimestamp(archive.stat().st_mtime, UTC)
                if min(stamped, modified) < cutoff:
                    archive.unlink()
                    removed.append(f"{candidate.name}/{archive.name}")
            continue
        match = BACKUP_NAME.fullmatch(candidate.name)
        if not match or candidate.is_symlink() or not candidate.is_file():
            continue
        if candidate.parent.resolve(strict=True) != root:
            continue
        try:
            stamped = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError:
            continue
        modified = datetime.fromtimestamp(candidate.stat().st_mtime, UTC)
        if min(stamped, modified) < cutoff:
            candidate.unlink()
            removed.append(candidate.name)
    return removed
