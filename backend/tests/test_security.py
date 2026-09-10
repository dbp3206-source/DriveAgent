import pytest

from app.core.config import Settings
from app.core.security import decrypt_json, encrypt_json, redact


@pytest.mark.parametrize(
    "text",
    [
        "api_key = FAKE_CANARY_NOT_A_SECRET",
        'request failed: {"refresh_token": "FAKE_CANARY_NOT_A_SECRET"}',
        "Authorization: Bearer FAKE_CANARY_NOT_A_SECRET",
        "Bearer FAKE_CANARY_NOT_A_SECRET",
        "password là fake password with spaces",
        "Cookie: session=FAKE_CANARY_NOT_A_SECRET",
        "-----BEGIN PRIVATE KEY-----\nFAKE_CANARY_NOT_A_SECRET",
    ],
)
def test_free_text_secrets_are_removed(text: str) -> None:
    assert redact({"result": [{"content": text}]}) == {
        "result": [{"content": "[REDACTED]"}],
    }


def test_secret_instructions_without_values_remain_readable() -> None:
    assert redact("Không lưu API key") == "Không lưu API key"


def test_encrypt_round_trip_and_ciphertext_does_not_contain_secret() -> None:
    settings = Settings(app_secret="a-secret-long-enough-for-tests")
    payload = {"access_token": "token-value", "nested": {"client_secret": "private"}}

    encrypted = encrypt_json(payload, settings)

    assert "token-value" not in encrypted
    assert decrypt_json(encrypted, settings) == payload


def test_redact_recursively_masks_sensitive_values() -> None:
    payload = {
        "query": "quarterly plan",
        "api_key": "secret",
        "nested": [{"Authorization": "Bearer abc"}],
    }

    assert redact(payload) == {
        "query": "quarterly plan",
        "api_key": "[REDACTED]",
        "nested": [{"Authorization": "[REDACTED]"}],
    }
