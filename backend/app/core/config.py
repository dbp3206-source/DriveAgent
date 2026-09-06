"""Cấu hình tập trung của ứng dụng.

Mọi secret đều đi qua biến môi trường. Việc gom cấu hình vào một nơi giúp người mới
dễ kiểm tra và giúp test có thể thay giá trị mà không sửa code nghiệp vụ.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


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

    app_name: str = "DriveAgent"
    environment: str = "development"
    app_secret: str = "local-development-change-me-before-sharing"
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./data/drive_agent.db"
    qdrant_path: str = "./data/qdrant"

    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-2"

    google_oauth_client_file: Path = Path("./client_secret.json")
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_drive_scopes: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
    )

    frontend_origin: str = "http://localhost:5173"
    public_base_url: str = "http://localhost:8000"
    max_download_mb: int = 25
    tool_timeout_seconds: int = 45
    enable_demo_login: bool = False

    @field_validator("google_drive_scopes", mode="before")
    @classmethod
    def parse_scopes(cls, value: object) -> object:
        """Cho phép người dùng viết scopes dạng chuỗi phân tách bằng dấu phẩy."""

        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def data_dir(self) -> Path:
        """Trả về thư mục dữ liệu và đảm bảo nó tồn tại."""

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
    def resolved_qdrant_path(self) -> Path:
        return _from_project_root(self.qdrant_path)

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

        return self.resolved_google_oauth_client_file.exists()

    @property
    def gemini_is_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cache Settings để toàn ứng dụng dùng chung một cấu hình nhất quán."""

    settings = Settings()
    _ = settings.data_dir
    return settings
