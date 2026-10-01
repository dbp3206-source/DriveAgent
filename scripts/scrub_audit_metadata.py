"""One-time, recoverable migration of legacy tool audit payloads to metadata.

Dry-run by default. Apply only while DriveAgent is stopped. The encrypted SQLite
snapshot is intentionally retained for operator-controlled recovery and must be
removed under a separately approved backup-retention policy.
"""

import argparse
import base64
import hashlib
import importlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

Settings = importlib.import_module("app.core.config").Settings
agentops = importlib.import_module("app.services.agentops")
registry = importlib.import_module("app.tools.registry")
RETENTION_DAYS = agentops.RETENTION_DAYS
sanitize_run_trace = agentops.sanitize_run_trace

LEGACY_ARGUMENTS = '{"legacy_values_removed":true}'
LEGACY_RESULT = '{"legacy_values_removed":true}'
SAFE_TOOL_FAILURE_MESSAGE = registry.SAFE_TOOL_FAILURE_MESSAGE


def _cipher(settings: Settings) -> Fernet:
    if settings.app_secret == "local-development-change-me-before-sharing":
        raise ValueError("Set a non-default APP_SECRET before encrypted backup")
    digest = hashlib.sha256(settings.app_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _is_legacy(arguments_json: str, result_json: str, error_message: str | None) -> bool:
    try:
        arguments = json.loads(arguments_json or "{}")
        result = json.loads(result_json or "{}")
    except (TypeError, ValueError):
        return True
    if not isinstance(arguments, dict) or not isinstance(result, dict):
        return True
    if arguments == {"legacy_values_removed": True} and result == {
        "legacy_values_removed": True
    }:
        return bool(error_message) and error_message != SAFE_TOOL_FAILURE_MESSAGE
    return set(arguments) != {"argument_count"} or (
        bool(error_message) and error_message != SAFE_TOOL_FAILURE_MESSAGE
    ) or (
        "output_type" not in result and bool(result)
    )


def legacy_ids(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT id, arguments_json, result_json, error_message "
        "FROM audit_events WHERE tool_name != 'agent_task'"
    )
    return [
        row[0]
        for row in rows
        if _is_legacy(row[1], row[2], row[3])
    ]


def trace_updates(
    connection: sqlite3.Connection, *, now: datetime | None = None
) -> list[tuple[str, str]]:
    """Return (sanitized trace JSON, message ID) without changing chat content."""

    tables = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "messages" not in tables:
        return []
    current = now or datetime.now(UTC)
    cutoff = current.astimezone(UTC) - timedelta(days=RETENTION_DAYS)
    updates = []
    rows = connection.execute(
        "SELECT id, request_id, created_at, trace_json FROM messages WHERE role='assistant'"
    )
    for message_id, request_id, created_at, trace_json in rows:
        try:
            created = datetime.fromisoformat(str(created_at))
            created = (
                created.replace(tzinfo=UTC)
                if created.tzinfo is None
                else created.astimezone(UTC)
            )
        except ValueError:
            created = datetime.min.replace(tzinfo=UTC)
        if created < cutoff:
            safe_trace = "[]"
        else:
            try:
                events = json.loads(trace_json or "[]")
            except (TypeError, ValueError):
                events = []
            safe_trace = json.dumps(
                sanitize_run_trace(events, str(request_id or "historical-run"))
                if isinstance(events, list)
                else [],
                ensure_ascii=False,
            )
        try:
            existing = json.loads(trace_json or "[]")
        except (TypeError, ValueError):
            existing = None
        if json.loads(safe_trace) != existing:
            updates.append((safe_trace, message_id))
    return updates


def backup_and_scrub(
    database: Path, backup_path: Path, settings: Settings, *, apply: bool
) -> dict[str, object]:
    database = database.resolve(strict=True)
    source = sqlite3.connect(str(database), timeout=30)
    try:
        targets = legacy_ids(source)
        traces = trace_updates(source)
        if not apply or (not targets and not traces):
            return {
                "legacy_rows": len(targets),
                "trace_rows": len(traces),
                "changed_rows": 0,
                "backup": None,
            }

        # SQLite's online backup gives a consistent image even with WAL. The
        # operator still must stop the app so no post-snapshot writes race the
        # migration. No raw temporary database file touches disk.
        snapshot = sqlite3.connect(":memory:")
        try:
            source.backup(snapshot)
            if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("SQLite snapshot failed integrity check")
            if len(legacy_ids(snapshot)) != len(targets):
                raise RuntimeError("SQLite snapshot is not the expected audit state")
            if len(trace_updates(snapshot)) != len(traces):
                raise RuntimeError("SQLite snapshot is not the expected trace state")
            snapshot_bytes = snapshot.serialize()
            encrypted = _cipher(settings).encrypt(snapshot_bytes)
            if _cipher(settings).decrypt(encrypted) != snapshot_bytes:
                raise RuntimeError("Encrypted backup failed round-trip verification")
        finally:
            snapshot.close()

        backup_path.parent.mkdir(parents=True, exist_ok=True)
        with backup_path.open("xb"):
            pass
        try:
            if os.name == "nt":
                owner = subprocess.run(
                    ["whoami"], check=True, capture_output=True, text=True
                ).stdout.strip()
                owner_of_project = subprocess.run(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-Command",
                        "(Get-Acl -LiteralPath $env:DRIVE_AGENT_BACKUP_PROJECT_ROOT).Owner",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    env={**os.environ, "DRIVE_AGENT_BACKUP_PROJECT_ROOT": str(PROJECT_ROOT)},
                ).stdout.strip()
                if owner.casefold() != owner_of_project.casefold():
                    raise PermissionError(
                        "Run encrypted backup migration as the repository owner, "
                        "not a sandbox or service account"
                    )
                subprocess.run(
                    ["icacls", str(backup_path), "/inheritance:r", "/grant:r", f"{owner}:(F)"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                backup_path.chmod(0o600)
            with backup_path.open("wb") as backup_file:
                backup_file.write(encrypted)
        except Exception:
            backup_path.unlink(missing_ok=True)
            raise

        source.execute("BEGIN IMMEDIATE")
        try:
            source.executemany(
                "UPDATE audit_events SET arguments_json=?, result_json=?, error_message=NULL "
                "WHERE id=? AND tool_name != 'agent_task'",
                [(LEGACY_ARGUMENTS, LEGACY_RESULT, row_id) for row_id in targets],
            )
            source.executemany(
                "UPDATE messages SET trace_json=? WHERE id=? AND role='assistant'",
                traces,
            )
            source.commit()
        except Exception:
            source.rollback()
            raise
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Database integrity check failed after migration")
        if legacy_ids(source) or trace_updates(source):
            raise RuntimeError("Legacy telemetry payloads remain after migration")
        return {
            "legacy_rows": len(targets),
            "trace_rows": len(traces),
            "changed_rows": len(targets) + len(traces),
            "backup": str(backup_path),
        }
    finally:
        source.close()


def restore_to_new_path(encrypted_backup: Path, destination: Path, settings: Settings) -> None:
    plaintext = _cipher(settings).decrypt(encrypted_backup.read_bytes())
    if not plaintext.startswith(b"SQLite format 3\x00"):
        raise RuntimeError("Encrypted backup is not a SQLite database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as restored:
        restored.write(plaintext)
    with sqlite3.connect(destination) as verifier:
        if verifier.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Restored SQLite database failed integrity check")


def _within_project(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT):
        raise ValueError("Paths must stay inside the DriveAgent repository")
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=PROJECT_ROOT / "data/drive_agent.db")
    parser.add_argument("--backup-root", type=Path, default=PROJECT_ROOT / ".local-backups")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--offline-confirmed", action="store_true")
    parser.add_argument("--restore-from", type=Path)
    parser.add_argument("--restore-to", type=Path)
    args = parser.parse_args()
    settings = Settings()
    if args.restore_from or args.restore_to:
        if not args.restore_from or not args.restore_to:
            parser.error("--restore-from and --restore-to are required together")
        restore_to_new_path(
            _within_project(args.restore_from), _within_project(args.restore_to), settings
        )
        print("Restored encrypted snapshot to a new path; live database unchanged.")
        return
    if args.apply and not args.offline_confirmed:
        parser.error("Stop DriveAgent and pass --offline-confirmed before applying")
    backup_name = (
        "telemetry-pre-scrub-"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        + ".db.fernet"
    )
    result = backup_and_scrub(
        _within_project(args.database),
        _within_project(args.backup_root) / backup_name,
        settings,
        apply=args.apply,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
