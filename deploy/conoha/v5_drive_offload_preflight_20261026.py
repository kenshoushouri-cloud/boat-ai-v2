#!/usr/bin/env python3
"""Secret-blind, non-destructive V5 Drive offload preflight.

Read only metadata of known local backup files; perform exactly one bounded
rclone Drive root-list request and one quota request.  NO backup reads, uploads,
downloads, deletions, DB activity, unit/timer edits, key reads or rclone config
prints.  A remote OAuth refresh may update the local rclone token cache.
This does not establish backup restore viability or authorize local removal.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

REMOTE = "v5_gdrive:"
BACKUP_SUFFIXES = (".dump", ".dump.age", ".backup", ".pgdump", ".sql.gz", ".tar.gz", ".tgz", ".zip", ".tar.zst", ".dump.zst")
SCAN_ROOTS = (Path("/root"), Path("/root/boat-v5-backups"))
BACKUP_DIR = Path("/var/backups")
MAX_ENTRIES = 1200

def say(k: str, v: object) -> None:
    print(f"{k}={v}", flush=True)

def read_dir(folder: Path, label: str, items: list) -> None:
    try:
        st = folder.lstat()
        if not stat.S_ISDIR(st.st_mode):
            say("DIR_" + label, "HOLD_NON_DIRECTORY")
            return
        with os.scandir(folder) as it:
            children = list(it)
        if len(children) > MAX_ENTRIES:
            say("DIR_" + label, "HOLD_TOO_MANY_ENTRIES")
            return
    except OSError:
        say("DIR_" + label, "ABSENT_OR_NO_ACCESS")
        return
    count = 0
    for child in children:
        if not child.name.endswith(BACKUP_SUFFIXES):
            continue
        try:
            st = child.stat(follow_symlinks=False)
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode):
            continue
        # No opening or hashing any file; report metadata only.
        count += 1
        items.append((str(Path(child.path)), st.st_size))
    say("DIR_" + label, f"META_ONLY_BACKUP_FILES_{count}")

def remote_cmd(command: list[str]) -> tuple[bool, object]:
    # Errors deliberately do not expose rclone diagnostic output or any token.
    try:
        p = subprocess.run(
            command + ["--retries", "1", "--low-level-retries", "1",
                       "--contimeout", "10s", "--timeout", "15s",
                       "--tpslimit", "0.3", "--checkers", "1"],
            check=False, capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        return False, None
    if p.returncode != 0 or len(p.stdout) > 1_500_000:
        return False, None
    try:
        return True, json.loads(p.stdout)
    except (ValueError, TypeError):
        return False, None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected-folder-id", required=True)
    args = ap.parse_args()
    fid = args.expected_folder_id
    if not (12 <= len(fid) <= 100 and
            all(ch.isascii() and (ch.isalnum() or ch in "-_") for ch in fid)):
        say("HOLD", "INVALID_EXPECTED_FOLDER_ID")
        return 2
    say("MODE", "LOCAL_METADATA_AND_MINIMAL_DRIVE_READONLY_PREFLIGHT")
    say("GOOGLE_DRIVE_WRITES", "NO")
    say("FILES_REMOVED", "NO")
    say("DB_OR_TIMER_CHANGES", "NO")
    say("CLIENT_ENCRYPTION", "NOT_YET_VERIFIED")
    say("RESTORE_TEST", "NOT_DONE")
    if os.geteuid() != 0:
        say("HOLD", "ROOT_REQUIRED_FOR_LOCAL_INVENTORY")
        return 2
    items: list[tuple[str, int]] = []
    for root in SCAN_ROOTS:
        read_dir(root, root.name if root.name != "root" else "root", items)
    try:
        with os.scandir(BACKUP_DIR) as scan:
            directories = [x for x in scan if
                           x.name.startswith("boat-") and
                           x.is_dir(follow_symlinks=False)]
        if len(directories) > MAX_ENTRIES:
            say("HOLD", "TOO_MANY_VAR_BACKUPS_DIRS")
            return 2
        for d in directories:
            read_dir(Path(d.path), d.name, items)
    except OSError:
        say("DIR_var_backups", "NOT_ACCESSIBLE")
    items.sort()
    say("BACKUP_FILE_CANDIDATES", len(items))
    say("BACKUP_TOTAL_BYTES", sum(size for _, size in items))
    # Display filename and size only (not content, config, credentials or keys).
    for i, (path, nbytes) in enumerate(items, 1):
        say(f"BACKUP_{i:02d}_FILE", path)
        say(f"BACKUP_{i:02d}_BYTES", nbytes)

    for exe in ("rclone", "age", "pg_dump", "pg_restore", "sha256sum"):
        if not shutil.which(exe):
            say("HOLD", "MISSING_BINARY_" + exe.upper())
            return 2

    # An existing private V5 folder on Drive account B was read by connector;
    # matching its Drive folder ID from THIS remote is required before uploads.
    ok, ls = remote_cmd([
        "rclone", "lsjson", REMOTE, "--dirs-only", "--max-depth", "1"])
    if not ok or not isinstance(ls, list):
        say("HOLD", "RCLONE_DRIVE_ROOT_QUERY_FAILED_OR_RATE_LIMIT")
        return 2
    matches = [x for x in ls if isinstance(x, dict)
               and x.get("ID") == fid and x.get("IsDir") is True]
    if len(matches) != 1:
        say("HOLD", "RCLONE_REMOTE_NOT_PROVEN_SAME_AS_V5_DRIVE_ACCOUNT_B")
        return 2
    say("REMOTE_IDENTITY", "V5_FOLDER_ID_MATCHED_ACCOUNT_B")

    quota_ok, info = remote_cmd(["rclone", "about", REMOTE, "--json"])
    if not quota_ok or not isinstance(info, dict):
        say("HOLD", "REMOTE_QUOTA_UNVERIFIED")
        return 2
    free = info.get("free")
    if not isinstance(free, (int, float)) or free < 0:
        say("HOLD", "REMOTE_AVAILABLE_QUOTA_UNKNOWN")
        return 2
    say("REMOTE_AVAILABLE_BYTES", int(free))
    say("PREFLIGHT", "PASS_REMOTE_IDENTITY_AND_QUOTA_METADATA_ONLY")
    say("NEXT_GATES", "AGE_RECIPIENT_VERIFIED;NO_OVERWRITE_UPLOAD;RETRIEVED_SHA256;INDEPENDENT_RESTORE;SEPARATE_LOCAL_DELETE_APPROVAL")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
