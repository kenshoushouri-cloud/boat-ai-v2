#!/usr/bin/env python3
"""Offline verification helper for the existing 2026-10-19 V5 .age backup pair.

Runs on an INDEPENDENT machine, not the ConoHa production VPS.
No Drive API, no PostgreSQL connection, no secret read from GitHub or logs.
Default inspects only file metadata and SHA256, never decrypts.
--decrypt-toc checks age decryption + pg_restore -l in a private temp dir,
but does NOT prove full database restore, data completeness or 10/24 recency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

EXPECTED = {
    "main_current_20261019.dump.age": 297756932,
    "archive_current_20261019.dump.age": 52130144,
}
AGE_MAGIC = b"age-encryption.org/v1"


def inspect_file(path: Path, expected_size: int) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("STOP: encrypted input is absent, not a regular file or is a symlink")
    stat = path.stat()
    if stat.st_size != expected_size:
        raise ValueError("STOP: encrypted file size does not match inventory")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        header = f.read(len(AGE_MAGIC))
        if header != AGE_MAGIC:
            raise ValueError("STOP: encrypted file does not have age-v1 header")
        digest.update(header)
        while piece := f.read(1024 * 1024):
            digest.update(piece)
    return {"name": path.name, "bytes": stat.st_size, "sha256": digest.hexdigest()}


def verify_decrypt_toc(path: Path, identity: Path) -> str:
    if shutil.which("age") is None or shutil.which("pg_restore") is None:
        raise ValueError("STOP: age/pg_restore unavailable on independent host")
    if not identity.is_file() or identity.is_symlink():
        raise ValueError("STOP: local age identity absent or unsafe")
    if identity.stat().st_mode & 0o077:
        raise ValueError("STOP: age identity file must not be group/world readable")
    with tempfile.TemporaryDirectory(prefix="v5-offsite-verify-") as tmp:
        dump = Path(tmp) / "decrypted.dump"
        try:
            outcome = subprocess.run(
                ["age", "--decrypt", "--identity", str(identity),
                 "--output", str(dump), str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=180, check=False,
            )
            if outcome.returncode:
                raise ValueError("STOP: age decrypt failed (details suppressed)")
            if not dump.is_file() or dump.stat().st_size == 0:
                raise ValueError("STOP: decrypted dump is empty")
            listing = subprocess.run(
                ["pg_restore", "--list", str(dump)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=45, check=False,
            )
            if listing.returncode:
                raise ValueError("STOP: decrypted input is not a valid pg_restore archive")
            return "AGE_DECRYPT_AND_PG_RESTORE_TOC_PASS_ONLY"
        finally:
            # Keep temp path non-public and unlink decrypted dump even on errors.
            if dump.exists():
                dump.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True, help="local directory containing both unchanged .age files")
    parser.add_argument("--decrypt-toc", action="store_true")
    parser.add_argument("--identity", help="local age identity file path; NEVER paste its contents")
    parser.add_argument("--independent-machine-confirmed", action="store_true")
    args = parser.parse_args(argv)

    if args.decrypt_toc and (not args.independent_machine_confirmed or not args.identity):
        raise ValueError("STOP: explicit independent host/identity prerequisites absent")
    if args.decrypt_toc and (Path("/opt/boat-ai-v5").exists()
                             or Path("/opt/boat-ai-collector").exists()):
        raise ValueError("STOP: appears to be an active ConoHa production server")
    folder = Path(args.folder)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("STOP: input folder invalid")
    observations = []
    for name, size in EXPECTED.items():
        candidate = folder / name
        record = inspect_file(candidate, size)
        if args.decrypt_toc:
            record["format_check"] = verify_decrypt_toc(candidate, Path(args.identity))
        else:
            record["format_check"] = "DECRYPT_NOT_REQUESTED"
        observations.append(record)

    # SHA here covers Drive-downloaded ciphertext, NOT the existing 10/23-24
    # VPS plaintext dumps. Do not label two different generations as equivalent.
    print(json.dumps({
        "mode": "OFFSITE_AGE_BUNDLE_LOCAL_FILE_CHECK",
        "backup_generation": "2026-10-19",
        "items": observations,
        "full_independent_db_restore": "UNVERIFIED",
        "current_2026_10_24_generation": "NOT_COVERED",
        "live_postgres_access": "NONE",
        "production_cutover": "NO_GO",
    }, ensure_ascii=False, indent=2))
    print("V5_OFFSITE_ENCRYPTED_BUNDLE_FILE_CHECK_FINISHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
