"""Optional LOCAL-ONLY, opt-in psql launcher for V5 catalogue preflight.

Neither importing nor default CLI execution opens a connection. It never
reads Railway variables via API, schedules Actions, scans race rows or writes DB.
No secrets are passed on the command line or printed in errors.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

SQL_BLOB_SHA = "7c69a740b460d1e049c846df130d79d3ed192c8b"
ENABLE = "YES_METADATA_ONLY"
TARGET = "HISTORY_ARCHIVE_CONFIRMED"


def verified_sql(path: Path) -> Path:
    """Pin the exact GitHub-reviewed SQL; refuse unreviewed SQL revisions."""
    data = path.read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if actual != SQL_BLOB_SHA:
        raise ValueError("PREFLIGHT_SQL_HASH_MISMATCH")
    return path.resolve()


def connection_profile(env: dict[str, str]) -> dict[str, str]:
    """Use libpq PG* env/.pgpass; never pass a URL/password in argv."""
    if not env.get("PGSERVICE") and not all(env.get(k) for k in
                                             ("PGHOST", "PGDATABASE", "PGUSER")):
        raise ValueError("LIBPQ_PROFILE_REQUIRED")
    result = {k: v for k, v in env.items()
              if k.startswith("PG") or k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")}
    result["PGCONNECT_TIMEOUT"] = "3"
    result["PGAPPNAME"] = "v5_catalog_readonly_once"
    # Session is read-only even if the SQL file's BEGIN is changed (it cannot be,
    # because verified_sql pins its immutable Git object SHA).
    result["PGOPTIONS"] = ("-c default_transaction_read_only=on "
                           "-c statement_timeout=2000 "
                           "-c lock_timeout=250 "
                           "-c max_parallel_workers_per_gather=0")
    return result


def execute_once(
    env: dict[str, str] | None = None,
    sql_path: Path | None = None,
    run_command=None,
) -> dict[str, object]:
    """Only explicitly authorized interactive use connects; never a cron job."""
    current = dict(os.environ if env is None else env)
    if (current.get("V5_PREFLIGHT_OPT_IN") != ENABLE
            or current.get("V5_PREFLIGHT_DB_TARGET") != TARGET):
        return {"status": "DISABLED_BY_DEFAULT", "database_read_executed": False}
    source = sql_path or Path(__file__).with_name(
        "v5_seven_day_archive_db_preflight_readonly.sql")
    checked = verified_sql(Path(source))
    profile = connection_profile(current)
    command = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
               "-P", "pager=off", "--no-align", "--file", str(checked)]
    runner = subprocess.run if run_command is None else run_command
    try:
        outcome = runner(command, env=profile, capture_output=True, text=True,
                         timeout=12, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return {"status": "LOCAL_PREFLIGHT_EXECUTION_FAILED",
                "database_read_executed": "UNKNOWN_NO_SUCCESS_CLAIM"}
    if outcome.returncode != 0:
        # Never echo libpq exceptions: these may contain credentials/hosts.
        return {"status": "LOCAL_PREFLIGHT_SQL_FAILED",
                "database_read_executed": "UNKNOWN_NO_SUCCESS_CLAIM"}
    # Metadata only. Caller must review 20 required fields, index flags and
    # transaction_read_only=on; a completed query is NOT a schema PASS.
    return {"status": "CATALOG_RESULTS_REQUIRE_MANUAL_REVIEW",
            "database_read_executed": True,
            "catalog_output": outcome.stdout[:12000],
            "forward_eligible": False, "buy_eligible": False}


def main() -> int:
    try:
        result = execute_once()
    except (ValueError, OSError):
        result = {"status": "LOCAL_PREFLIGHT_SETUP_REJECTED",
                  "database_read_executed": False}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in (
        "DISABLED_BY_DEFAULT", "CATALOG_RESULTS_REQUIRE_MANUAL_REVIEW") else 2


if __name__ == "__main__":
    raise SystemExit(main())
