from pathlib import Path

from app.core.config import PROJECT_ROOT, Settings


def test_scopes_from_dotenv_are_comma_separated(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DRIVE_AGENT_GOOGLE_DRIVE_SCOPES=openid,email,profile,"
        "https://www.googleapis.com/auth/drive.readonly\n",
        encoding="utf-8-sig",
    )
    settings = Settings(_env_file=env_file)
    assert settings.google_drive_scopes == [
        "openid", "email", "profile", "https://www.googleapis.com/auth/drive.readonly"
    ]


def test_built_ui_path_is_inside_frontend() -> None:
    assert Settings(_env_file=None).frontend_dist == PROJECT_ROOT / "frontend/dist"


def test_relative_local_paths_are_resolved_from_repository_root() -> None:
    settings = Settings(
        database_url="sqlite+aiosqlite:///./data/example.db",
        qdrant_path="./data/qdrant-example",
        google_oauth_client_file=Path("./client_secret.json"),
    )

    database_path = Path(settings.resolved_database_url.split("///", maxsplit=1)[1])
    assert database_path == (PROJECT_ROOT / "data/example.db").resolve()
    assert settings.resolved_qdrant_path == (PROJECT_ROOT / "data/qdrant-example").resolve()
    assert settings.resolved_google_oauth_client_file == (
        PROJECT_ROOT / "client_secret.json"
    ).resolve()
