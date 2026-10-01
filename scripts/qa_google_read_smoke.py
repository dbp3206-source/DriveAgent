"""Read-only, privacy-minimal Google integration smoke through the running app.

The JSON result contains status/count/MIME metadata only: no mail subject, body,
sender, file name, Google ID, token, or signed session cookie is persisted.
"""

from __future__ import annotations

import base64
import importlib
import json
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import itsdangerous

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

Settings = importlib.import_module("app.core.config").Settings

DB = ROOT / "data" / "drive_agent.db"
BASE = "http://127.0.0.1:8000"


def _connected_owner_id() -> str:
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT id FROM users WHERE role='super_admin' AND is_active=1 "
            "AND encrypted_google_credentials IS NOT NULL "
            "AND length(encrypted_google_credentials)>0"
        ).fetchall()
    if len(rows) != 1:
        raise RuntimeError("Expected exactly one connected active owner")
    return str(rows[0][0])


def _cookie() -> str:
    settings = Settings()
    signer = itsdangerous.TimestampSigner(settings.app_secret)
    payload = base64.b64encode(json.dumps({"user_id": _connected_owner_id()}).encode())
    return signer.sign(payload).decode()


def _read(path: str, cookie: str, *, binary: bool = False):
    request = urllib.request.Request(
        BASE + path,
        headers={
            "Cookie": f"drive_agent_session={cookie}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        if binary:
            body = response.read()
            return {
                "status": response.status,
                "mime": response.headers.get_content_type(),
                "bytes": len(body),
            }
        return json.loads(response.read().decode("utf-8"))


def smoke_passed(result: dict[str, object]) -> bool:
    """A printed error must never be mistaken for a passing integration smoke."""

    if "gmail_error" in result or "drive_error" in result:
        return False
    if not isinstance(result.get("gmail_list"), dict) or not isinstance(
        result.get("drive_list"), dict
    ):
        return False
    if result["gmail_list"].get("status") != "ok" or result["drive_list"].get("status") != "ok":
        return False
    if result.get("gmail_threads", {}).get("status") != "ok":
        return False
    attachment = result.get("gmail_inline_attachment", {})
    if isinstance(attachment, dict) and attachment.get("status") not in {
        None,
        200,
        "not_present_in_bounded_sample",
    }:
        return False
    content = result.get("drive_content", {})
    return isinstance(content, dict) and all(
        isinstance(sample, dict) and sample.get("status") != "read_error"
        for sample in content.values()
    )


def main() -> None:
    cookie = _cookie()
    result: dict[str, object] = {"cloud_writes": 0}
    stage = "gmail_list"
    try:
        inbox = _read("/api/gmail/messages?query=in%3Ainbox&max_results=10", cookie)
        result["gmail_list"] = {
            "status": "ok",
            "returned": len(inbox.get("messages", [])),
            "estimate": inbox.get("total_found"),
        }
        threads = []
        messages = []
        for header in inbox.get("messages", [])[:10]:
            stage = "gmail_inbox_thread"
            thread_id = urllib.parse.quote(str(header["thread_id"]), safe="")
            thread = _read(f"/api/gmail/threads/{thread_id}", cookie)
            for message in thread.get("messages", []):
                messages.append(message)
                html = str(message.get("html_body") or "")
                attachments = message.get("attachments") or []
                item = {
                    "mode": message.get("presentation_mode"),
                    "html_images": len(re.findall(r"<img\b", html, re.IGNORECASE)),
                    "cid_images": len(
                        re.findall(r"\bsrc\s*=\s*['\"]cid:", html, re.IGNORECASE)
                    ),
                    "inline_attachments": sum(
                        1 for part in attachments if part.get("inline")
                    ),
                    "inline_requires_fetch": sum(
                        1
                        for part in attachments
                        if part.get("inline")
                        and part.get("attachment_id")
                        and not part.get("data_base64")
                    ),
                }
                threads.append(item)
        result["gmail_threads"] = {
            "status": "ok",
            "messages_inspected": len(threads),
            "modes": [item["mode"] for item in threads],
            "html_images": sum(item["html_images"] for item in threads),
            "cid_images": sum(item["cid_images"] for item in threads),
            "inline_requires_fetch": sum(
                item["inline_requires_fetch"] for item in threads
            ),
        }
        attachments_checked = False
        for message in messages:
            for part in message.get("attachments") or []:
                if not part.get("inline") or not part.get("attachment_id"):
                    continue
                message_id = urllib.parse.quote(str(message["id"]), safe="")
                attachment_id = urllib.parse.quote(str(part["attachment_id"]), safe="")
                stage = "gmail_attachment_get"
                result["gmail_inline_attachment"] = _read(
                    f"/api/gmail/messages/{message_id}/attachments/{attachment_id}?inline=true",
                    cookie,
                    binary=True,
                )
                attachments_checked = True
                break
            if attachments_checked:
                break
        if not attachments_checked:
            stage = "gmail_attachment_search"
            attachment_inbox = _read(
                "/api/gmail/messages?query=has%3Aattachment&max_results=10", cookie
            )
            result["gmail_attachment_search"] = {
                "returned": len(attachment_inbox.get("messages", []))
            }
            for header in attachment_inbox.get("messages", [])[:4]:
                stage = "gmail_attachment_thread"
                thread_id = urllib.parse.quote(str(header["thread_id"]), safe="")
                thread = _read(f"/api/gmail/threads/{thread_id}", cookie)
                for message in thread.get("messages", []):
                    for part in message.get("attachments") or []:
                        if not part.get("inline") or not part.get("attachment_id"):
                            continue
                        message_id = urllib.parse.quote(str(message["id"]), safe="")
                        attachment_id = urllib.parse.quote(
                            str(part["attachment_id"]), safe=""
                        )
                        stage = "gmail_attachment_get"
                        result["gmail_inline_attachment"] = _read(
                            f"/api/gmail/messages/{message_id}/attachments/{attachment_id}?inline=true",
                            cookie,
                            binary=True,
                        )
                        attachments_checked = True
                        break
                    if attachments_checked:
                        break
                if attachments_checked:
                    break
        if not attachments_checked:
            result["gmail_inline_attachment"] = {
                "status": "not_present_in_bounded_sample"
            }
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError) as exc:
        error_code = None
        if isinstance(exc, urllib.error.HTTPError):
            try:
                error_code = json.loads(exc.read().decode("utf-8")).get("code")
            except (ValueError, UnicodeDecodeError):
                pass
        result["gmail_error"] = {
            "kind": type(exc).__name__,
            "status": getattr(exc, "code", None),
            "stage": stage,
            "code": error_code,
        }
    try:
        files = _read("/api/drive/files?page_size=10", cookie)
        result["drive_list"] = {
            "status": "ok",
            "returned": len(files.get("files", [])),
            "indexed": sum(1 for item in files.get("files", []) if item.get("indexed")),
        }
        drive_samples: dict[str, object] = {}
        for label, mime_type in (
            ("google_doc", "application/vnd.google-apps.document"),
            ("google_sheet", "application/vnd.google-apps.spreadsheet"),
            ("pdf", "application/pdf"),
        ):
            listed = _read(
                "/api/drive/files?"
                + urllib.parse.urlencode({"page_size": 3, "mime_type": mime_type}),
                cookie,
            )
            candidates = listed.get("files", [])
            if label == "pdf":
                candidates = [
                    item
                    for item in candidates
                    if item.get("size") and int(item["size"]) <= 2 * 1024 * 1024
                ]
            if not candidates:
                drive_samples[label] = {"status": "not_present_in_bounded_sample"}
                continue
            read_errors = []
            for candidate in candidates if label == "google_doc" else candidates[:1]:
                file_id = urllib.parse.quote(str(candidate["id"]), safe="")
                try:
                    content = _read(f"/api/drive/files/{file_id}/content", cookie)
                    drive_samples[label] = {
                        "status": "ok",
                        "chars": len(content.get("text", "")),
                        "truncated": bool(content.get("truncated")),
                        "assets": len(content.get("assets", [])),
                        "attempts": len(read_errors) + 1,
                        "prior_errors": read_errors,
                    }
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
                    error_code = None
                    if isinstance(exc, urllib.error.HTTPError):
                        try:
                            error_code = json.loads(exc.read().decode("utf-8")).get("code")
                        except (ValueError, UnicodeDecodeError):
                            pass
                    read_errors.append(
                        {"http_status": getattr(exc, "code", None), "code": error_code}
                    )
            else:
                drive_samples[label] = {"status": "read_error", "attempts": read_errors}
        result["drive_content"] = drive_samples
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError) as exc:
        result["drive_error"] = {
            "kind": type(exc).__name__,
            "status": getattr(exc, "code", None),
        }
    result["passed"] = smoke_passed(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
