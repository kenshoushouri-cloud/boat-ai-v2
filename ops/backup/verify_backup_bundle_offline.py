#!/usr/bin/env python3
"""Read-only local acceptance gate for a copied .dump.age/.sha256/.ready bundle.

No decryption, DB/Drive access, keys, restoration, network, subprocess or writes.
PASS proves only consistency of this local trio, not authenticity or restorability.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import stat

TARGETS = ("v3", "archive", "v4", "v5")
NAME_RE = re.compile(r"boat-ai-(v3|archive|v4|v5)-(\d{8}T\d{6}Z)-([0-9a-f]{10})\.dump\.age\Z")
SHA_RE = re.compile(rb"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)\n\Z")
MAX_SIDECAR_BYTES = 256


class BundleRejected(Exception):
    pass


def read_regular(path: Path, *, max_bytes: int | None = None) -> bytes | str:
    """No symlinks/devices/FIFOs, even if changed between lstat and open."""
    try:
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode):
            raise BundleRejected("NOT_REGULAR_FILE")
        if max_bytes is not None and st.st_size > max_bytes:
            raise BundleRejected("SIDECAR_TOO_LARGE")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise BundleRejected("NOT_REGULAR_FILE")
            if max_bytes is not None:
                if opened.st_size > max_bytes:
                    raise BundleRejected("SIDECAR_TOO_LARGE")
                contents = stream.read(max_bytes + 1)
                if len(contents) > max_bytes:
                    raise BundleRejected("SIDECAR_TOO_LARGE")
                return contents
            if opened.st_size == 0:
                raise BundleRejected("EMPTY_ENCRYPTED_FILE")
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
            return digest.hexdigest()
    except (OSError, ValueError) as exc:
        raise BundleRejected("FILE_UNAVAILABLE") from exc


def verify(directory: Path, filename: str, target: str) -> int:
    if target not in TARGETS:
        raise BundleRejected("UNKNOWN_TARGET")
    # Reject paths rather than normalizing them; no traversal or arbitrary files.
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise BundleRejected("UNSAFE_FILENAME")
    match = NAME_RE.fullmatch(filename)
    if match is None:
        raise BundleRejected("INVALID_FILENAME")
    if match.group(1) != target:
        raise BundleRejected("TARGET_MISMATCH")
    try:
        if datetime.strptime(match.group(2), "%Y%m%dT%H%M%SZ").strftime("%Y%m%dT%H%M%SZ") != match.group(2):
            raise ValueError("non-canonical time")
    except ValueError as exc:
        raise BundleRejected("INVALID_TIMESTAMP") from exc
    if not directory.is_dir() or directory.is_symlink():
        raise BundleRejected("DIRECTORY_UNAVAILABLE")
    for suffix in (".uploading", ".sha256.uploading", ".ready.uploading"):
        if (directory / (filename + suffix)).exists() or (directory / (filename + suffix)).is_symlink():
            raise BundleRejected("INCOMPLETE_STAGING_PRESENT")
    sha_sidecar = read_regular(directory / (filename + ".sha256"), max_bytes=MAX_SIDECAR_BYTES)
    ready_marker = read_regular(directory / (filename + ".ready"), max_bytes=MAX_SIDECAR_BYTES)
    if not isinstance(sha_sidecar, bytes) or not isinstance(ready_marker, bytes):
        raise BundleRejected("INVALID_SIDECAR")
    if sha_sidecar != ready_marker:
        raise BundleRejected("SIDECAR_MARKER_MISMATCH")
    info = SHA_RE.fullmatch(sha_sidecar)
    if info is None or info.group(2) != filename.encode("ascii"):
        raise BundleRejected("INVALID_SIDECAR_FORMAT_OR_NAME")
    actual_hash = read_regular(directory / filename)
    if actual_hash != info.group(1).decode("ascii"):
        raise BundleRejected("SHA256_MISMATCH")
    return (directory / filename).stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline read-only .dump.age/.sha256/.ready validation")
    parser.add_argument("--directory", type=Path, required=True, help="already downloaded, trusted local folder")
    parser.add_argument("--filename", required=True, help="basename such as boat-ai-v3-20261014T100000Z-0123456789.dump.age")
    parser.add_argument("--target", choices=TARGETS, required=True)
    args = parser.parse_args()
    try:
        size = verify(args.directory, args.filename, args.target)
    except BundleRejected as exc:
        print(f"BUNDLE_ACCEPT=REJECT reason:{exc}")
        print("RESTORE_VERIFIED=NO")
        return 2
    print("BUNDLE_ACCEPT=PASS_LOCAL_SHA256_ONLY")
    print(f"TARGET={args.target} ENCRYPTED_BYTES={size}")
    print("REMOTE_ORIGIN_VERIFIED=NO RESTORE_VERIFIED=NO BUY=HARD_HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
