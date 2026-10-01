"""Offline, encrypted backup/restore for a mounted Veridra STATE_DIR.

The app must be stopped before backup. Restores never replace an existing
directory. This utility intentionally does not include .env or OAuth client JSON;
store those separately in an encrypted secret manager.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import io
import json
import os
import shutil
import socket
import struct
import tarfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"VRDSTATE"
HEADER = struct.Struct(">8s16s8sI")
LENGTH = struct.Struct(">I")
CHUNK_SIZE = 64 * 1024
MAX_FILES = 100_000
MAX_TOTAL_BYTES = 5 * 1024**3


def _key(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 16:
        raise ValueError("Backup passphrase must have at least 16 characters")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(
        passphrase.encode("utf-8")
    )


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class _EncryptedWriter:
    def __init__(self, raw, passphrase: str):
        self.raw = raw
        self.salt = os.urandom(16)
        self.prefix = os.urandom(8)
        self.aes = AESGCM(_key(passphrase, self.salt))
        self.buffer = bytearray()
        self.sequence = 0
        raw.write(HEADER.pack(MAGIC, self.salt, self.prefix, CHUNK_SIZE))

    def write(self, data: bytes) -> int:
        self.buffer.extend(data)
        while len(self.buffer) >= CHUNK_SIZE:
            self._chunk(bytes(self.buffer[:CHUNK_SIZE]))
            del self.buffer[:CHUNK_SIZE]
        return len(data)

    def _chunk(self, plaintext: bytes) -> None:
        if self.sequence >= 2**32:
            raise ValueError("Backup archive exceeds supported chunk count")
        seq = self.sequence.to_bytes(4, "big")
        ciphertext = self.aes.encrypt(self.prefix + seq, plaintext, MAGIC + seq)
        self.raw.write(LENGTH.pack(len(ciphertext)))
        self.raw.write(ciphertext)
        self.sequence += 1

    def finish(self) -> None:
        if self.buffer:
            self._chunk(bytes(self.buffer))
            self.buffer.clear()
        self.raw.write(LENGTH.pack(0))
        self.raw.flush()
        os.fsync(self.raw.fileno())


class _DecryptedReader:
    def __init__(self, raw, passphrase: str):
        header = raw.read(HEADER.size)
        if len(header) != HEADER.size:
            raise ValueError("Incomplete backup header")
        magic, salt, self.prefix, self.chunk_size = HEADER.unpack(header)
        if magic != MAGIC or self.chunk_size != CHUNK_SIZE:
            raise ValueError("Unsupported backup format")
        self.raw = raw
        self.aes = AESGCM(_key(passphrase, salt))
        self.buffer = bytearray()
        self.sequence = 0
        self.ended = False

    def _next(self) -> None:
        encoded_length = self.raw.read(LENGTH.size)
        if len(encoded_length) != LENGTH.size:
            raise ValueError("Backup ended before its authenticated footer")
        size = LENGTH.unpack(encoded_length)[0]
        if size == 0:
            self.ended = True
            if self.raw.read(1):
                raise ValueError("Backup has trailing bytes")
            return
        if size < 16 or size > self.chunk_size + 16 or self.sequence >= 2**32:
            raise ValueError("Invalid encrypted backup chunk")
        ciphertext = self.raw.read(size)
        if len(ciphertext) != size:
            raise ValueError("Truncated encrypted backup chunk")
        seq = self.sequence.to_bytes(4, "big")
        try:
            self.buffer.extend(self.aes.decrypt(self.prefix + seq, ciphertext, MAGIC + seq))
        except InvalidTag as exc:
            raise ValueError("Wrong passphrase or corrupted backup") from exc
        self.sequence += 1

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            while not self.ended:
                self._next()
            size = len(self.buffer)
        while len(self.buffer) < size and not self.ended:
            self._next()
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    def verify_footer(self) -> None:
        self.buffer.clear()
        while not self.ended:
            self._next()
            self.buffer.clear()


def _source_files(source: Path, excluded_top_dirs: frozenset[str] = frozenset()
                  ) -> list[dict[str, object]]:
    if any(not name or name in {".", ".."} or "/" in name or "\\" in name
           for name in excluded_top_dirs):
        raise ValueError("Invalid excluded top-level directory")
    files = []
    total = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if relative.parts[0] in excluded_top_dirs:
            continue
        if path.is_symlink():
            raise ValueError("STATE_DIR must not contain symlinks")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("STATE_DIR contains an unsupported file type")
        size = path.stat().st_size
        total += size
        if len(files) >= MAX_FILES or total > MAX_TOTAL_BYTES:
            raise ValueError("STATE_DIR exceeds the archive safety limit")
        files.append(
            {"path": path.relative_to(source).as_posix(), "size": size, "sha256": _hash_file(path)}
        )
    if not files:
        raise ValueError("STATE_DIR has no files to back up")
    return files


def _assert_app_stopped(port: int | None) -> None:
    if not port:
        return
    with socket.socket() as connection:
        connection.settimeout(0.5)
        if connection.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Stop Veridra on port {port} before backup")


def backup_state(source: Path, archive: Path, passphrase: str, *, port: int | None = 8000,
                 excluded_top_dirs: frozenset[str] = frozenset()) -> int:
    """Create a new encrypted archive; never overwrite an existing archive."""

    _assert_app_stopped(port)
    if source.is_symlink():
        raise ValueError("STATE_DIR symlink is not a valid backup source")
    source = source.resolve(strict=True)
    archive = archive.resolve(strict=False)
    if not source.is_dir() or not archive.parent.is_dir():
        raise ValueError("Source and output parent must be existing directories")
    if source in {Path(source.anchor), Path.home().resolve(), Path.cwd().resolve()}:
        raise ValueError("Unsafe broad backup source")
    if archive.is_relative_to(source) or archive.exists():
        raise ValueError("Backup output must be new and outside STATE_DIR")
    files = _source_files(source, excluded_top_dirs)
    manifest = json.dumps({"version": 1, "files": files,
                           "excluded_top_dirs": sorted(excluded_top_dirs)},
                          separators=(",", ":")).encode()
    created = False
    try:
        with archive.open("xb") as raw:
            created = True
            os.chmod(archive, 0o600)
            writer = _EncryptedWriter(raw, passphrase)
            with tarfile.open(fileobj=writer, mode="w|gz") as tar:
                for entry in files:
                    path = source / str(entry["path"])
                    info = tarfile.TarInfo("state/" + str(entry["path"]))
                    info.size = int(entry["size"])
                    info.mode = 0o600
                    with path.open("rb") as handle:
                        tar.addfile(info, handle)
                info = tarfile.TarInfo("manifest.json")
                info.size = len(manifest)
                info.mode = 0o600
                tar.addfile(info, io.BytesIO(manifest))
            writer.finish()
        # An in-flight write must invalidate the archive, not produce a
        # deceptively valid backup of mixed application states.
        if any(
            (source / str(entry["path"])).stat().st_size != entry["size"]
            or _hash_file(source / str(entry["path"])) != entry["sha256"]
            for entry in files
        ):
            raise ValueError("STATE_DIR changed during backup; stop all writers")
    except BaseException:
        if created:
            archive.unlink(missing_ok=True)
        raise
    return len(files)


def _safe_relative(name: str) -> Path:
    parsed = PurePosixPath(name)
    if (
        parsed.is_absolute()
        or not parsed.parts
        or parsed.parts[0] != "state"
        or len(parsed.parts) < 2
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or "\\" in name
        or ":" in name
    ):
        raise ValueError("Unsafe backup archive path")
    return Path(*parsed.parts[1:])


def restore_state(archive: Path, destination: Path, passphrase: str) -> int:
    """Verify/decrypt to an isolated directory, then rename atomically."""

    archive = archive.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if not archive.is_file() or not destination.parent.is_dir() or destination.exists():
        raise ValueError("Archive must exist and destination must be a new directory")
    if destination in {
        Path.cwd().resolve(), Path.home().resolve(), Path(destination.anchor)
    }:
        raise ValueError("Unsafe restore destination")
    # Do not repeat a long destination name: Windows' legacy path limit can
    # otherwise break restores of valid, nested PDF asset directories.
    stage = destination.parent / f".restore-{uuid4().hex}"
    if stage.resolve(strict=False).parent != destination.parent:
        raise ValueError("Unsafe staging directory")
    stage.mkdir(mode=0o700)
    restored: dict[str, dict[str, object]] = {}
    manifest = None
    total = 0
    try:
        with archive.open("rb") as raw:
            reader = _DecryptedReader(raw, passphrase)
            with tarfile.open(fileobj=reader, mode="r|gz") as tar:
                for member in tar:
                    if not member.isfile() or member.size < 0:
                        raise ValueError("Backup archive contains an unsupported entry")
                    if member.name == "manifest.json":
                        if manifest is not None or member.size > 10 * 1024**2:
                            raise ValueError("Invalid backup manifest")
                        manifest_file = tar.extractfile(member)
                        if manifest_file is None:
                            raise ValueError("Missing backup manifest")
                        manifest = json.load(manifest_file)
                        continue
                    if manifest is not None:
                        raise ValueError("Backup manifest must be last")
                    relative = _safe_relative(member.name)
                    key = relative.as_posix()
                    total += member.size
                    if key in restored or len(restored) >= MAX_FILES or total > MAX_TOTAL_BYTES:
                        raise ValueError("Duplicate or oversized backup entry")
                    target = stage / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = tar.extractfile(member)
                    if source is None:
                        raise ValueError("Cannot read backup entry")
                    digest = hashlib.sha256()
                    with target.open("xb") as output:
                        remaining = member.size
                        while remaining:
                            block = source.read(min(1024 * 1024, remaining))
                            if not block:
                                raise ValueError("Truncated backup entry")
                            output.write(block)
                            digest.update(block)
                            remaining -= len(block)
                    restored[key] = {"path": key, "size": member.size, "sha256": digest.hexdigest()}
            reader.verify_footer()
        if not isinstance(manifest, dict) or manifest.get("version") != 1:
            raise ValueError("Missing or unsupported backup manifest")
        expected = manifest.get("files")
        if not isinstance(expected, list) or len(expected) != len(restored):
            raise ValueError("Backup manifest file count mismatch")
        if {entry.get("path") for entry in expected if isinstance(entry, dict)} != set(restored):
            raise ValueError("Backup manifest paths mismatch")
        for entry in expected:
            if not isinstance(entry, dict) or restored.get(entry.get("path")) != entry:
                raise ValueError("Backup manifest hash or size mismatch")
        if destination.exists():
            raise ValueError("Restore destination appeared during verification")
        stage.rename(destination)
    except BaseException:
        if stage.exists() and stage.resolve().parent == destination.parent:
            shutil.rmtree(stage)
        raise
    return len(restored)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--source", type=Path, required=True)
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--port", type=int, default=8000)
    restore = commands.add_parser("restore")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    passphrase = os.environ.get("VERIDRA_BACKUP_PASSPHRASE") or getpass.getpass(
        "Backup passphrase (never shown): "
    )
    if args.command == "backup":
        if not 1 <= args.port <= 65535:
            parser.error("Backup --port must be the actual listening port")
        count = backup_state(args.source, args.output, passphrase, port=args.port)
        print(f"Encrypted and verified {count} files: {args.output}")
    else:
        count = restore_state(args.archive, args.destination, passphrase)
        print(f"Restored and verified {count} files: {args.destination}")


if __name__ == "__main__":
    main()
