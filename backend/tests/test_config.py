from pathlib import Path

from app.core.config import PROJECT_ROOT, Settings


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
