#!/usr/bin/env python3
"""LOCAL ONLY rclone config status diagnostic. No Drive API, DB or writes.

Never prints tokens, IDs, passwords, credential paths or raw config.
No remote calls; reading local rclone configuration requires root.
This does NOT prove account identity, token validity, quota, or cloud access.
"""
from __future__ import annotations
import configparser
import json
import os
import stat
import sys
from pathlib import Path

ALLOWED = ("v5_gdrive", "gdrive_a_backup", "drive")

def out(label: str, value: str) -> None:
    print(f"{label}={value}", flush=True)

def main() -> int:
    out("MODE", "LOCAL_RCLONE_CONFIG_METADATA_ONLY_NO_NETWORK")
    out("REMOTE_API_REQUESTS", "0")
    out("UPLOAD_DOWNLOAD_DELETE", "NO")
    out("DB_TIMER_AND_BUY_CHANGES", "NO")
    if os.geteuid() != 0:
        out("HOLD", "ROOT_REQUIRED")
        return 2
    env_path = os.environ.get("RCLONE_CONFIG")
    if env_path:
        path = Path(env_path)
        out("CONFIG_SELECTION", "RCLONE_CONFIG_ENV")
    else:
        home = Path(os.environ.get("XDG_CONFIG_HOME", "/root/.config"))
        path = home / "rclone" / "rclone.conf"
        out("CONFIG_SELECTION", "ROOT_XDG_DEFAULT")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size > 1_000_000:
                raise OSError("invalid config file")
            with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as handle:
                payload = handle.read()
        finally:
            os.close(fd)
    except (OSError, UnicodeError):
        out("HOLD", "CONFIG_NOT_ACCESSIBLE_OR_UNEXPECTED_FORMAT")
        return 2

    parser = configparser.RawConfigParser(interpolation=None, strict=False)
    try:
        parser.read_string(payload)
    except configparser.Error:
        out("HOLD", "CONFIG_NOT_PARSEABLE_ENCRYPTED_OR_UNEXPECTED")
        return 2
    finally:
        del payload
    for name in ALLOWED:
        label = name.upper()
        if not parser.has_section(name):
            out(f"{label}_PRESENT", "NO")
            continue
        out(f"{label}_PRESENT", "YES")
        def present(key: str) -> bool:
            return bool((parser.get(name, key, fallback="") or "").strip())
        out(f"{label}_TYPE", "DRIVE" if parser.get(name, "type", fallback="").strip() == "drive" else "NOT_DRIVE")
        for key, suffix in (
            ("root_folder_id", "ROOT_ID_SET"),
            ("team_drive", "TEAM_DRIVE_SET"),
            ("client_id", "CUSTOM_CLIENT_ID_SET"),
            ("client_secret", "CLIENT_SECRET_SET"),
            ("service_account_file", "SERVICE_ACCOUNT_FILE_SET"),
            ("scope", "SCOPE_EXPLICIT"),
            ("token", "OAUTH_TOKEN_CONFIGURED"),
        ):
            out(f"{label}_{suffix}", "YES" if present(key) else "NO")
        if present("token"):
            try:
                tok = json.loads(parser.get(name, "token"))
                out(f"{label}_OAUTH_REFRESH_FIELD", "YES" if isinstance(tok, dict) and bool(tok.get("refresh_token")) else "NO_OR_UNREADABLE")
            except (ValueError, TypeError):
                out(f"{label}_OAUTH_REFRESH_FIELD", "NO_OR_UNREADABLE")
    out("DRIVE_IDENTITY", "NOT_VERIFIED")
    out("API_RATE_LIMIT", "NOT_TESTED")
    out("DO_NOT_DELETE_BACKUPS", "YES")
    out("VERDICT", "LOCAL_CONFIG_FLAGS_ONLY_NEED_REMOTE_IDENTITY_AND_QUOTA_LATER")
    return 0

if __name__ == "__main__":
    sys.exit(main())
