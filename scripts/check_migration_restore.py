"""Verify encrypted application snapshot into a fresh, owner-private directory."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def run(archive: Path) -> dict:
    from state_archive import restore_state

    from app.core.config import get_settings

    archive = archive.resolve(strict=True)
    allowed = (ROOT / ".local-backups" / "migration-20260930").resolve(strict=True)
    if archive.parent != allowed or not archive.name.startswith("state-pre-migration-"):
        raise ValueError("Expected exact migration application archive")
    target = allowed / "restore-check-090150"
    restored = restore_state(archive, target, get_settings().app_secret)
    database = target / "drive_agent.db"
    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as db:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ValueError("Restored database integrity failed")
    return {"restored_files": restored, "database_integrity": integrity,
            "restore_verified": True, "isolated_directory": str(target),
            "operational_dashboard_stores_included": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.archive)))
