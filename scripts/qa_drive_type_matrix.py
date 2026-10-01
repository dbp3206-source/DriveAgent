"""Bounded, read-only Drive search, pagination and supported-type smoke.

Only counts, MIME labels, parser lengths and safe HTTP error codes are printed.
No file names, IDs, contents, tokens or Google writes are persisted.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse

from qa_google_read_smoke import _cookie, _read

MIN_REQUEST_INTERVAL_SECONDS = 1.1
_last_request_started = 0.0
READ_ERRORS = (
    urllib.error.HTTPError,
    urllib.error.URLError,
    TimeoutError,
    ValueError,
    KeyError,
)
TYPE_SAMPLES = (
    ("google_doc", "application/vnd.google-apps.document"),
    ("google_sheet", "application/vnd.google-apps.spreadsheet"),
    ("google_slides", "application/vnd.google-apps.presentation"),
    ("google_drawing", "application/vnd.google-apps.drawing"),
    ("pdf", "application/pdf"),
    ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ("text_plain", "text/plain"),
    ("text_markdown", "text/markdown"),
    ("text_csv", "text/csv"),
    ("text_html", "text/html"),
    ("json_or_ipynb", "application/json"),
)


def paced_read(path: str, cookie: str, *, binary: bool = False):
    global _last_request_started
    delay = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_started)
    if delay > 0:
        time.sleep(delay)
    _last_request_started = time.monotonic()
    return _read(path, cookie, binary=binary)


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
    results: dict[str, object] = {}
    failures: list[dict[str, object]] = []
    search_check: dict[str, object] = {"status": "not_run"}
    full_text_search: dict[str, object] = {"status": "not_run"}

    for label, mime_type in TYPE_SAMPLES:
        listing_path = "/api/drive/files?" + urllib.parse.urlencode(
            {"page_size": 5, "mime_type": mime_type}
        )
        try:
            listing = paced_read(listing_path, cookie)
        except READ_ERRORS as exc:
            failures.append({"stage": "type_list", "type": label, **safe_error(exc)})
            results[label] = {"status": "list_error"}
            continue

        files = listing.get("files", [])
        if not files:
            results[label] = {"status": "not_present"}
            continue

        candidate = files[0]
        sample: dict[str, object] = {
            "status": "listed",
            "mime_match": candidate.get("mime_type") == mime_type,
            "attempts": 0,
            "prior_errors": [],
        }
        for candidate in files:
            sample["attempts"] = int(sample["attempts"]) + 1
            sample["mime_match"] = candidate.get("mime_type") == mime_type
            try:
                file_id = urllib.parse.quote(str(candidate["id"]), safe="")
                content = paced_read(f"/api/drive/files/{file_id}/content", cookie)
                sample.update(
                    {
                        "status": "read_ok",
                        "chars": len(str(content.get("text") or "")),
                        "truncated": bool(content.get("truncated")),
                        "assets": len(content.get("assets") or []),
                    }
                )
                if not sample["mime_match"]:
                    failures.append({"stage": "type_mismatch", "type": label})
                break
            except READ_ERRORS as exc:
                sample["prior_errors"].append(safe_error(exc))
        if sample["status"] != "read_ok":
            sample["status"] = "read_error"
            failures.append(
                {
                    "stage": "content_read",
                    "type": label,
                    "attempts": sample["attempts"],
                    "last_error": sample["prior_errors"][-1] if sample["prior_errors"] else None,
                }
            )
        results[label] = sample
        if search_check["status"] == "not_run":
            try:
                search_path = "/api/drive/files?" + urllib.parse.urlencode(
                    {
                        "page_size": 5,
                        "query": str(candidate.get("name") or ""),
                        "mime_type": mime_type,
                    }
                )
                search = paced_read(search_path, cookie)
                search_check = {
                    "status": "ok",
                    "returned": len(search.get("files", [])),
                    "candidate_found": any(
                        item.get("id") == candidate.get("id")
                        for item in search.get("files", [])
                    ),
                }
                if not search_check["candidate_found"]:
                    failures.append({"stage": "search_miss", "type": label})
            except READ_ERRORS as exc:
                search_check = {"status": "error", **safe_error(exc)}
                failures.append({"stage": "search", "type": label, **safe_error(exc)})

    # Search for a high-entropy marker that was placed in the body (not the title)
    # of the previously owner-approved QA Doc. This distinguishes full-text search
    # from the name-search check above without printing the document or its ID.
    try:
        body_query = urllib.parse.urlencode(
            {"page_size": 10, "query": "QA-DOC-20260925", "mime_type": TYPE_SAMPLES[0][1]}
        )
        body_results = paced_read(f"/api/drive/files?{body_query}", cookie)
        body_files = body_results.get("files", [])
        body_only_hits = sum(
            1
            for item in body_files
            if isinstance(item, dict)
            and item.get("mime_type") == TYPE_SAMPLES[0][1]
            and "QA-DOC-20260925" not in str(item.get("name") or "")
        )
        full_text_search = {
            "status": "ok" if body_only_hits else "body_marker_not_found",
            "returned": len(body_files),
            "body_only_google_doc_hits": body_only_hits,
        }
        if not body_only_hits:
            failures.append({"stage": "full_text_search", "kind": "body_marker_not_found"})
    except READ_ERRORS as exc:
        full_text_search = {"status": "error", **safe_error(exc)}
        failures.append({"stage": "full_text_search", **safe_error(exc)})

    pagination: dict[str, object] = {"status": "single_page"}
    try:
        first = paced_read("/api/drive/files?page_size=1", cookie)
        token = first.get("next_page_token")
        if token:
            page2_path = "/api/drive/files?" + urllib.parse.urlencode(
                {"page_size": 1, "page_token": token}
            )
            second = paced_read(page2_path, cookie)
            first_ids = {item.get("id") for item in first.get("files", [])}
            second_ids = {item.get("id") for item in second.get("files", [])}
            distinct = bool(second_ids) and first_ids.isdisjoint(second_ids)
            pagination = {"status": "ok" if distinct else "duplicate_or_empty_page"}
            if not distinct:
                failures.append({"stage": "pagination"})
    except READ_ERRORS as exc:
        pagination = {"status": "error", **safe_error(exc)}
        failures.append({"stage": "pagination", **safe_error(exc)})

    output = {
        "cloud_writes": 0,
        "min_request_interval_seconds": MIN_REQUEST_INTERVAL_SECONDS,
        "types": results,
        "search": search_check,
        "full_text_search": full_text_search,
        "pagination": pagination,
        "failures": failures,
        "passed": not failures
        and any(item.get("status") == "read_ok" for item in results.values()),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not output["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
