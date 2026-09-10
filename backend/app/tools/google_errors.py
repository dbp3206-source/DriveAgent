"""Safe, actionable classifications for Google Workspace API failures."""

from googleapiclient.errors import HttpError

from app.tools.contracts import ToolError


def workspace_http_error(exc: HttpError, service_label: str) -> ToolError:
    """Map provider details to a user-safe code without exposing headers or tokens."""

    detail = str(exc).casefold()
    if exc.resp.status == 403 and any(
        marker in detail
        for marker in ("accessnotconfigured", "service_disabled", "has not been used", "disabled")
    ):
        return ToolError(
            f"{service_label} API chưa được bật cho Google Cloud project này. "
            f"Hãy bật {service_label} API rồi tạo một bản duyệt mới; operation hiện tại "
            "không được gửi lại.",
            code=f"{service_label.casefold().replace(' ', '_')}_api_disabled",
        )
    if exc.resp.status in {401, 403}:
        return ToolError(
            f"Google chưa cho phép thao tác {service_label}. Hãy kết nối lại quyền "
            "Workspace bằng đúng tài khoản, sau đó tạo một bản duyệt mới.",
            code="google_workspace_permission_denied",
        )
    if exc.resp.status == 429:
        return ToolError(
            f"{service_label} đang giới hạn tần suất. Không tự gửi lại thao tác ghi; "
            "hãy kiểm tra trạng thái trước.",
            code="google_workspace_rate_limited",
        )
    return ToolError(
        f"{service_label} chưa xác minh hoàn tất. Kiểm tra trạng thái trước khi tạo yêu cầu mới.",
        code="google_workspace_error",
    )
