#!/usr/bin/env python3
"""Locate the ONE 2026-10-24 history dump by bounded glob and SHA256 it.

Read-only; no DB access, no HTTP, no rename/delete, no reading secrets.
Handles exact-case differences in historical evidence path safely.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import stat
import sys

BASE = Path("/var/backups")
PATTERN = "boat-history-20261024-*/boat_history_archive.dump"
EXPECTED_SIZE = 81865791
EXPECTED_SHA = "7301975821593cdab2fdcf30eedc8d78558537023ed7af30f03d679de19fd37e"


def main() -> int:
    print("MODE=READ_ONLY_LOCAL_HISTORY_FILE_DISCOVERY_AND_HASH")
    try:
        files = sorted(BASE.glob(PATTERN))
    except OSError:
        print("HOLD=HISTORY_PATH_SEARCH_INACCESSIBLE")
        return 2
    print(f"HISTORY_CANDIDATES={len(files)}")
    if len(files) != 1:
        print("HOLD=EXPECTED_EXACTLY_ONE_HISTORY_FILE")
        return 2

    path = files[0]
    # Parent and file may not be symlinks: reject unexpected redirects.
    try:
        directory = path.parent
        parent = directory.lstat()
        if not stat.S_ISDIR(parent.st_mode):
            raise OSError("history directory not a real directory")
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise OSError("history file not regular")
            print(f"HISTORY_DISCOVERED_DIR={directory.name}")
            print(f"HISTORY_FILE_BYTES={before.st_size}")
            if before.st_size != EXPECTED_SIZE:
                print("HOLD=HISTORY_SIZE_MISMATCH")
                return 2
            digest = hashlib.sha256()
            n = 0
            with os.fdopen(fd, "rb", closefd=False) as handle:
                while chunk := handle.read(1024 * 1024):
                    n += len(chunk)
                    digest.update(chunk)
            after = os.fstat(fd)
            if (after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns
                    or after.st_ino != before.st_ino or n != EXPECTED_SIZE):
                print("HOLD=HISTORY_CHANGED_DURING_SCAN")
                return 2
            if digest.hexdigest() != EXPECTED_SHA:
                print("HOLD=HISTORY_SHA256_MISMATCH")
                return 2
        finally:
            os.close(fd)
    except (OSError, ValueError):
        print("HOLD=HISTORY_NOT_ACCESSIBLE_OR_NOT_REGULAR")
        return 2

    print("HISTORY_LOCAL_SHA256=PASS_BASELINE_20261024")
    print("HISTORY_LOCAL_SHA_VERIFICATION_ONLY_NO_CLOUD_COPY_NO_RESTORE")
    print("NO_NETWORK=YES NO_DB_WRITES=YES NO_LOCAL_DELETION=YES BUY=OFF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
