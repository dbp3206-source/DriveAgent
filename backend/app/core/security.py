"""Tiện ích bảo mật dùng cho cookie, token OAuth và audit log."""

import base64
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|authorization)",
    re.IGNORECASE,
)

# Dùng cho nội dung tự do của Memory. Khác SENSITIVE_KEY, regex này chỉ chặn khi
# tên secret đi kèm dấu gán/câu mô tả giá trị, nên câu hướng dẫn như "không lưu API key"
# vẫn hợp lệ trong khi "api_key = abc" bị từ chối.
SENSITIVE_CONTENT = re.compile(
    r"\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|password|bearer)"
    r"\b\s*(?:is|là|[:=])\s*\S+",
    re.IGNORECASE,
)


def _fernet(settings: Settings) -> Fernet:
    """Dẫn xuất khóa Fernet ổn định từ app secret mà không lưu thêm khóa phụ."""

    digest = hashlib.sha256(settings.app_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_json(payload: Mapping[str, Any], settings: Settings) -> str:
    serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return _fernet(settings).encrypt(serialized).decode("ascii")


def decrypt_json(ciphertext: str, settings: Settings) -> dict[str, Any]:
    try:
        plaintext = _fernet(settings).decrypt(ciphertext.encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("Không thể giải mã credential. APP_SECRET có thể đã thay đổi.") from exc
    return json.loads(plaintext.decode("utf-8"))


def redact(value: Any) -> Any:
    """Che secret trước khi ghi audit, kể cả khi secret nằm trong object lồng nhau."""

    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    return value
