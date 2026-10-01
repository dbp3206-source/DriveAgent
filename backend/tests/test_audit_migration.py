import os
import sqlite3
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from scripts.scrub_audit_metadata import (
    SAFE_TOOL_FAILURE_MESSAGE,
    _is_legacy,
    backup_and_scrub,
    restore_to_new_path,
)

from app.core.config import Settings


def test_sanitized_tool_failure_is_not_misclassified_as_legacy():
    assert not _is_legacy('{"argument_count": 3}', '{}', SAFE_TOOL_FAILURE_MESSAGE)
    assert _is_legacy('{"argument_count": 3}', '{}', 'Raw provider document text')
    assert _is_legacy('{"query": "private"}', '{}', SAFE_TOOL_FAILURE_MESSAGE)


def test_legacy_audit_scrub_has_encrypted_recoverable_snapshot(tmp_path):
    database = tmp_path / "audit.db"
    backup = tmp_path / "audit.db.fernet"
    restored = tmp_path / "restored.db"
    with sqlite3.connect(database) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        db.execute(
            "CREATE TABLE audit_events (id TEXT PRIMARY KEY, tool_name TEXT, "
            "arguments_json TEXT, result_json TEXT, error_message TEXT)"
        )
        db.execute(
            "CREATE TABLE messages (id TEXT PRIMARY KEY, role TEXT, request_id TEXT, "
            "created_at TEXT, trace_json TEXT, content TEXT)"
        )
        db.executemany(
            "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "old-trace",
                    "assistant",
                    "old-run",
                    (datetime.now(UTC) - timedelta(days=31)).isoformat(),
                    '[{"stage":"planning","steps":["private-old-canary"]}]',
                    "Keep old answer",
                ),
                (
                    "recent-trace",
                    "assistant",
                    "recent-run",
                    datetime.now(UTC).isoformat(),
                    '[{"stage":"planning","steps":["private-recent-canary"]}]',
                    "Keep recent answer",
                ),
            ],
        )
        db.executemany(
            "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "legacy",
                    "drive_read_file",
                    '{"query":"private-request-canary"}',
                    '{"text":"private-document-canary"}',
                    "private-error-canary",
                ),
                (
                    "current",
                    "gmail_read_thread",
                    '{"argument_count": 1}',
                    '{"output_type":"GmailThread","field_count":2}',
                    None,
                ),
                (
                    "task",
                    "agent_task",
                    '{"session_id":"operation-metadata"}',
                    '{"answer_characters":10}',
                    None,
                ),
            ],
        )
    settings = Settings(
        _env_file=None, app_secret="test-only-secret-that-is-long-enough"
    )
    dry_run = backup_and_scrub(database, backup, settings, apply=False)
    assert dry_run["legacy_rows"] == 1
    assert dry_run["trace_rows"] == 2
    assert not backup.exists()

    with patch("scripts.scrub_audit_metadata.subprocess.run") as run:
        run.side_effect = [
            SimpleNamespace(stdout="DESKTOP\\Owner"),
            SimpleNamespace(stdout="DESKTOP\\Owner"),
            SimpleNamespace(stdout=""),
        ]
        outcome = backup_and_scrub(database, backup, settings, apply=True)
        assert run.call_count == (3 if os.name == "nt" else 0)
    assert outcome["changed_rows"] == 3
    assert backup.exists()
    assert b"private-document-canary" not in backup.read_bytes()
    with sqlite3.connect(database) as db:
        legacy = db.execute(
            "SELECT arguments_json, result_json, error_message FROM audit_events WHERE id='legacy'"
        ).fetchone()
        task = db.execute(
            "SELECT arguments_json FROM audit_events WHERE id='task'"
        ).fetchone()
        assert legacy == (
            '{"legacy_values_removed":true}',
            '{"legacy_values_removed":true}',
            None,
        )
        assert task == ('{"session_id":"operation-metadata"}',)
        traces = db.execute(
            "SELECT id, trace_json, content FROM messages ORDER BY id"
        ).fetchall()
        assert traces[0] == ("old-trace", "[]", "Keep old answer")
        assert "private-recent-canary" not in traces[1][1]
        assert "step_count" in traces[1][1]
        assert traces[1][2] == "Keep recent answer"
    assert backup_and_scrub(database, tmp_path / "unused.fernet", settings, apply=True)[
        "changed_rows"
    ] == 0

    restore_to_new_path(backup, restored, settings)
    with sqlite3.connect(restored) as db:
        raw = db.execute("SELECT result_json FROM audit_events WHERE id='legacy'").fetchone()
        assert "private-document-canary" in raw[0]
        raw_trace = db.execute(
            "SELECT trace_json FROM messages WHERE id='recent-trace'"
        ).fetchone()
        assert "private-recent-canary" in raw_trace[0]


def test_windows_backup_refuses_non_owner_identity(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows ACL policy")
    database = tmp_path / "audit.db"
    backup = tmp_path / "audit.db.fernet"
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE audit_events (id TEXT PRIMARY KEY, tool_name TEXT, "
            "arguments_json TEXT, result_json TEXT, error_message TEXT)"
        )
        db.execute(
            "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?)",
            ("raw", "drive_read_file", '{"file":"private"}', '{}', None),
        )
    settings = Settings(_env_file=None, app_secret="test-only-secret-that-is-long-enough")
    with patch("scripts.scrub_audit_metadata.subprocess.run") as run:
        run.side_effect = [
            SimpleNamespace(stdout="DESKTOP\\CodexSandboxOffline"),
            SimpleNamespace(stdout="DESKTOP\\Owner"),
        ]
        with pytest.raises(PermissionError, match="repository owner"):
            backup_and_scrub(database, backup, settings, apply=True)
    assert not backup.exists()
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT arguments_json FROM audit_events").fetchone() == (
            '{"file":"private"}',
        )
