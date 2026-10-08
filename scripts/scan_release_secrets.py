"""Fail closed when Git-visible release files contain likely private credentials.

The scanner considers tracked files plus untracked files that are not ignored. It does
not print the matching value. Synthetic credential fixtures under tests are allowed;
runtime files and raw live evidence must be excluded by .gitignore instead.
"""

from __future__ import annotations

import re
import subprocess
import sys
from contextlib import contextmanager
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
    "Tavily API key": re.compile(rb"tvly-[0-9A-Za-z_-]{20,}"),
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


@contextmanager
def git_stream(*arguments: str, interactive: bool = False):
    """Keep Git pipes bounded and treat interrupted/failed readers as scan failures."""
    process = subprocess.Popen(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *arguments],
        cwd=ROOT, stdin=subprocess.PIPE if interactive else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        yield process
        if process.stdin is not None:
            process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("Git history reader failed; scan incomplete.")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        if process.stdout is not None:
            process.stdout.close()
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()


def batch_request(process, oid: bytes) -> list[bytes]:
    process.stdin.write(oid + b"\n")
    process.stdin.flush()
    header = process.stdout.readline(256).split()
    if len(header) != 3 or header[0] != oid or not header[2].isdigit():
        raise RuntimeError("Invalid Git batch response; history scan incomplete.")
    return header


def scan_history() -> tuple[list[tuple[str, str]], int]:
    findings: list[tuple[str, str]] = []
    checked = 0
    # Read metadata before requesting content so large/excluded objects never enter
    # Python memory. Three Git processes suffice regardless of history length.
    with git_stream("rev-list", "--objects", "--all") as objects, \
            git_stream("cat-file", "--batch-check", interactive=True) as metadata, \
            git_stream("cat-file", "--batch", interactive=True) as blobs:
        for item in objects.stdout:
            parts = item.rstrip(b"\n").split(b" ", 1)
            if len(parts) != 2:
                continue
            oid, raw_path = parts
            _, kind, raw_size = batch_request(metadata, oid)
            if kind != b"blob":
                continue
            path = raw_path.decode("utf-8", "replace")
            if any(pattern.search(path) for pattern in FORBIDDEN_NAMES):
                findings.append((path, "private/runtime file in Git history"))
                continue
            size = int(raw_size)
            if size > MAX_TEXT_BYTES or path.startswith("backend/tests/") or "/fixtures/" in path:
                continue
            _, blob_kind, blob_size = batch_request(blobs, oid)
            if blob_kind != b"blob" or int(blob_size) != size:
                raise RuntimeError("Git blob metadata changed; history scan incomplete.")
            data = blobs.stdout.read(size)
            if len(data) != size or blobs.stdout.read(1) != b"\n":
                raise RuntimeError("Truncated Git blob; history scan incomplete.")
            data = without_known_canary(data)
            checked += 1
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(data):
                    findings.append((path, f"{label} in Git history"))
    return findings, checked


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
        history_findings, checked = scan_history()
        findings.extend(history_findings)
        if findings:
            print("History scan FAILED; values redacted.")
            for path, label in sorted(set(findings)):
                print(f"- {path}: {label}")
            return 1
        print(f"History credential scan passed for {checked} bounded blobs; not a PII review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
