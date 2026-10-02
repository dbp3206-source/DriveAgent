"""Bounded, read-only Gmail format sample with privacy-minimal output.

Only aggregate counts and safe error codes are printed. Subjects, senders,
message IDs, body text, URLs and credentials never enter the report.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from qa_google_read_smoke import _cookie, _read

MIN_REQUEST_INTERVAL_SECONDS = 2.1
_last_request_started = 0.0


def paced_read(path: str, cookie: str, *, binary: bool = False):
    """Keep the live acceptance probe below the product's 30 calls/min limit."""

    global _last_request_started
    delay = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_started)
    if delay > 0:
        time.sleep(delay)
    _last_request_started = time.monotonic()
    return _read(path, cookie, binary=binary)

COHORTS = (
    ("inbox", "in:inbox", 20),
    ("sent", "in:sent", 8),
    ("attachments", "has:attachment", 8),
    ("calendar", "filename:ics", 5),
    ("older_mail", "in:anywhere older_than:365d", 10),
)


def message_metadata(message: dict) -> dict[str, object]:
    html = str(message.get("html_body") or "")
    attachments = message.get("attachments") or []
    return {
        "mode": str(message.get("presentation_mode") or "missing"),
        "plain": bool(str(message.get("plain_body") or "").strip()),
        "html": bool(html.strip()),
        "readable": bool(str(message.get("body") or "").strip()),
        "html_images": len(re.findall(r"<img\b", html, flags=re.IGNORECASE)),
        "cid_images": len(re.findall(r"\bsrc\s*=\s*['\"]cid:", html, flags=re.IGNORECASE)),
        "remote_images": len(re.findall(r"\bsrc\s*=\s*['\"]https?://", html, flags=re.IGNORECASE)),
        "attachments": len(attachments),
        "inline_attachments": sum(1 for item in attachments if item.get("inline")),
        "attachment_mime_families": [
            str(item.get("mime_type") or "unknown").split("/", 1)[0] for item in attachments
        ],
    }


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    modes = Counter(str(row["mode"]) for row in rows)
    families = Counter(
        family for row in rows for family in row["attachment_mime_families"]
    )
    return {
        "messages": len(rows),
        "modes": dict(sorted(modes.items())),
        "plain_parts": sum(bool(row["plain"]) for row in rows),
        "html_parts": sum(bool(row["html"]) for row in rows),
        "readable_bodies": sum(bool(row["readable"]) for row in rows),
        "html_images": sum(int(row["html_images"]) for row in rows),
        "cid_images": sum(int(row["cid_images"]) for row in rows),
        "remote_images": sum(int(row["remote_images"]) for row in rows),
        "attachments": sum(int(row["attachments"]) for row in rows),
        "inline_attachments": sum(int(row["inline_attachments"]) for row in rows),
        "attachment_mime_families": dict(sorted(families.items())),
    }


def safe_error(exc: Exception) -> dict[str, object]:
    code = None
    if isinstance(exc, urllib.error.HTTPError):
        try:
            code = json.loads(exc.read().decode("utf-8")).get("code")
        except (ValueError, UnicodeDecodeError):
            pass
    return {"kind": type(exc).__name__, "http_status": getattr(exc, "code", None), "code": code}


def main() -> None:
    cookie = _cookie()
    seen_threads: set[str] = set()
    seen_inline_parts: set[tuple[str, str]] = set()
    rows: list[dict[str, object]] = []
    cohort_results: dict[str, dict[str, object]] = {}
    failures: list[dict[str, object]] = []
    inline_fetch = Counter()
    for label, query, limit in COHORTS:
        path = "/api/gmail/messages?" + urllib.parse.urlencode(
            {"query": query, "max_results": limit}
        )
        try:
            listing = paced_read(path, cookie)
            headers = listing.get("messages", [])
            cohort_results[label] = {"headers": len(headers), "new_threads": 0}
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError) as exc:
            failures.append({"cohort": label, "stage": "list", **safe_error(exc)})
            continue
        for header in headers:
            thread_id = str(header.get("thread_id") or "")
            if not thread_id or thread_id in seen_threads:
                continue
            seen_threads.add(thread_id)
            try:
                thread = paced_read(
                    "/api/gmail/threads/" + urllib.parse.quote(thread_id, safe=""), cookie
                )
                for item in thread.get("messages", []):
                    rows.append(message_metadata(item))
                    message_id = str(item.get("id") or "")
                    for part in item.get("attachments") or []:
                        attachment_id = str(part.get("attachment_id") or "")
                        if not part.get("inline") or not attachment_id or not message_id:
                            continue
                        part_key = (message_id, attachment_id)
                        if part_key in seen_inline_parts:
                            continue
                        seen_inline_parts.add(part_key)
                        path = (
                            "/api/gmail/messages/"
                            + urllib.parse.quote(message_id, safe="")
                            + "/attachments/"
                            + urllib.parse.quote(attachment_id, safe="")
                            + "?inline=true"
                        )
                        try:
                            response = paced_read(path, cookie, binary=True)
                            if response["status"] != 200 or response["bytes"] < 1:
                                failures.append({"cohort": label, "stage": "inline_empty"})
                            else:
                                inline_fetch["ok"] += 1
                        except (
                            urllib.error.HTTPError,
                            urllib.error.URLError,
                            ValueError,
                            KeyError,
                        ) as exc:
                            failures.append({"cohort": label, "stage": "inline", **safe_error(exc)})
                cohort_results[label]["new_threads"] += 1
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError) as exc:
                failures.append({"cohort": label, "stage": "read", **safe_error(exc)})
    result = {
        "run_at": datetime.now(UTC).isoformat(),
        "scope": "bounded_real_mail_format_reads_not_semantic_summary_acceptance",
        "cloud_writes": 0,
        "min_request_interval_seconds": MIN_REQUEST_INTERVAL_SECONDS,
        "cohorts": cohort_results,
        "unique_threads": len(seen_threads),
        "aggregate": summarize(rows),
        "inline_fetch": {"attempted": len(seen_inline_parts), "ok": inline_fetch["ok"]},
        "failures": failures,
        "passed": not failures and bool(rows),
    }
    folder = Path(__file__).resolve().parents[1] / "design-work/qa/RELEASE-20261002"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"gmail-mime-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["report_file"] = path.name
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
