"""Run the real app against disposable, credential-free local QA state."""

import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.core import config  # noqa: E402

state = ROOT / "tmp" / "production-ui-20261013"
state.mkdir(parents=True, exist_ok=True)
profile = config.Settings(
    _env_file=None,
    _env_prefix="VERIDRA_ISOLATED_UI_QA_",
    environment="development",
    public_base_url="http://127.0.0.1:8003",
    frontend_origin="http://127.0.0.1:5175",
    google_redirect_uri="http://127.0.0.1:8003/api/auth/google/callback",
    database_url=f"sqlite+aiosqlite:///{(state / 'app.db').as_posix()}",
    state_dir=state,
    qdrant_path=str(state / "qdrant"),
    google_oauth_client_file=state / "not-configured.json",
    enable_demo_login=True,
)
assert not profile.gemini_is_configured and not profile.oauth_is_configured
assert profile.relational_state_url is None and profile.storage_backend == "local"
config.get_settings = lambda: profile

# Defense in depth: the QA process cannot resolve external provider hosts.
original_getaddrinfo = socket.getaddrinfo


def loopback_only(host, *args, **kwargs):
    if host not in {None, "localhost", "127.0.0.1", "::1", b"localhost", b"127.0.0.1"}:
        raise OSError("External networking disabled for isolated UI QA")
    return original_getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = loopback_only

import uvicorn  # noqa: E402

from app import main  # noqa: E402

# Retention must not touch the user's existing local backup directory.
main.PROJECT_ROOT = state / "maintenance"

if __name__ == "__main__":
    uvicorn.run(main.app, host="127.0.0.1", port=8003)
