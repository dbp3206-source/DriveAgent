from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from google.auth.exceptions import RefreshError, TransportError

from app.auth import google_oauth
from app.tools.contracts import ToolAccessDeniedError, ToolError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,retryable",
    [(TransportError("token=private"), True), (RefreshError("token=private"), False)],
)
async def test_google_refresh_normalizes_errors_without_saving(monkeypatch, failure, retryable):
    credentials = SimpleNamespace(
        expired=True, refresh_token="test", refresh=Mock(side_effect=failure)
    )
    monkeypatch.setattr(google_oauth, "credentials_from_user", lambda *_: credentials)
    db = SimpleNamespace(commit=AsyncMock())
    with pytest.raises(ToolError) as caught:
        await google_oauth.refresh_and_store_if_needed(SimpleNamespace(), db, SimpleNamespace())
    assert caught.value.retryable is retryable
    assert "private" not in str(caught.value)
    if not retryable:
        assert isinstance(caught.value, ToolAccessDeniedError)
    db.commit.assert_not_awaited()
