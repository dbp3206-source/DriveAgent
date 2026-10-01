"""Verify existence/uniqueness of the two owner-approved QA writes without mutating Google."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse

from qa_google_read_smoke import _cookie, _read

EXPECTED_DRAFT_SUBJECT = "[DriveAgent QA] Kiểm thử tạo thư nháp — không gửi"
EXPECTED_DOC_TITLE = "[DriveAgent QA] Kiểm thử tạo Google Doc — 2026-09-25"
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"


def safe_failure(exc: Exception) -> dict[str, object]:
    return {"type": type(exc).__name__, "http_status": getattr(exc, "code", None)}


def main() -> None:
    cookie = _cookie()
    result: dict[str, object] = {
        "cloud_writes": 0,
        "registry_reads_may_append_local_metadata_audit": True,
        "checks": {},
        "failures": [],
    }
    failures: list[dict[str, object]] = result["failures"]  # type: ignore[assignment]

    try:
        drafts = _read(
            "/api/gmail/messages?"
            + urllib.parse.urlencode({"query": "in:drafts", "max_results": 50}),
            cookie,
        )
        draft_rows = drafts.get("messages", [])
        expected_drafts = [
            item for item in draft_rows if item.get("subject") == EXPECTED_DRAFT_SUBJECT
        ]
        draft_ids = {str(item.get("id") or "") for item in expected_drafts}
        result["checks"]["approved_gmail_draft"] = {
            "status": "ok" if len(draft_ids) == 1 else "missing_or_duplicate",
            "matches": len(expected_drafts),
            "unique_message_ids": len(draft_ids),
        }
        if len(draft_ids) != 1:
            failures.append({"check": "approved_gmail_draft", "matches": len(expected_drafts)})
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError) as exc:
        failures.append({"check": "approved_gmail_draft", **safe_failure(exc)})

    try:
        docs = _read(
            "/api/drive/files?"
            + urllib.parse.urlencode(
                {
                    "query": "QA-DOC-20260925",
                    "mime_type": GOOGLE_DOC_MIME,
                    "page_size": 50,
                }
            ),
            cookie,
        )
        rows = docs.get("files", [])
        expected_docs = [
            item
            for item in rows
            if item.get("mime_type") == GOOGLE_DOC_MIME
            and item.get("name") == EXPECTED_DOC_TITLE
        ]
        doc_ids = {str(item.get("id") or "") for item in expected_docs}
        result["checks"]["approved_google_doc"] = {
            "status": "ok" if len(doc_ids) == 1 else "missing_or_duplicate",
            "matches": len(expected_docs),
            "unique_file_ids": len(doc_ids),
        }
        if len(doc_ids) != 1:
            failures.append({"check": "approved_google_doc", "matches": len(expected_docs)})
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError) as exc:
        failures.append({"check": "approved_google_doc", **safe_failure(exc)})

    result["passed"] = not failures and len(result["checks"]) == 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
