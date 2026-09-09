#!/usr/bin/env python3
"""Approval-gated one-shot production executor for the 2026-09-08 evidence audit.

This entrypoint is deliberately narrow:
- it accepts only the approved push context on the research branch;
- it provisions a fresh dedicated audit role with a random in-memory password;
- it executes only the fixed 19-race read-only audit through that login;
- it drops the temporary role after success or failure;
- it emits only sanitized result files and status text.

It never changes application rows, Railway configuration, Cron, or PUBLIC grants.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import audit_odds_evidence_20260908_pg as audit
import odds_evidence_privilege_guard as guard
import odds_evidence_role_provisioning as provisioning
import run_odds_evidence_20260908 as runner

REPO = "kenshoushouri-cloud/boat-ai-v2"
BRANCH = "research/odds-evidence-20260908"
OWNER = "kenshoushouri-cloud"
CONFIRMATION = "PROVISION-AND-AUDIT-2026-09-08-ONCE"
COMMIT_MESSAGE = "PRODUCTION-AUDIT-2026-09-08-APPROVED-ONCE"
RESULT_DIR = Path(".audit-results")
REPORT_PATH = RESULT_DIR / "odds-evidence-20260908.json"
EXECUTION_PATH = RESULT_DIR / "production-execution.json"
_HOST_RE = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.proxy\.rlwy\.net")
_DB_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$-]{0,62}")


class ProductionExecutionError(RuntimeError):
    """Fixed, non-sensitive production-execution failure."""


def authorize(env) -> None:
    expected = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_REF": "refs/heads/" + BRANCH,
        "GITHUB_ACTOR": OWNER,
        "GITHUB_RUN_ATTEMPT": "1",
        "PRODUCTION_EXECUTION_CONFIRMATION": CONFIRMATION,
        "PRODUCTION_EXECUTION_COMMIT_MESSAGE": COMMIT_MESSAGE,
    }
    if any(env.get(key) != value for key, value in expected.items()):
        raise ProductionExecutionError("production_execution_context_rejected")
    sha = env.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ProductionExecutionError("production_execution_context_rejected")
    if not env.get("ADMIN_DATABASE_URL"):
        raise ProductionExecutionError("admin_database_credentials_missing")


def _decode(raw: str | None) -> str:
    if raw is None:
        raise ProductionExecutionError("admin_database_url_invalid")
    try:
        value = unquote(raw, errors="strict")
    except (UnicodeError, ValueError):
        raise ProductionExecutionError("admin_database_url_invalid") from None
    if not value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ProductionExecutionError("admin_database_url_invalid")
    return value


def admin_connection(url: str):
    """Validate the Railway public admin URL and rebuild a pinned libpq conninfo.

    Railway's recovered PostgreSQL endpoint is an authenticated project-derived
    TCP proxy and the repository's existing recovery integrity audit uses
    sslmode=require. The URL host is separately restricted to Railway's proxy
    namespace and URL-supplied libpq options are discarded.
    """
    try:
        if not isinstance(url, str) or not url or len(url) > 8192:
            raise ValueError("url")
        parts = urlsplit(url)
        if parts.scheme not in ("postgres", "postgresql") or parts.fragment:
            raise ValueError("scheme")
        host = parts.hostname
        if not host or not _HOST_RE.fullmatch(host):
            raise ValueError("host")
        if any(label.startswith("-") or label.endswith("-") or len(label) > 63
               for label in host.split(".")):
            raise ValueError("host")
        port = parts.port
        if port is None or not 1 <= port <= 65535:
            raise ValueError("port")
        for raw in (parts.username, parts.password, parts.path, parts.query):
            if raw is not None and re.search(r"%(?![0-9a-fA-F]{2})", raw):
                raise ValueError("percent")
        user = _decode(parts.username)
        password = _decode(parts.password)
        if user == guard.ROLE_NAME or not parts.path.startswith("/"):
            raise ValueError("role")
        database = _decode(parts.path[1:])
        if "/" in database or not _DB_RE.fullmatch(database):
            raise ValueError("database")
    except (TypeError, ValueError):
        raise ProductionExecutionError("admin_database_url_invalid") from None

    from psycopg.conninfo import make_conninfo
    conninfo = make_conninfo(
        "", host=host, port=port, dbname=database, user=user, password=password,
        sslmode="require", gssencmode="disable", connect_timeout=10,
        application_name="odds_evidence_role_provisioner",
        options="-c search_path=pg_catalog -c statement_timeout=15000 "
                "-c lock_timeout=2000 -c idle_in_transaction_session_timeout=30000",
    )
    return conninfo, host, port, database


def audit_connection(*, host: str, port: int, database: str, password: str) -> str:
    from psycopg.conninfo import make_conninfo
    return make_conninfo(
        "", host=host, port=port, dbname=database, user=guard.ROLE_NAME,
        password=password, sslmode="require", gssencmode="disable",
        connect_timeout=10, application_name="odds_evidence_20260908",
        options="-c search_path=pg_catalog -c default_transaction_read_only=on "
                "-c statement_timeout=15000 -c lock_timeout=2000 "
                "-c idle_in_transaction_session_timeout=30000",
    )


def _role_exists(admin) -> bool:
    row = admin.execute(
        "SELECT 1 AS present FROM pg_catalog.pg_roles WHERE rolname=%s",
        (guard.ROLE_NAME,),
    ).fetchone()
    return bool(row)


def _drop_role(admin) -> bool:
    """Remove only the dedicated temporary audit role; never alter PUBLIC."""
    from psycopg import sql
    if not _role_exists(admin):
        return True
    role = sql.Identifier(guard.ROLE_NAME)
    with admin.transaction():
        admin.execute(sql.SQL("DROP OWNED BY {}").format(role))
        admin.execute(sql.SQL("DROP ROLE {}").format(role))
    return not _role_exists(admin)


def _write_execution(*, status: str, stage: str, cleanup: str,
                     server_version=None, snapshots=None) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "audit_date": audit.TARGET_DATE,
        "stage": stage,
        "role_cleanup": cleanup,
        "preflight_server_version": server_version,
        "bao_snapshots_available": snapshots,
        "historical_roi_approval": "BLOCKED",
        "production_promotion": "BLOCKED",
    }
    EXECUTION_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(env=None) -> int:
    env = os.environ if env is None else env
    stage = "authorization"
    created = False
    cleanup = "NOT_NEEDED"
    report = None
    admin = None
    try:
        authorize(env)
        stage = "admin_connection_validation"
        admin_conninfo, host, port, database = admin_connection(env["ADMIN_DATABASE_URL"])

        stage = "admin_connection"
        import psycopg
        from psycopg.rows import dict_row
        admin = psycopg.connect(
            admin_conninfo, autocommit=True, row_factory=dict_row
        )

        stage = "existing_role_check"
        if _role_exists(admin):
            raise ProductionExecutionError("dedicated_audit_role_already_exists")

        stage = "role_provisioning"
        password = secrets.token_urlsafe(32)
        with admin.transaction():
            with admin.cursor() as cur:
                provisioning.apply(
                    cur,
                    database=database,
                    password=password,
                    confirmation=provisioning.CONFIRMATION,
                )
        created = True

        stage = "dedicated_role_audit"
        conninfo = audit_connection(
            host=host, port=port, database=database, password=password
        )
        raw = audit.read_database(conninfo, expected_database=database)

        stage = "report_validation"
        report = runner.safe_report(raw)

        stage = "role_cleanup"
        cleanup = "COMPLETE" if _drop_role(admin) else "FAILED"
        created = False
        if cleanup != "COMPLETE":
            raise ProductionExecutionError("dedicated_audit_role_cleanup_failed")

        stage = "report_write"
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _write_execution(
            status="PRODUCTION_READ_ONLY_AUDIT_COMPLETED",
            stage="complete",
            cleanup=cleanup,
            server_version=report["preflight_server_version"],
            snapshots=report["schema"]["bao_snapshots_available"],
        )
    except Exception:
        failure_stage = stage
        if admin is not None and created:
            stage = "failure_cleanup"
            try:
                cleanup = "COMPLETE" if _drop_role(admin) else "FAILED"
            except Exception:
                cleanup = "FAILED"
        try:
            _write_execution(
                status="BLOCKED",
                stage=failure_stage,
                cleanup=cleanup,
            )
        except Exception:
            pass
        print("PRODUCTION_AUDIT_FAILED=" + failure_stage + ";ROLE_CLEANUP=" + cleanup,
              file=sys.stderr)
        return 1
    finally:
        if admin is not None:
            try:
                admin.close()
            except Exception:
                pass

    print("PRODUCTION_AUDIT_COMPLETED=2026-09-08;RACES=19;"
          "ROLE_CLEANUP=COMPLETE;ROOT_CAUSE=UNDETERMINED;ROI=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
