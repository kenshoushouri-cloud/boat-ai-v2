#!/usr/bin/env python3
"""Read-only, fail-closed integrity gate for 5 known local V5 restore assets.

Exactly checks bytes/SHA256 recorded in GitHub's 2026-10-24 evidence.
No DB access, no network, no dump/tar extraction, no secrets access, no writes.
Use nice/ionice when executed on ConoHa; do not run during resource pressure.
This is *not* a latest/remote/independently-restored backup verification.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys

ASSETS = (
    ("railway_20261023",
     "/var/backups/boat-railway-20261023-ORfLpY/railway.dump",
     393138215, "4ee6a5d9c1ddf67c61b8bb82426961431c25f20f944f87b6cef5137bb294478d"),
    ("history_20261024",
     "/var/backups/boat-history-20261024-U6CRLt/boat_history_archive.dump",
     81865791, "7301975821593cdab2fdcf30eedc8d78558537023ed7af30f03d679de19fd37e"),
    ("collector_tar_20261024",
     "/var/backups/boat-collector-20261024-7Tn5rg/collector.tar",
     2283520, "823a46ee4820e66373abaec7d6e099c3e1d99ae019488691e03d6fbd2a4d7d62"),
    ("v5_runtime_tar_20261024",
     "/var/backups/boat-v5-20261024-Dip2iAH2/v5-runtime.tar",
     25200640, "4f1b2c6cd497e0300b34bad2e08aa570b5eeab09b472bf0be846f89d8c954968"),
    ("systemd_tar_20261024",
     "/var/backups/boat-v5-systemd-20261024-Qwz5OloV/units.tar",
     20480, "dc2b54596477a6440f51596d76a84285ea3cf203522355cc1eb4393b224936fb"),
)


def sha_and_size(path: str):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink < 1:
            raise OSError("not a regular file")
        if st.st_size > 2_000_000_000:
            raise OSError("unexpectedly large file")
        hasher = hashlib.sha256()
        size = 0
        with os.fdopen(fd, "rb", closefd=False) as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
                size += len(chunk)
        after = os.fstat(fd)
        if size != st.st_size or st.st_size != after.st_size or st.st_mtime_ns != after.st_mtime_ns or st.st_ino != after.st_ino:
            raise OSError("file changed during read")
        return size, hasher.hexdigest()
    finally:
        os.close(fd)


def main() -> int:
    print("MODE=READ_ONLY_5_ASSETS_NO_NETWORK_NO_DB_NO_WRITES")
    failures = 0
    total = 0
    for label, path, expected_size, expected_sha in ASSETS:
        # Display logical labels only; do not expose file contents or secrets.
        try:
            if not Path(path).is_file():
                raise OSError("not accessible regular file")
            size, digest = sha_and_size(path)
            valid = size == expected_size and digest == expected_sha
            total += size if valid else 0
            print(f"ASSET_{label}={'MATCH' if valid else 'HOLD_MISMATCH'} bytes={size} expected_bytes={expected_size}")
            failures += not valid
        except OSError:
            print(f"ASSET_{label}=HOLD_MISSING_OR_INACCESSIBLE")
            failures += 1
    print(f"VERIFIED_LOCAL_ASSETS={len(ASSETS)-failures}/{len(ASSETS)}")
    print(f"VERIFIED_LOCAL_BYTES={total}")
    print("REMOTE_COPY=NOT_DONE LOCAL_DELETE=NO RESTORE_OUTSIDE_VPS=NOT_DONE")
    print("V5_PRODUCTION_BACKUP_CURRENT_AS_OF_20261026=NO")
    if failures:
        print("V5_LOCAL_CHECKSUM_GATE=HOLD")
        return 2
    print("V5_LOCAL_CHECKSUM_GATE=PASS_FOR_20261023_24_EXISTING_FILES_ONLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
