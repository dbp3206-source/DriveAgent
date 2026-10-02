"""Verify public requests cannot read private data, without cookies or model calls."""

import argparse
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit

PATHS = (
    "/api/memories", "/api/skills", "/api/artifacts", "/api/chat/sessions",
    "/api/local-sources", "/api/evaluation-jobs",
)


def check(origin: str) -> dict:
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query):
        raise ValueError("An HTTPS origin without credentials or query is required")
    if parsed.path not in ("", "/") or parsed.fragment:
        raise ValueError("Use an origin, not a page URL")
    rows = []
    for path in PATHS:
        try:
            with urllib.request.urlopen(origin.rstrip("/") + path, timeout=20) as response:
                status = response.status
                cache = response.headers.get("Cache-Control")
        except urllib.error.HTTPError as error:
            status = error.code
            cache = error.headers.get("Cache-Control")
            error.close()
        except (OSError, urllib.error.URLError) as error:
            rows.append({"path": path, "passed": False, "error": type(error).__name__})
            continue
        rows.append({"path": path, "status": status, "cache_control": cache,
                     "passed": status == 401})
    return {"origin": origin, "scope": "Unauthenticated public reads only; not cross-owner proof",
            "checks": rows, "passed": all(row["passed"] for row in rows),
            "model_calls": 0, "writes": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    arguments = parser.parse_args()
    result = check(arguments.origin)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
