"""Opaque keyset cursors shared by growing history endpoints."""

import base64
import json
from datetime import datetime


def encode_cursor(value: datetime, row_id: str) -> str:
    raw = json.dumps({"at": value.isoformat(), "id": row_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(value: str | None) -> tuple[datetime, str] | None:
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        at = datetime.fromisoformat(payload["at"])
        row_id = str(payload["id"])
        if not row_id:
            raise ValueError
        return at, row_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid cursor") from exc
