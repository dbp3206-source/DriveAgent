"""History checks use only synthetic credentials in isolated temporary repositories."""

import importlib.util
import subprocess
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def scanner(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts" / "scan_release_secrets.py"
    spec = importlib.util.spec_from_file_location("release_secret_scan", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return module


def commit(scanner):
    subprocess.run(["git", "add", "-A"], cwd=scanner.ROOT, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Scanner Test", "-c", "user.email=scanner@example.test",
         "commit", "-qm", "synthetic scan fixture"], cwd=scanner.ROOT, check=True,
    )


def test_deleted_secret_is_detected_and_output_redacted(scanner, monkeypatch, capsys):
    synthetic = b"ghp_" + b"A" * 36
    path = scanner.ROOT / "old-token.txt"
    path.write_bytes(synthetic)
    commit(scanner)
    path.unlink()
    (scanner.ROOT / "clean.txt").write_text("clean", encoding="utf-8")
    commit(scanner)
    monkeypatch.setattr(scanner.sys, "argv", ["scanner", "--history"])
    assert scanner.main() == 1
    output = capsys.readouterr().out
    assert "old-token.txt: GitHub token in Git history" in output
    assert synthetic.decode() not in output
    assert "values redacted" in output


def test_forbidden_history_names_override_fixture_and_size_exclusions(scanner):
    path = scanner.ROOT / "backend" / "tests" / "client_secret_test.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * (scanner.MAX_TEXT_BYTES + 1))
    commit(scanner)
    findings, checked = scanner.scan_history()
    assert findings == [
        ("backend/tests/client_secret_test.json", "private/runtime file in Git history")
    ]
    assert checked == 0


def test_history_exclusions_canaries_and_bounded_batch_reads(scanner, monkeypatch):
    synthetic = b"AIza" + b"A" * 36
    for name in ("backend/tests/synthetic.txt", "assets/fixtures/synthetic.txt"):
        path = scanner.ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(synthetic)
    (scanner.ROOT / "huge.txt").write_bytes(synthetic + b"x" * scanner.MAX_TEXT_BYTES)
    for number, separator in enumerate((b"\n", b"\\n", b"&#10;")):
        (scanner.ROOT / f"canary-{number}.txt").write_bytes(
            b"-----BEGIN PRIVATE KEY-----" + separator + b"FAKE_CANARY_NOT_A_SECRET"
        )
    for number in range(20):
        (scanner.ROOT / f"clean-{number}.txt").write_text(f"clean {number}", encoding="utf-8")
    commit(scanner)
    original_popen = scanner.subprocess.Popen
    processes = []
    reads = []

    class RecordingReader:
        def __init__(self, stream):
            self.stream = stream

        def read(self, count):
            reads.append(count)
            return self.stream.read(count)

        def __getattr__(self, name):
            return getattr(self.stream, name)

    def recording_popen(command, **kwargs):
        process = original_popen(command, **kwargs)
        processes.append(process)
        if command[-1] == "--batch":
            process.stdout = RecordingReader(process.stdout)
        return process

    monkeypatch.setattr(scanner.subprocess, "Popen", recording_popen)
    findings, checked = scanner.scan_history()
    assert findings == []
    assert checked == 23
    assert len(processes) == 3
    assert all(process.poll() == 0 for process in processes)
    assert reads and max(reads) <= scanner.MAX_TEXT_BYTES


def test_arbitrary_private_key_is_not_suppressed(scanner):
    (scanner.ROOT / "key.txt").write_bytes(b"-----BEGIN PRIVATE KEY-----\nOTHER_SYNTHETIC_VALUE")
    commit(scanner)
    assert scanner.scan_history() == ([("key.txt", "private key in Git history")], 1)


def test_invalid_batch_response_fails_closed(scanner):
    process = SimpleNamespace(stdin=BytesIO(), stdout=BytesIO(b"deadbeef missing\n"))
    with pytest.raises(RuntimeError, match="history scan incomplete"):
        scanner.batch_request(process, b"deadbeef")


def test_git_reader_failure_fails_closed(scanner):
    with pytest.raises(RuntimeError, match="scan incomplete"):
        with scanner.git_stream("not-a-real-git-command") as process:
            assert process.stdout.read() == b""
