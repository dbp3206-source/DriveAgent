"""Credential-free regression run; never load the user's .env or app database."""

import os
import socket
import sys
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.core import config  # noqa: E402

for name in list(os.environ):
    if name.startswith("DRIVE_AGENT_"):
        del os.environ[name]
config.Settings.model_config["env_file"] = None
state = ROOT / "tmp" / f"offline-regression-{uuid4().hex}"
state.mkdir(parents=True, exist_ok=False)
profile = config.Settings(
    _env_file=None,
    state_dir=state,
    database_url=f"sqlite+aiosqlite:///{(state / 'app.db').as_posix()}",
    qdrant_path=str(state / "qdrant"),
    google_oauth_client_file=state / "not-configured.json",
)
config.get_settings = lru_cache(maxsize=1)(lambda: profile)

original_getaddrinfo = socket.getaddrinfo


def loopback_only(host, *args, **kwargs):
    if host not in {None, "localhost", "127.0.0.1", "::1", b"localhost", b"127.0.0.1"}:
        raise OSError("External networking disabled for offline regression")
    return original_getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = loopback_only
os.chdir(ROOT / "backend")

import pytest  # noqa: E402

if __name__ == "__main__":
    qa = ROOT / "design-work" / "production-20261013" / "qa" / "validation"
    qa.mkdir(parents=True, exist_ok=True)
    sys.exit(pytest.main([
        "tests", "-q", "-p", "no:cacheprovider",
        "--basetemp", str(state / "pytest"),
        "--junitxml", str(qa / "backend-regression.xml"),
        *sys.argv[1:],
    ]))
