import json
from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

from app.tools.drive import _translate_http_error


@pytest.mark.parametrize(
    ("status", "reason", "code", "retryable"),
    [
        (400, "badRequest", "google_drive_invalid_query", False),
        (401, "authError", "google_drive_401", False),
        (403, "insufficientFilePermissions", "google_drive_permission_denied", False),
        (403, "insufficientPermissions", "google_drive_permission_denied", False),
        (403, "appNotAuthorizedToFile", "google_drive_permission_denied", False),
        (403, "rateLimitExceeded", "google_drive_rate_limited", True),
        (403, "userRateLimitExceeded", "google_drive_rate_limited", True),
        (403, "dailyLimitExceeded", "google_drive_rate_limited", False),
        (403, "accessNotConfigured", "google_drive_misconfigured", False),
        (403, "domainPolicy", "google_drive_misconfigured", False),
        (403, "unknownReason", "google_drive_403", False),
        (404, "notFound", "google_drive_404", False),
        (429, "unknownReason", "google_drive_429", True),
        (503, "backendError", "google_drive_503", True),
    ],
)
def test_provider_reason_separates_access_quota_and_query(status, reason, code, retryable):
    exc = HttpError(
        SimpleNamespace(status=status, reason="private-provider-message"),
        json.dumps(
            {"error": {"errors": [{"reason": reason}], "message": "private-file-id"}}
        ).encode(),
    )
    result = _translate_http_error(exc)
    assert result.code == code
    assert result.retryable is retryable
    assert "private" not in str(result)


@pytest.mark.parametrize("body", [b"not-json", b"null", b"[]", b'{"error":null}'])
def test_malformed_provider_error_is_safe(body):
    exc = HttpError(SimpleNamespace(status=403, reason="private-provider-message"), body)
    result = _translate_http_error(exc)
    assert result.code == "google_drive_403"
    assert not result.retryable
    assert "private" not in str(result)
