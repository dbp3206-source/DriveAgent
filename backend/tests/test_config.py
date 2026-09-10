from pathlib import Path

from app.core.config import PROJECT_ROOT, Settings


def test_scopes_from_dotenv_are_comma_separated(tmp_path, monkeypatch) -> None:
    # Process variables have higher priority than a supplied dotenv file. Remove
    # the developer machine value so this test verifies the file in isolation.
    monkeypatch.delenv("DRIVE_AGENT_GOOGLE_DRIVE_SCOPES", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DRIVE_AGENT_GOOGLE_DRIVE_SCOPES=openid,email,profile,"
        "https://www.googleapis.com/auth/drive.readonly\n",
        encoding="utf-8-sig",
    )
    settings = Settings(_env_file=env_file)
    assert settings.google_drive_scopes == [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/drive.readonly",
    ]


def test_built_ui_path_is_inside_frontend(monkeypatch) -> None:
    # _env_file=None skips dotenv but not process variables loaded by SDKs.
    # This test checks defaults independently of the user's selected live model.
    for key in (
        "GEMINI_CHAT_MODEL",
        "GEMINI_FALLBACK_MODEL",
        "GEMINI_EMBEDDING_MODEL",
        "GOOGLE_DRIVE_SCOPES",
    ):
        monkeypatch.delenv("DRIVE_AGENT_" + key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.frontend_dist == PROJECT_ROOT / "frontend/dist"
    assert settings.gemini_chat_model == "gemini-3.5-flash-lite"
    assert settings.gemini_fallback_model == "gemini-3.5-flash-lite"
    assert settings.gemini_embedding_model == "gemini-embedding-2"
    assert "https://www.googleapis.com/auth/drive.file" in settings.google_drive_scopes


def test_relative_local_paths_are_resolved_from_repository_root() -> None:
    settings = Settings(
        database_url="sqlite+aiosqlite:///./data/example.db",
        qdrant_path="./data/qdrant-example",
        google_oauth_client_file=Path("./client_secret.json"),
    )

    database_path = Path(settings.resolved_database_url.split("///", maxsplit=1)[1])
    assert database_path == (PROJECT_ROOT / "data/example.db").resolve()
    assert settings.resolved_qdrant_path == (PROJECT_ROOT / "data/qdrant-example").resolve()
    assert (
        settings.resolved_google_oauth_client_file
        == (PROJECT_ROOT / "client_secret.json").resolve()
    )
