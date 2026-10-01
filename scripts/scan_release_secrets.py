"""Fail closed when Git-visible release files contain likely private credentials.

The scanner considers tracked files plus untracked files that are not ignored. It does
not print the matching value. Synthetic credential fixtures under tests are allowed;
runtime files and raw live evidence must be excluded by .gitignore instead.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 5_000_000

FORBIDDEN_NAMES = (
    re.compile(r"(^|/)\.env($|\.(?!example$))", re.IGNORECASE),
    re.compile(r"(^|/)client_secret[^/]*\.json$", re.IGNORECASE),
    re.compile(r"(^|/)cookies?[^/]*\.txt$", re.IGNORECASE),
    re.compile(r"\.(?:db|sqlite|sqlite3)$", re.IGNORECASE),
    re.compile(r"(^|/)ops/secrets/", re.IGNORECASE),
)
SECRET_PATTERNS = {
    "Google API key": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(rb"gh[pousr]_[0-9A-Za-z]{30,}"),
    "Supabase service JWT": re.compile(rb"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}"),
}


def without_known_canary(data: bytes) -> bytes:
    # Exact security-test sentinel; never suppress arbitrary PEM/key material.
    return re.sub(rb"-----BEGIN [P]RIVATE KEY-----(?:\n|\\n|&#10;)FAKE_CANARY_NOT_A_SECRET",
                  b"SYNTHETIC_SECURITY_TEST_CANARY", data)


def git_visible_files() -> list[str]:
    command = [
        "git",
        "-c",
        f"safe.directory={ROOT.as_posix()}",
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    ]
    raw = subprocess.check_output(command, cwd=ROOT)
    return sorted({item.decode("utf-8", "surrogateescape") for item in raw.split(b"\0") if item})


def main() -> int:
    findings: list[tuple[str, str]] = []
    for relative in git_visible_files():
        normalized = relative.replace("\\", "/")
        if any(pattern.search(normalized) for pattern in FORBIDDEN_NAMES):
            findings.append((normalized, "forbidden runtime/private filename"))
            continue
        path = ROOT / relative
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_TEXT_BYTES:
            continue
        # Test fixtures intentionally exercise redaction with unmistakably synthetic values.
        if normalized.startswith("backend/tests/") or "/fixtures/" in normalized:
            continue
        data = without_known_canary(path.read_bytes())
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                findings.append((normalized, label))
    if findings:
        print("Release secret scan FAILED. Values are intentionally redacted.")
        for path, label in findings:
            print(f"- {path}: {label}")
        return 1
    print(f"Release secret scan passed for {len(git_visible_files())} Git-visible files.")
    if "--history" in sys.argv:
        command = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
        objects = subprocess.check_output([*command, "rev-list", "--objects", "--all"],
                                          cwd=ROOT).splitlines()
        checked = 0
        for item in objects:
            parts = item.split(b" ", 1)
            if len(parts) != 2:
                continue
            oid, raw_path = parts
            path = raw_path.decode("utf-8", "replace")
            kind = subprocess.check_output([*command, "cat-file", "-t", oid.decode()],
                                           cwd=ROOT).strip()
            if kind != b"blob":
                continue
            if any(pattern.search(path) for pattern in FORBIDDEN_NAMES):
                findings.append((path, "private/runtime file in Git history"))
                continue
            size = int(subprocess.check_output([*command, "cat-file", "-s", oid.decode()], cwd=ROOT))
            if size > MAX_TEXT_BYTES or path.startswith("backend/tests/") or "/fixtures/" in path:
                continue
            data = without_known_canary(subprocess.check_output(
                [*command, "cat-file", "blob", oid.decode()], cwd=ROOT))
            checked += 1
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(data):
                    findings.append((path, f"{label} in Git history"))
        if findings:
            print("History scan FAILED; values redacted.")
            for path, label in sorted(set(findings)):
                print(f"- {path}: {label}")
            return 1
        print(f"History credential scan passed for {checked} bounded blobs; not a PII review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
