from app.core.config import Settings
from app.core.security import decrypt_json, encrypt_json, redact


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
