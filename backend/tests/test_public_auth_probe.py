"""The acceptance probe fails closed and never treats network failure as success."""

from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from scripts.qa_public_auth_boundaries import PATHS, check


@pytest.mark.parametrize("origin", [
    "http://example.com", "https://", "https://user:secret@example.com",
    "https://example.com/chat", "https://example.com?key=secret",
    "https://example.com/#/chat",
])
def test_invalid_origin_does_not_send_requests(origin):
    with patch("urllib.request.urlopen") as request:
        with pytest.raises(ValueError):
            check(origin)
        request.assert_not_called()


def test_unauthenticated_denials_are_passes():
    def denied(url, timeout):
        assert timeout == 20
        raise HTTPError(url, 401, "Unauthorized", Message(), None)

    with patch("urllib.request.urlopen", side_effect=denied) as request:
        result = check("https://example.com")
    assert result["passed"]
    assert len(result["checks"]) == len(PATHS)
    assert request.call_count == len(PATHS)
    assert result["model_calls"] == result["writes"] == 0


@pytest.mark.parametrize("failure", [
    URLError("unreachable"),
    HTTPError("https://example.com", 503, "Unavailable", Message(), None),
])
def test_outage_is_not_an_authentication_pass(failure):
    with patch("urllib.request.urlopen", side_effect=failure):
        result = check("https://example.com")
    assert not result["passed"]
    assert all(not row["passed"] for row in result["checks"])
