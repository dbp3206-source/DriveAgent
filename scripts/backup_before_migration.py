"""Offline encrypted state/code snapshot. Never prints the app secret.

Archive key is derived from the existing owner-held APP_SECRET. Keep that secret
separately; changing it without retaining the original makes these archives
unreadable. The output directory must already have an owner-only OS ACL.
"""

import hashlib
import io
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def run():
    from app.core.config import get_settings
    from state_archive import _EncryptedWriter, backup_state

    settings = get_settings()
    if len(settings.app_secret) < 32 or settings.app_secret.startswith("local-development"):
        raise ValueError("Owner-held strong APP_SECRET required")
    folder = ROOT / ".local-backups" / "migration-20260930"
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("Create owner-only archive directory first")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = folder / f"state-pre-migration-{stamp}.vrd"
    excluded = frozenset({"grafana", "grafana-logs", "grafana-plugins", "prometheus",
                           "prometheus-native", "otel", "logs", "test_tmp", "qa-final",
                           "qa-qdrant", "qa-pdf-renders", "qa-drive-agent.db"})
    count = backup_state(settings.data_dir, archive, settings.app_secret,
                         excluded_top_dirs=excluded)
    source = io.BytesIO()
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        files = []
        for directory in ("backend/app", "frontend/src", "docs", ".github/workflows"):
            files.extend(path for path in (ROOT / directory).rglob("*")
                         if path.is_file() and "__pycache__" not in path.parts
                         and path.suffix not in {".pyc", ".pyo"})
        files.extend(ROOT / name for name in ("README.md", "Dockerfile", ".env.example",
                     "backend/pyproject.toml", "backend/uv.lock", "frontend/package-lock.json")
                     if (ROOT / name).is_file())
        for path in sorted(files):
            bundle.write(path, path.relative_to(ROOT).as_posix())
    code_archive = folder / f"code-pre-migration-{stamp}.vrd"
    with code_archive.open("xb") as raw:
        writer = _EncryptedWriter(raw, settings.app_secret)
        writer.write(source.getvalue())
        writer.finish()
    return {"state_archive": str(archive), "state_files": count,
            "state_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "code_archive": str(code_archive), "code_files": len(files),
            "excluded_operational_and_test_stores": sorted(excluded),
            "retention_days": 30, "restore_verified": False}


if __name__ == "__main__":
    print(json.dumps(run()))
