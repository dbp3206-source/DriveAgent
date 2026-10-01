from pathlib import Path

import pytest

from app.core.config import (
    APPROVED_GEMINI_MODELS,
    PROJECT_ROOT,
    Settings,
    assert_release_configuration,
)


def test_portable_state_url_requires_explicit_driver_and_tls():
    from pydantic import ValidationError

    valid = "postgresql+psycopg://user:private-password@db.example.com/veridra?sslmode=require"
    settings = Settings(_env_file=None, relational_state_url=valid)
    assert "private-password" not in repr(settings)
    assert settings.relational_state_url.get_secret_value() == valid
    for invalid in (
        "postgresql+psycopg://user:password@db.example.com/veridra",
        "mysql://user:password@db.example.com/veridra",
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, relational_state_url=invalid)


def _beta_settings(**overrides: object) -> Settings:
    values = {
        "environment": "production",
        "app_secret": "a" * 48,
        "beta_invited_emails": ["invited@example.com"],
        "beta_owner_email": "invited@example.com",
        "state_dir": PROJECT_ROOT / "data",
        "public_base_url": "https://app.example.com",
        "frontend_origin": "https://app.example.com",
        "google_redirect_uri": "https://app.example.com/api/auth/google/callback",
        "google_oauth_client_id": "client.apps.googleusercontent.com",
        "google_oauth_client_secret": "oauth-test-secret",
        "metrics_bearer_token": "m" * 48,
        "scheduler_bearer_token": "s" * 48,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_closed_beta_configuration_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("DRIVE_AGENT_QUOTA_PROFILE", raising=False)
    assert_release_configuration(_beta_settings())
    for override in (
        {"beta_invited_emails": []},
        {"beta_invited_emails": ["not-an-email"]},
        {"beta_invited_emails": ["invited@example.com", "INVITED@example.com"]},
        {
            "beta_invited_emails": [
                "invited@example.com",
                "two@example.com",
                "three@example.com",
                "four@example.com",
                "five@example.com",
            ]
        },
        {"beta_owner_email": ""},
        {"beta_owner_email": "outsider@example.com"},
        {"app_secret": "local-development-change-me-before-sharing"},
        {"app_secret": "short"},
        {"public_base_url": "http://app.example.com"},
        {"frontend_origin": "http://app.example.com"},
        {"google_redirect_uri": "http://app.example.com/api/auth/google/callback"},
        {"google_redirect_uri": "https://other.example.com/callback"},
        {"enable_demo_login": True},
        {"metrics_bearer_token": "short"},
        {"scheduler_bearer_token": "short"},
        {"state_dir": None},
        {"state_dir": Path("relative-data")},
        {"database_url": "sqlite+aiosqlite:///./other/drive_agent.db"},
        {"qdrant_path": "./other/qdrant"},
        {"database_url": "postgresql+asyncpg://example.invalid/veridra"},
    ):
        with pytest.raises(ValueError):
            assert_release_configuration(_beta_settings(**override))
    monkeypatch.setenv("DRIVE_AGENT_QUOTA_PROFILE", "relaxed")
    with pytest.raises(ValueError, match="conservative"):
        assert_release_configuration(_beta_settings())


def test_closed_beta_cloud_profile_requires_one_private_postgres_project(monkeypatch) -> None:
    monkeypatch.delenv("DRIVE_AGENT_QUOTA_PROFILE", raising=False)
    database = (
        "postgresql+psycopg://user:private-password@db.example.com/veridra?sslmode=require"
    )
    cloud = _beta_settings(
        state_dir=None,
        database_url=database,
        relational_state_url=database,
        storage_backend="supabase",
        supabase_url="https://project-ref.supabase.co",
        supabase_service_role_key="service-role-test-value",
    )
    assert_release_configuration(cloud)
    assert "service-role-test-value" not in repr(cloud)
    from sqlalchemy.engine import make_url

    assert make_url(cloud.framework_session_database_url).query["options"] == (
        "-csearch_path=veridra_private"
    )
    assert "private-password" in cloud.framework_session_database_url
    for override in (
        {"relational_state_url": None},
        {
            "relational_state_url": (
                "postgresql+psycopg://user:private-password@other.example.com/"
                "veridra?sslmode=require"
            )
        },
        {"storage_backend": "local"},
        {"supabase_url": "http://project-ref.supabase.co"},
        {"supabase_service_role_key": None},
        {"orchestrator_backend": "langgraph"},
        {"google_oauth_client_id": ""},
        {"google_oauth_client_secret": None},
    ):
        values = {
            "state_dir": None,
            "database_url": database,
            "relational_state_url": database,
            "storage_backend": "supabase",
            "supabase_url": "https://project-ref.supabase.co",
            "supabase_service_role_key": "service-role-test-value",
            **override,
        }
        with pytest.raises(ValueError):
            assert_release_configuration(_beta_settings(**values))


def test_development_configuration_rejects_public_url() -> None:
    assert_release_configuration(
        Settings(_env_file=None, environment="development", public_base_url="http://localhost:8000")
    )
    with pytest.raises(ValueError, match="loopback"):
        assert_release_configuration(
            Settings(_env_file=None, environment="development", public_base_url="https://app.example.com")
        )
    assert Settings(_env_file=None, environment="staging").is_local_environment is False
    assert Settings(_env_file=None, environment="production").is_local_environment is False


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
    assert settings.app_name == "Veridra"
    assert settings.frontend_dist == PROJECT_ROOT / "frontend/dist"
    assert settings.gemini_chat_model == "gemini-3.5-flash-lite"
    assert settings.gemini_fallback_model == "gemini-3.8-flash"
    assert settings.gemini_embedding_model == "gemini-embedding-2"
    assert "https://www.googleapis.com/auth/drive.file" in settings.google_drive_scopes


def test_approved_gemini_models_match_product_contract() -> None:
    assert APPROVED_GEMINI_MODELS == {
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
    }
    assert "gemini-3.6-flash" in APPROVED_GEMINI_MODELS


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


def test_cloud_oauth_client_secret_is_not_exposed_in_settings_repr(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        google_oauth_client_file=tmp_path / "missing.json",
        google_oauth_client_id="client.apps.googleusercontent.com",
        google_oauth_client_secret="oauth-private-value",
        google_redirect_uri="https://app.example.com/api/auth/google/callback",
    )
    assert settings.oauth_is_configured is True
    assert settings.oauth_client_config["web"]["client_secret"] == "oauth-private-value"
    assert "oauth-private-value" not in repr(settings)


def test_database_password_is_not_exposed_in_settings_repr() -> None:
    settings = Settings(
        _env_file=None,
        database_url=(
            "postgresql+psycopg://user:private-password@db.example.com/"
            "veridra?sslmode=require"
        ),
    )
    assert "private-password" not in repr(settings)
