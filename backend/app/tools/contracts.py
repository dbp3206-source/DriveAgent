"""Hợp đồng kiểu dữ liệu cho Tool Registry."""

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import User

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(slots=True)
class ToolContext:
    request_id: str
    user: User
    db: AsyncSession
    settings: Settings
    source: str = "api"
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolHandler(Protocol[InputT, OutputT]):
    async def __call__(self, payload: InputT, context: ToolContext) -> OutputT: ...


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: ToolHandler[Any, Any]
    required_permissions: set[str]
    required_oauth_scopes: set[str] = field(default_factory=set)
    rate_limit_per_minute: int = 30
    timeout_seconds: float | None = None
    max_attempts: int = 3
    # Server-owned policy: tool is available only after a deliberate UI/API action.
    requires_user_action: bool = False


class ToolError(RuntimeError):
    """Lỗi có cấu trúc để registry quyết định retry hay trả về ngay."""

    def __init__(self, message: str, *, code: str = "tool_error", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ToolNotFoundError(ToolError):
    def __init__(self, name: str):
        super().__init__(f"Tool không tồn tại: {name}", code="tool_not_found")


class ToolAccessDeniedError(ToolError):
    def __init__(self, message: str):
        super().__init__(message, code="access_denied")


class ToolRateLimitError(ToolError):
    def __init__(self, message: str):
        super().__init__(message, code="rate_limited", retryable=False)
