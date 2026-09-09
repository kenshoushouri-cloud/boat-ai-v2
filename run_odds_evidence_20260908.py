#!/usr/bin/env python3
"""One-shot, fixed-date research audit. No Railway mutations or raw secret output."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

import audit_odds_evidence_20260908_pg as audit

REPO = "kenshoushouri-cloud/boat-ai-v2"
BRANCH = "research/odds-evidence-20260908"
PROJECT = "268a5b17-0712-440a-884d-27f7fa887a2d"
ENVIRONMENT = "5ffb02f6-5ec8-4268-9bda-8e30431ff625"
SERVICE = "aa4b9c32-f2bf-42c8-89b9-f5aac8d70fb3"
CONFIRMATION = "AUDIT-2026-09-08-READ-ONLY"
ENDPOINT = "https://backboard.railway.com/graphql/v2"
OUTPUT = Path(".audit-results/odds-evidence-20260908.json")
QUERY = """query AuditConnection($p:String!, $e:String!, $s:String!) {
  projectToken { projectId environmentId }
  service(id:$s) { id name }
  variables(projectId:$p, environmentId:$e, serviceId:$s, unrendered:false)
}"""


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
    if not env.get("RAILWAY_TOKEN"):
        raise AuditGuardError("railway_token_missing")


def resolve_public_url(token, opener=urllib.request.urlopen):
    payload = json.dumps({"query": QUERY, "variables": {
        "p": PROJECT, "e": ENVIRONMENT, "s": SERVICE,
    }}).encode("utf-8")
    request = urllib.request.Request(ENDPOINT, data=payload, method="POST", headers={
        "Project-Access-Token": token,
        "Content-Type": "application/json",
        "User-Agent": "boat-ai-v2-odds-evidence-audit",
    })
    try:
        with opener(request, timeout=15) as response:
            result = json.loads(response.read(262145).decode("utf-8"))
    except Exception:
        raise AuditGuardError("railway_read_failed") from None
    if not isinstance(result, dict) or result.get("errors"):
        raise AuditGuardError("railway_read_failed")
    data = result.get("data")
    if not isinstance(data, dict):
        raise AuditGuardError("railway_read_failed")
    context, service = data.get("projectToken"), data.get("service")
    if not isinstance(context, dict) or not isinstance(service, dict):
        raise AuditGuardError("railway_identity_mismatch")
    if (context.get("projectId"), context.get("environmentId")) != (PROJECT, ENVIRONMENT):
        raise AuditGuardError("railway_identity_mismatch")
    if (service.get("id"), service.get("name")) != (SERVICE, "postgres-recovery"):
        raise AuditGuardError("railway_identity_mismatch")
    variables = data.get("variables")
    if not isinstance(variables, dict):
        raise AuditGuardError("public_database_url_missing")
    url = variables.get("DATABASE_PUBLIC_URL")
    if not isinstance(url, str) or not url:
        raise AuditGuardError("public_database_url_missing")
    return url


def connection_info(url):
    """Validate the public endpoint before importing the database driver.

    Only the authority, database and credentials are carried forward. Query
    options supplied in the URL cannot override our connection safeguards.
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
        if parts.username is None or parts.password is None:
            raise ValueError("credentials")
        user = unquote(parts.username, errors="strict")
        password = unquote(parts.password, errors="strict")
        if not user or not password or not parts.path.startswith("/"):
            raise ValueError("credentials")
        database = unquote(parts.path[1:], errors="strict")
        if not database or "/" in database or parts.fragment:
            raise ValueError("database")
        for value in (user, password, database):
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
                raise ValueError("control_character")
        for part in (parts.username, parts.password, parts.path, parts.query):
            if re.search(r"%(?![0-9a-fA-F]{2})", part):
                raise ValueError("percent_encoding")
    except (TypeError, ValueError, UnicodeError):
        raise AuditGuardError("public_database_url_invalid") from None
    # Import only after every URL guard has passed. Do not put the URL in an
    # exception, log, subprocess argument, or artifact.
    from psycopg.conninfo import make_conninfo
    return make_conninfo("", host=host, port=port, dbname=database,
        user=user, password=password, sslmode="require",
        options="-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000 -c idle_in_transaction_session_timeout=30000",
        connect_timeout=10, application_name="odds_evidence_20260908")


def safe_report(result):
    """Allowlist evidence fields; never export raw odds vectors or DB strings."""
    if result.get("audit_date") != audit.TARGET_DATE:
        raise AuditGuardError("unexpected_audit_result")
    rows = result.get("races")
    if not isinstance(rows, list) or [r.get("race_id") for r in rows] != list(audit.TARGET_RACES):
        raise AuditGuardError("unexpected_audit_result")
    output = []
    for row in rows:
        base = row["base"]
        missing = base["missing"]
        if any(t not in audit.ALL_TICKETS for t in missing):
            raise AuditGuardError("unexpected_audit_result")
        output.append({
            "race_id": row["race_id"], "race_found": bool(row["race_found"]),
            "deadline_matches_reference": bool(row["deadline_matches_reference"]),
            "entry_status": "FULL6" if row["entry_status"] == "FULL6" else "UNVERIFIED",
            "base": {"expected": 120, "observed": int(base["observed"]),
                "distinct": int(base["distinct"]), "complete": bool(base["complete"]),
                "missing": missing, "unexpected_count": len(base["unexpected"]),
                "duplicates": int(base["duplicates"])},
            "base_fetched_at_min": row["base_fetched_at_min"],
            "base_fetched_at_max": row["base_fetched_at_max"],
            "base_timestamp_semantics": "current_saved_value_not_first_observation",
            "snapshot_statuses": {
                "recorded_candidates": sum(s["status"] == "RECORDED_PREDEADLINE_CANDIDATE" for s in row["snapshots"]),
                "unverified": sum(s["status"] != "RECORDED_PREDEADLINE_CANDIDATE" for s in row["snapshots"])},
            "independent_source_verification": "NOT_PERFORMED",
            "root_cause": "UNDETERMINED",
        })
    return {"audit_date": audit.TARGET_DATE, "execution_status": "READ_ONLY_QUERY_COMPLETED",
        "executed_at": datetime.now(timezone.utc).isoformat(), "scope": "fixed_19_races_expected_120_each",
        "schema": {"bao_snapshots_available": bool(result["schema"]["bao_snapshots_available"])},
        "races": output, "root_cause": "UNDETERMINED",
        "production_promotion": "BLOCKED", "historical_roi_approval": "BLOCKED"}


def main(env=None):
    env = os.environ if env is None else env
    stage = "authorization"
    try:
        authorize(env)
        stage = "railway_read"
        url = resolve_public_url(env["RAILWAY_TOKEN"])
        stage = "database_audit"
        result = audit.read_database(connection_info(url))
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
