#!/usr/bin/env python3
"""One-shot, fixed-date research audit. No Railway mutations or raw secret output."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

import audit_odds_evidence_20260908_pg as audit
import odds_evidence_privilege_guard as privilege_guard

REPO = "kenshoushouri-cloud/boat-ai-v2"
BRANCH = "research/odds-evidence-20260908"
CONFIRMATION = "AUDIT-2026-09-08-READ-ONLY"
OUTPUT = Path(".audit-results/odds-evidence-20260908.json")


class AuditGuardError(RuntimeError):
    pass


def authorize(env):
    expected = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_REF": "refs/heads/" + BRANCH,
        "GITHUB_ACTOR": "kenshoushouri-cloud",
        "AUDIT_DATE": audit.TARGET_DATE,
        "AUDIT_CONFIRMATION": CONFIRMATION,
    }
    if any(env.get(key) != value for key, value in expected.items()):
        raise AuditGuardError("execution_context_rejected")
    if not env.get("AUDIT_DATABASE_URL"):
        raise AuditGuardError("dedicated_database_credentials_missing")
    if any(not env.get(key) for key in ("AUDIT_DB_HOST", "AUDIT_DB_PORT", "AUDIT_DB_NAME")):
        raise AuditGuardError("approved_database_identity_missing")


def connection_info(url, *, expected_host, expected_port, expected_database):
    """Validate dedicated credentials and pinned endpoint before driver import.

    URL query options and ambient libpq connection defaults cannot weaken the
    explicit options below. The expected identity comes from separately
    approved GitHub configuration, not from the URL or Railway's admin URL.
    """
    try:
        if not isinstance(url, str) or not url or len(url) > 8192:
            raise ValueError("url")
        parts = urlsplit(url)
        if parts.scheme not in ("postgres", "postgresql"):
            raise ValueError("scheme")
        host = parts.hostname
        if not host or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.proxy\.rlwy\.net", host):
            raise ValueError("host")
        if any(label.startswith("-") or label.endswith("-") or len(label) > 63
               for label in host.split(".")):
            raise ValueError("host")
        port = parts.port
        if port is None or not 1 <= port <= 65535:
            raise ValueError("port")
        if not isinstance(expected_host, str) or host != expected_host:
            raise ValueError("expected_host")
        if not isinstance(expected_port, str) or not re.fullmatch(r"[1-9][0-9]*", expected_port):
            raise ValueError("expected_port")
        if port != int(expected_port):
            raise ValueError("expected_port")
        if parts.username is None or parts.password is None:
            raise ValueError("credentials")
        user = unquote(parts.username, errors="strict")
        password = unquote(parts.password, errors="strict")
        if user != privilege_guard.ROLE_NAME or not password or not parts.path.startswith("/"):
            raise ValueError("credentials")
        database = unquote(parts.path[1:], errors="strict")
        if not isinstance(expected_database, str) or not expected_database or database != expected_database:
            raise ValueError("database")
        if "/" in database or parts.fragment:
            raise ValueError("database")
        for value in (user, password, database):
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
                raise ValueError("control_character")
        for part in (parts.username, parts.password, parts.path, parts.query):
            if re.search(r"%(?![0-9a-fA-F]{2})", part):
                raise ValueError("percent_encoding")
    except (TypeError, ValueError, UnicodeError):
        raise AuditGuardError("dedicated_database_url_invalid") from None
    from psycopg.conninfo import make_conninfo
    return make_conninfo("", host=host, port=port, dbname=database,
        user=user, password=password, sslmode="verify-full",
        sslrootcert="/etc/ssl/certs/ca-certificates.crt", gssencmode="disable",
        options="-c search_path=pg_catalog -c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000 -c idle_in_transaction_session_timeout=30000",
        connect_timeout=10, application_name="odds_evidence_20260908")


def _safe_time(value):
    if value is None:
        return None
    try:
        return audit.iso(value)
    except (TypeError, ValueError, OverflowError):
        raise AuditGuardError("unexpected_audit_result") from None


def safe_report(result):
    """Allowlist evidence fields; never export raw odds vectors or DB strings."""
    if not isinstance(result, dict) or result.get("audit_date") != audit.TARGET_DATE:
        raise AuditGuardError("unexpected_audit_result")
    preflight = result.get("privilege_preflight")
    if (not isinstance(preflight, dict)
            or preflight.get("status") != "BOUNDED_PRIVILEGE_PREFLIGHT_PASSED"
            or type(preflight.get("server_version")) is not int
            or not privilege_guard.MIN_VERSION <= preflight["server_version"] < privilege_guard.MAX_VERSION):
        raise AuditGuardError("unexpected_audit_result")
    rows = result.get("races")
    if not isinstance(rows, list) or [r.get("race_id") for r in rows] != list(audit.TARGET_RACES):
        raise AuditGuardError("unexpected_audit_result")
    output = []
    for row in rows:
        base = row["base"]
        missing = base["missing"]
        if not isinstance(missing, list) or any(t not in audit.ALL_TICKETS for t in missing):
            raise AuditGuardError("unexpected_audit_result")
        output.append({
            "race_id": row["race_id"], "race_found": bool(row["race_found"]),
            "deadline_matches_reference": bool(row["deadline_matches_reference"]),
            "entry_status": "FULL6" if row["entry_status"] == "FULL6" else "UNVERIFIED",
            "base": {"expected": 120, "observed": int(base["observed"]),
                "distinct": int(base["distinct"]), "complete": bool(base["complete"]),
                "missing": missing, "unexpected_count": len(base["unexpected"]),
                "duplicates": int(base["duplicates"])},
            "base_fetched_at_min": _safe_time(row["base_fetched_at_min"]),
            "base_fetched_at_max": _safe_time(row["base_fetched_at_max"]),
            "base_timestamp_semantics": "current_saved_value_not_first_observation",
            "snapshot_statuses": {
                "recorded_candidates": sum(s["status"] == "RECORDED_PREDEADLINE_CANDIDATE" for s in row["snapshots"]),
                "unverified": sum(s["status"] != "RECORDED_PREDEADLINE_CANDIDATE" for s in row["snapshots"])},
            "independent_source_verification": "NOT_PERFORMED",
            "root_cause": "UNDETERMINED",
        })
    return {"audit_date": audit.TARGET_DATE, "execution_status": "READ_ONLY_QUERY_COMPLETED",
        "executed_at": datetime.now(timezone.utc).isoformat(), "scope": "fixed_19_races_expected_120_each",
        "privilege_preflight": preflight["status"],
        "preflight_server_version": preflight["server_version"],
        "schema": {"bao_snapshots_available": bool(result["schema"]["bao_snapshots_available"])},
        "races": output, "root_cause": "UNDETERMINED",
        "production_promotion": "BLOCKED", "historical_roi_approval": "BLOCKED"}


def main(env=None):
    env = os.environ if env is None else env
    stage = "authorization"
    try:
        authorize(env)
        stage = "connection_validation"
        conninfo = connection_info(env["AUDIT_DATABASE_URL"],
            expected_host=env["AUDIT_DB_HOST"], expected_port=env["AUDIT_DB_PORT"],
            expected_database=env["AUDIT_DB_NAME"])
        stage = "database_audit"
        result = audit.read_database(conninfo, expected_database=env["AUDIT_DB_NAME"])
        stage = "report_validation"
        report = safe_report(result)
        stage = "report_write"
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        print("AUDIT_FAILED=" + stage, file=sys.stderr)
        return 1
    print("AUDIT_COMPLETED=2026-09-08;RACES=19;ROOT_CAUSE=UNDETERMINED;ROI=BLOCKED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
