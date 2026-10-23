#!/usr/bin/env python3
"""Read-only, secret-blind ConoHa backup/restore path inventory.

Only checks binary availability, known directory/file metadata and aggregate
local backup counts. Never reads rclone.conf, age keys, dumps, environment
values, or database connections. Never executes rclone/age/pg_restore/pg_dump,
downloads files, creates files, schedules jobs, or changes services.
NOT a restore test or confirmation of recent independent backup coverage.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import stat

# Fixed, conservative locations only. No recursive search or mounted cloud
# drive probing. Existing local encrypted key material is NOT enumerated.
DIRECTORIES = (
    ("k_results_local", Path("/root/boat-v5-backups")),
    ("root_level", Path("/root")),
    ("root_backups", Path("/root/backups")),
    ("opt_backups", Path("/opt/boat-ai-v5/backups")),
    ("legacy_backups", Path("/opt/boat-ai-v5-backups")),
)
TOOLS = ("pg_dump", "pg_restore", "psql", "age", "rclone", "sha256sum")
EXTENSIONS = {
    "encrypted_pg_dump": ".dump.age",
    "plain_pg_dump": ".dump",
    "sha256_sidecar": ".sha256",
}
MAX_DIRECTORY_ENTRIES = 4096


def utcstamp(epoch: float | None) -> str:
    if epoch is None:
        return "NOT_FOUND"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def inspect_directory(label: str, folder: Path) -> str:
    """Only aggregate safe backup extensions; do not print filenames."""
    try:
        info = folder.lstat()
    except OSError:
        return f"LOCAL_DIR={label}|status=NOT_ACCESSIBLE_OR_ABSENT"
    if not stat.S_ISDIR(info.st_mode):
        return f"LOCAL_DIR={label}|status=NOT_REAL_DIRECTORY"
    counts = {kind: 0 for kind in EXTENSIONS}
    sizes = {kind: 0 for kind in EXTENSIONS}
    newest = None
    entries_seen = 0
    try:
        with os.scandir(folder) as iterator:
            for entry in iterator:
                entries_seen += 1
                if entries_seen > MAX_DIRECTORY_ENTRIES:
                    return f"LOCAL_DIR={label}|status=TOO_MANY_ENTRIES_NOT_SCANNED"
                # Never follow symlinks into additional locations.
                if not entry.is_file(follow_symlinks=False):
                    continue
                name = entry.name
                matched = None
                for kind, suffix in EXTENSIONS.items():
                    if name.endswith(suffix):
                        matched = kind
                        break
                if matched is None:
                    continue
                fileinfo = entry.stat(follow_symlinks=False)
                counts[matched] += 1
                sizes[matched] += fileinfo.st_size
                newest = max(newest or 0, fileinfo.st_mtime)
    except OSError:
        return f"LOCAL_DIR={label}|status=PERMISSION_OR_METADATA_ERROR"
    result = [f"LOCAL_DIR={label}", "status=SCANNED_METADATA_ONLY"]
    for kind in EXTENSIONS:
        result.append(f"{kind}_files={counts[kind]}")
        result.append(f"{kind}_bytes={sizes[kind]}")
    result.append("latest_matching_file_mtime_UTC=" + utcstamp(newest))
    return "|".join(result)


def main() -> int:
    print("V5_BACKUP_RESTORE_INVENTORY_READONLY_BEGIN")
    print("DATA_READ=NONE|SECRETS_READ=NONE|CLOUD_CONTACT=NONE|DB_CONTACT=NONE")
    print("PROCESS_EUID_IS_ROOT=" + ("YES" if os.geteuid() == 0 else "NO"))
    for name in TOOLS:
        print("BINARY_" + name.upper() + "="
              + ("ON_PATH" if shutil.which(name) else "NOT_ON_PATH"))
    # Presence only: neither parse nor display rclone remotes/tokens.
    for label, name in (
        ("root_xdg", "/root/.config/rclone/rclone.conf"),
        ("root_legacy", "/root/.rclone.conf"),
    ):
        try:
            kind = os.stat(name, follow_symlinks=False)
            is_regular = stat.S_ISREG(kind.st_mode)
        except OSError:
            is_regular = False
        print("RCLONE_CONFIG_" + label + "="
              + ("PRESENT_NOT_READ" if is_regular else "ABSENT_OR_NOT_READABLE"))
    for label, folder in DIRECTORIES:
        print(inspect_directory(label, folder))
    try:
        storage = shutil.disk_usage("/")
        print("ROOT_FILESYSTEM_FREE_BYTES=" + str(storage.free))
    except OSError:
        print("ROOT_FILESYSTEM_FREE_BYTES=UNKNOWN")
    print("GOOGLE_DRIVE_CONTENT_NOT_REVALIDATED")
    print("AGE_KEY_AND_PASSWORD_NOT_INSPECTED")
    print("PG_RESTORE_TOC_NOT_EXECUTED")
    print("INDEPENDENT_RESTORE_NOT_TESTED")
    print("CURRENT_BACKUP_COVERAGE_NOT_VERIFIED")
    print("NIGHT_CUTOVER_GATE=NO_GO")
    print("V5_BACKUP_PATH_AUDIT_COMPLETE_NO_WRITES_NO_BUY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
