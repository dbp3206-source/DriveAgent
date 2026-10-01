"""Run the single owner-approved Gmail send gate and verify it read-only.

This script is intentionally narrow: one self-addressed message, one pre-existing
QA Google Doc attachment, one deterministic request key, and no automatic retry.
Provider identifiers and message contents are never printed.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

from qa_google_read_smoke import BASE, _cookie, _read

RECIPIENT = "dbp3206@gmail.com"
SUBJECT = "[Veridra QA] Kiểm thử gửi email có tệp — không phản hồi"
BODY = (
    "Đây là email thử nghiệm cho quy trình xem trước → duyệt → gửi → đọc lại. "
    "Không cần phản hồi. Mã kiểm thử: QA-SEND-20260927."
)
DOC_TITLE = "[DriveAgent QA] Kiểm thử tạo Google Doc — 2026-09-25"
DOC_MIME = "application/vnd.google-apps.document"
REQUEST_KEY = "veridraQASend20260927v1"


def _post(path: str, payload: dict[str, object], cookie: str) -> dict:
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Cookie": f"drive_agent_session={cookie}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "http://localhost:8000",
            "Referer": "http://localhost:8000/#/gmail",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _matching_sent(cookie: str) -> list[dict]:
    query = urllib.parse.urlencode(
        {"query": f'in:sent subject:"{SUBJECT}"', "max_results": 20}
    )
    payload = _read(f"/api/gmail/messages?{query}", cookie)
    return [item for item in payload.get("messages", []) if item.get("subject") == SUBJECT]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-approved", action="store_true")
    args = parser.parse_args()
    if not args.execute_approved:
        raise SystemExit("Refusing cloud write without --execute-approved")

    cookie = _cookie()
    before = _matching_sent(cookie)
    if before:
        raise SystemExit("Refusing to send: the exact QA subject already exists in Sent")

    drive_query = urllib.parse.urlencode(
        {"query": "QA-DOC-20260925", "mime_type": DOC_MIME, "page_size": 50}
    )
    drive_payload = _read(f"/api/drive/files?{drive_query}", cookie)
    matches = [
        item
        for item in drive_payload.get("files", [])
        if item.get("name") == DOC_TITLE and item.get("mime_type") == DOC_MIME
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one approved QA Doc, found {len(matches)}")

    prepare = _post(
        "/api/gmail/prepare",
        {
            "request_key": REQUEST_KEY,
            "draft": {
                "recipient": RECIPIENT,
                "subject": SUBJECT,
                "body": BODY,
                "drive_file_ids": [str(matches[0]["id"])],
                "cc": "",
                "bcc": "",
                "thread_id": None,
                "in_reply_to": "",
                "references": "",
            },
        },
        cookie,
    )["data"]
    if prepare.get("state") not in {"prepared", "pending"}:
        raise SystemExit("Prepare did not return an approvable state")

    sent = _post(
        "/api/gmail/approve",
        {
            "operation_id": prepare["operation_id"],
            "approved_digest": prepare["digest"],
        },
        cookie,
    )["data"]

    operation = _read(
        "/api/gmail/operations/"
        + urllib.parse.quote(str(prepare["operation_id"]), safe=""),
        cookie,
    )
    after = _matching_sent(cookie)
    attachment_names = sent.get("attachment_names") or []
    result = {
        "cloud_writes": 1,
        "approved_send_attempts": 1,
        "recipient_is_owner": sent.get("recipient") == RECIPIENT,
        "subject_matches": sent.get("subject") == SUBJECT,
        "operation_state": operation.get("state"),
        "provider_reported_sent": bool(sent.get("sent")),
        "attachment_count": len(attachment_names),
        # Native Google Docs are exported as DOCX for Gmail attachments.
        "attachment_name_matches": attachment_names == [f"{DOC_TITLE}.docx"],
        "sent_matches_before": len(before),
        "sent_matches_after": len(after),
        "exactly_one_sent_copy": len(after) == 1,
        "no_retry_performed": True,
    }
    result["passed"] = all(
        (
            result["recipient_is_owner"],
            result["subject_matches"],
            result["provider_reported_sent"],
            result["attachment_count"] == 1,
            result["attachment_name_matches"],
            result["sent_matches_before"] == 0,
            result["exactly_one_sent_copy"],
            result["operation_state"] == "succeeded",
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
