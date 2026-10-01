"""Cấu hình tập trung của ứng dụng.

Mọi secret đều đi qua biến môi trường. Việc gom cấu hình vào một nơi giúp người mới
dễ kiểm tra và giúp test có thể thay giá trị mà không sửa code nghiệp vụ.
"""

import ipaddress
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Chỉ cho phép các model Gemini đã được kiểm thử với contract của Veridra.
# Danh sách này phải khớp với lựa chọn hiển thị ở frontend và local_config.py.
APPROVED_GEMINI_MODELS = frozenset(
    {"gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.8-flash"}
)
GEMINI_HTTP_TIMEOUT_MS: int = 15_000


def assert_release_configuration(settings: "Settings") -> None:
    """Refuse an accidentally exposed development or unconfigured beta server.

    This guard runs before database initialization and never logs secret values.
    It supplements, rather than replaces, proxy/TLS and deployment checks.
    """

    local = settings.is_local_environment
    public = urlsplit(settings.public_base_url)
    if local:
        if public.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Development mode requires a loopback public URL")
        return
    if not settings.beta_invited_emails:
        raise ValueError("Closed beta requires invited email addresses")
    normalized_invites = {
        address.strip().casefold() for address in settings.beta_invited_emails
    }
    if len(normalized_invites) != len(settings.beta_invited_emails):
        raise ValueError("Closed beta invite list must not contain duplicates")
    if len(normalized_invites) > 4:
        raise ValueError("Closed beta supports at most four invited users")
    if any(
        not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address)
        for address in settings.beta_invited_emails
    ):
        raise ValueError("Closed beta invite list contains an invalid address")
    owner_email = settings.beta_owner_email.strip().casefold()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", owner_email):
        raise ValueError("Closed beta requires an explicit owner email")
    if owner_email not in normalized_invites:
        raise ValueError("Closed beta owner must be in the invite list")
    if (
        settings.app_secret == "local-development-change-me-before-sharing"
        or len(settings.app_secret) < 32
    ):
        raise ValueError("Closed beta requires a non-default APP_SECRET of at least 32 chars")
    for field in ("public_base_url", "frontend_origin", "google_redirect_uri"):
        value = urlsplit(getattr(settings, field))
        if value.scheme != "https" or not value.hostname or value.username or value.password:
            raise ValueError(f"Closed beta requires a valid HTTPS {field}")
    if urlsplit(settings.google_redirect_uri).hostname != public.hostname:
        raise ValueError("Google redirect host must match the public app host")
    if settings.enable_demo_login:
        raise ValueError("Closed beta cannot enable demo login")
    if not settings.oauth_is_configured:
        raise ValueError("Closed beta requires a Google OAuth client configuration")
    if len(settings.metrics_bearer_token) < 32:
        raise ValueError("Closed beta requires a metrics bearer token of at least 32 chars")
    if (
        settings.scheduler_bearer_token is None
        or len(settings.scheduler_bearer_token.get_secret_value()) < 32
    ):
        raise ValueError("Closed beta requires a scheduler bearer token of at least 32 chars")
    quota_profile = os.environ.get("DRIVE_AGENT_QUOTA_PROFILE", "conservative").strip().lower()
    if quota_profile != "conservative":
        raise ValueError("Closed beta requires the conservative API quota profile")
    database_url = settings.resolved_database_url
    if database_url.startswith("sqlite+aiosqlite:///"):
        if settings.storage_backend != "local":
            raise ValueError("SQLite profile requires local object storage")
        if settings.state_dir is None or not settings.state_dir.is_absolute():
            raise ValueError("SQLite beta requires an absolute persistent STATE_DIR")
        state_root = settings.resolved_state_dir
        db_path = Path(database_url.split("///", maxsplit=1)[1])
        if not db_path.is_relative_to(state_root):
            raise ValueError("SQLite beta database must reside inside STATE_DIR")
        if not settings.resolved_qdrant_path.is_relative_to(state_root):
            raise ValueError("SQLite beta Qdrant path must reside inside STATE_DIR")
        return

    from sqlalchemy.engine import make_url

    database = make_url(database_url)
    relational_secret = settings.relational_state_url
    if database.drivername != "postgresql+psycopg" or relational_secret is None:
        raise ValueError("Cloud beta requires PostgreSQL for app data and durable state")
    relational = make_url(relational_secret.get_secret_value())
    if relational.drivername != "postgresql+psycopg" or (
        database.host,
        database.port,
        database.database,
    ) != (relational.host, relational.port, relational.database):
        raise ValueError("App data and durable state must use the same PostgreSQL project")
    if settings.storage_backend != "supabase":
        raise ValueError("Cloud beta requires private Supabase object storage")
    if settings.orchestrator_backend != "adk":
        raise ValueError("Cloud beta release profile requires the verified ADK runtime")
    storage_url = urlsplit(settings.supabase_url)
    if storage_url.scheme != "https" or not storage_url.hostname:
        raise ValueError("Cloud beta requires a valid HTTPS Supabase URL")
    if settings.supabase_service_role_key is None:
        raise ValueError("Cloud beta requires a backend-only Supabase service role key")
    if not (
        settings.google_oauth_client_id.strip()
        and settings.google_oauth_client_secret is not None
    ):
        raise ValueError("Cloud beta requires OAuth client credentials in environment secrets")


def _from_project_root(path: Path | str) -> Path:
    """Giữ path tuyệt đối; path tương đối luôn được hiểu từ root repository."""

    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()


class Settings(BaseSettings):
    """Các biến môi trường có tiền tố ``DRIVE_AGENT_``."""

    model_config = SettingsConfigDict(
        env_prefix="DRIVE_AGENT_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    app_name: str = "Veridra"
    orchestrator_backend: Literal["langgraph", "adk", "compiler"] = "adk"
    no_paid_fallback: Literal[True] = True
    environment: str = "development"
    local_timezone: str = "Asia/Bangkok"
    pdf_ocr_enabled: bool = False
    pdf_tesseract_binary: str = ""
    pdf_pdftoppm_binary: str = ""
    pdf_tessdata_dir: str = ""
    app_secret: str = "local-development-change-me-before-sharing"
    log_level: str = "INFO"
    # Optional metadata-only local Langfuse; never a cloud telemetry endpoint.
    langfuse_local_url: str = ""
    langfuse_credentials_file: Path | None = None
    container_local_gateway: str = ""

    @field_validator("container_local_gateway")
    @classmethod
    def validate_container_gateway(cls, value: str) -> str:
        if value:
            address = ipaddress.ip_address(value)
            if address.version != 4 or not address.is_private or address.is_loopback:
                raise ValueError("Container gateway must be one explicit private IPv4 address")
        return value

    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/drive_agent.db",
        repr=False,
    )
    # Optional portable state adapter, enabled service by service during migration.
    # This alone does NOT make ephemeral hosting safe for the rest of the product.
    relational_state_url: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        from sqlalchemy.engine import make_url

        try:
            url = make_url(value)
        except Exception as exc:
            raise ValueError("Invalid app database configuration") from exc
        if url.drivername not in {"sqlite+aiosqlite", "postgresql+psycopg"}:
            raise ValueError("App database requires sqlite+aiosqlite or postgresql+psycopg")
        if url.drivername == "postgresql+psycopg" and (
            not url.host or not url.database or url.query.get("sslmode") != "require"
        ):
            raise ValueError("Cloud app database requires a host and sslmode=require")
        return value

    @field_validator("relational_state_url")
    @classmethod
    def validate_relational_state_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            from sqlalchemy.engine import make_url

            try:
                url = make_url(value.get_secret_value())
            except Exception as exc:
                raise ValueError("Invalid relational state connection configuration") from exc
            if url.drivername not in {"sqlite", "postgresql+psycopg"}:
                raise ValueError("Relational state requires sqlite or postgresql+psycopg")
            if url.drivername == "postgresql+psycopg" and (
                not url.host or not url.database or url.query.get("sslmode") != "require"
            ):
                raise ValueError("Cloud state requires a database host and sslmode=require")
        return value

    qdrant_path: str = "./data/qdrant"
    # Explicit persistent-volume root for sidecar SQLite databases in beta.
    state_dir: Path | None = None
    storage_backend: Literal["local", "supabase"] = "local"
    supabase_url: str = ""
    supabase_service_role_key: SecretStr | None = None
    supabase_storage_bucket: str = "veridra-private"

    @field_validator("supabase_storage_bucket")
    @classmethod
    def validate_storage_bucket(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,62}", value):
            raise ValueError("Storage bucket must be a lowercase DNS-style name")
        return value

    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-3.5-flash-lite"
    # Independent from Chat; no silent paid Search grounding fallback.
    gemini_web_research_model: Literal["gemini-2.5-flash"] = "gemini-2.5-flash"
    gemini_fallback_model: str = "gemini-3.8-flash"
    gemini_embedding_model: str = "gemini-embedding-2"

    google_oauth_client_file: Path = Path("./client_secret.json")
    google_oauth_client_id: str = ""
    google_oauth_client_secret: SecretStr | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_drive_scopes: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.compose",
            "https://www.googleapis.com/auth/calendar.readonly",
        ]
    )

    frontend_origin: str = "http://localhost:5173"
    public_base_url: str = "http://localhost:8000"
    max_download_mb: int = 25
    tool_timeout_seconds: int = 45
    enable_demo_login: bool = False
    # Closed beta is fail-closed outside local development. Configure the
    # invited addresses before exposing the app; never infer access from an
    # existing account or an OAuth grant alone.
    beta_invited_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)
    beta_owner_email: str = ""
    # A separate owner decision is required before invited beta users can make
    # external Gmail/Drive writes, even after the normal per-operation approval.
    beta_allow_external_writes: bool = False
    web_research_max_sources: int = 12
    report_export_max_characters: int = 100_000
    metrics_bearer_token: str = ""
    scheduler_bearer_token: SecretStr | None = None
    gemini_input_usd_per_million: float = Field(default=0.0, ge=0)
    gemini_output_usd_per_million: float = Field(default=0.0, ge=0)

    @property
    def is_local_environment(self) -> bool:
        return self.environment.casefold() in {"local", "development"}

    # Remote Monitoring & Alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    remote_email_monitor_enabled: bool = False
    remote_email_poll_interval_seconds: int = 180

    @field_validator("google_drive_scopes", mode="before")
    @classmethod
    def parse_scopes(cls, value: object) -> object:
        """Cho phép người dùng viết scopes dạng chuỗi phân tách bằng dấu phẩy."""

        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("beta_invited_emails", mode="before")
    @classmethod
    def parse_beta_invites(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().casefold() for item in value.split(",") if item.strip()]
        return value

    def beta_email_allowed(self, email: str) -> bool:
        if self.environment.casefold() in {"local", "development"}:
            return True
        return email.strip().casefold() in {
            item.strip().casefold() for item in self.beta_invited_emails
        }

    def beta_identity_allowed(self, email: str, role: str) -> bool:
        if not self.beta_email_allowed(email):
            return False
        if self.is_local_environment:
            return True
        return (
            role != "super_admin"
            or email.strip().casefold() == self.beta_owner_email.strip().casefold()
        )

    @property
    def data_dir(self) -> Path:
        """Trả về thư mục dữ liệu và đảm bảo nó tồn tại."""

        if self.state_dir is not None:
            target = self.resolved_state_dir
            target.mkdir(parents=True, exist_ok=True)
            return target
        database_url = self.resolved_database_url
        if database_url.startswith("sqlite") and "///" in database_url:
            db_path = Path(database_url.split("///", maxsplit=1)[1])
            target = db_path.parent
        else:
            target = PROJECT_ROOT / "data"
        target.mkdir(parents=True, exist_ok=True)
        return target

    @property
    def resolved_database_url(self) -> str:
        """Chuẩn hóa SQLite URL để không phụ thuộc current working directory."""

        if not self.database_url.startswith("sqlite") or "///" not in self.database_url:
            return self.database_url
        prefix, raw_path = self.database_url.split("///", maxsplit=1)
        resolved_path = _from_project_root(raw_path)
        return f"{prefix}///{resolved_path.as_posix()}"

    @property
    def framework_session_database_url(self) -> str:
        """Keep ADK framework tables private while canonical chat stays portable."""

        if not self.resolved_database_url.startswith("postgresql+psycopg"):
            path = (self.data_dir / "adk_sessions.db").resolve().as_posix()
            return f"sqlite+aiosqlite:///{path}"
        from sqlalchemy.engine import make_url

        url = make_url(self.resolved_database_url)
        query = dict(url.query)
        query["options"] = "-csearch_path=veridra_private"
        return url.set(query=query).render_as_string(hide_password=False)

    @property
    def resolved_qdrant_path(self) -> Path:
        return _from_project_root(self.qdrant_path)

    @property
    def resolved_state_dir(self) -> Path:
        return _from_project_root(self.state_dir or PROJECT_ROOT / "data")

    @property
    def frontend_dist(self) -> Path:
        """UI đã build nằm cạnh backend, không nằm bên trong backend."""

        return PROJECT_ROOT / "frontend" / "dist"

    @property
    def resolved_google_oauth_client_file(self) -> Path:
        return _from_project_root(self.google_oauth_client_file)

    @property
    def oauth_is_configured(self) -> bool:
        """Chỉ báo cấu hình, không đọc hoặc làm lộ nội dung file OAuth."""

        return self.resolved_google_oauth_client_file.exists() or bool(
            self.google_oauth_client_id.strip() and self.google_oauth_client_secret is not None
        )

    @property
    def oauth_client_config(self) -> dict | None:
        if not self.google_oauth_client_id.strip() or self.google_oauth_client_secret is None:
            return None
        return {
            "web": {
                "client_id": self.google_oauth_client_id.strip(),
                "client_secret": self.google_oauth_client_secret.get_secret_value(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.google_redirect_uri],
            }
        }

    @property
    def gemini_is_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cache Settings để toàn ứng dụng dùng chung một cấu hình nhất quán."""

    settings = Settings()
    _ = settings.data_dir
    return settings
