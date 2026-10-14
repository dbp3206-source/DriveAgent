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

# Explicit, local-only notification QA: real queue/SQL/UI with delayed synthetic
# execution. Never load credentials or claim these fixtures are Gemini quality.
if "--mascot-check" in sys.argv:
    import asyncio

    from app.agent.orchestrator import AgentRunResult

    original_factory = main._new_orchestrator

    async def mascot_qa_factory(settings, registry):
        orchestrator = await original_factory(settings, registry)
        original_run = orchestrator.run

        async def delayed_run(*args, **kwargs):
            message = kwargs.get("user_message", "")
            if message.startswith("QA mascot:"):
                message = message.removeprefix("QA mascot:").strip()
                delay = 45 if message.startswith("chậm:") else 12
                await asyncio.sleep(delay)
                message = message.removeprefix("chậm:").strip()
                if message == "bản nháp":
                    return AgentRunResult(
                        answer="Bản nháp giả lập cần kiểm tra; chưa xác nhận số liệu.",
                        plan=[], citations=[],
                        trace=[{"stage": "output_contract", "status": "degraded",
                                "note": "Dữ liệu giả lập cho kiểm thông báo, không gọi mô hình."}],
                    )
                kwargs["user_message"] = message
            return await original_run(*args, **kwargs)

        orchestrator.run = delayed_run
        return orchestrator

    main._new_orchestrator = mascot_qa_factory

if __name__ == "__main__":
    uvicorn.run(main.app, host="127.0.0.1", port=8003)
