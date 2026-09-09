#!/usr/bin/env python3
"""Approval-gated one-shot read-only audit of realtime odds snapshots for 2026-09-08.

The executor creates a fresh temporary LOGIN role with column-level SELECT only
on the fixed evidence tables, reads aggregate metadata for the fixed 19 races,
then drops the role. It never changes application rows, Railway configuration,
Cron, PUBLIC privileges, model settings, or notification state.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import audit_odds_evidence_20260908_pg as audit
import odds_evidence_privilege_guard as base_guard
import odds_evidence_production_executor as base_executor

REPO = "kenshoushouri-cloud/boat-ai-v2"
BRANCH = "research/odds-evidence-20260908"
OWNER = "kenshoushouri-cloud"
ROLE_NAME = "boat_odds_realtime_audit_ro"
CONFIRMATION = "REALTIME-SNAPSHOT-AUDIT-2026-09-08-ONCE"
COMMIT_MESSAGE = "REALTIME-SNAPSHOT-AUDIT-2026-09-08-APPROVED-ONCE"
RESULT_DIR = Path(".audit-results")
RESULT_PATH = RESULT_DIR / "realtime-snapshot-audit-20260908.json"
ALLOWED_COLUMNS = {
    "v2_races": ("race_id", "deadline_at"),
    "v2_realtime_odds_snapshots": (
        "race_id", "snapshot_label", "snapshot_at", "ticket",
    ),
}
MAX_GROUP_ROWS = 500


class RealtimeSnapshotAuditError(RuntimeError):
    """Fixed, non-sensitive failure code."""


def authorize(env) -> None:
    expected = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_REF": "refs/heads/" + BRANCH,
        "GITHUB_ACTOR": OWNER,
        "GITHUB_RUN_ATTEMPT": "1",
        "REALTIME_SNAPSHOT_AUDIT_CONFIRMATION": CONFIRMATION,
        "REALTIME_SNAPSHOT_AUDIT_COMMIT_MESSAGE": COMMIT_MESSAGE,
    }
    if any(env.get(key) != value for key, value in expected.items()):
        raise RealtimeSnapshotAuditError("execution_context_rejected")
    if not re.fullmatch(r"[0-9a-f]{40}", env.get("GITHUB_SHA", "")):
        raise RealtimeSnapshotAuditError("execution_context_rejected")
    if not env.get("ADMIN_DATABASE_URL"):
        raise RealtimeSnapshotAuditError("admin_database_credentials_missing")


def _role_exists(admin) -> bool:
    return bool(admin.execute(
        "SELECT 1 AS present FROM pg_catalog.pg_roles WHERE rolname=%s",
        (ROLE_NAME,),
    ).fetchone())


def _drop_role(admin) -> bool:
    from psycopg import sql
    if not _role_exists(admin):
        return True
    role = sql.Identifier(ROLE_NAME)
    with admin.transaction():
        admin.execute(sql.SQL("DROP OWNED BY {}").format(role))
        admin.execute(sql.SQL("DROP ROLE {}").format(role))
    return not _role_exists(admin)


def _assert_target_schema(admin) -> None:
    for table, columns in ALLOWED_COLUMNS.items():
        row = admin.execute(
            """SELECT c.oid AS relation_oid, c.relrowsecurity, c.relforcerowsecurity,
                      array_agg(a.attname ORDER BY a.attname)
                        FILTER (WHERE a.attnum > 0 AND NOT a.attisdropped) AS columns
               FROM pg_catalog.pg_class c
               JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
               LEFT JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
               WHERE n.nspname='public' AND c.relname=%s AND c.relkind IN ('r','p')
               GROUP BY c.oid,c.relrowsecurity,c.relforcerowsecurity""",
            (table,),
        ).fetchone()
        if (not row or row["relrowsecurity"] or row["relforcerowsecurity"]
                or not set(columns) <= set(row["columns"] or ())):
            raise RealtimeSnapshotAuditError("target_schema_rejected")


def _provision(admin, *, database: str, password: str) -> None:
    from psycopg import sql
    if _role_exists(admin):
        raise RealtimeSnapshotAuditError("dedicated_role_already_exists")
    _assert_target_schema(admin)
    role = sql.Identifier(ROLE_NAME)
    db = sql.Identifier(database)
    with admin.transaction():
        admin.execute(sql.SQL("""CREATE ROLE {} WITH LOGIN NOINHERIT NOSUPERUSER
            NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 1
            PASSWORD {}""").format(role, sql.Literal(password)))
        admin.execute(sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}").format(db, role))
        admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(db, role))
        admin.execute(sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA public FROM {}").format(role))
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        for table, columns in ALLOWED_COLUMNS.items():
            admin.execute(sql.SQL("REVOKE ALL PRIVILEGES ON TABLE public.{} FROM {}").format(
                sql.Identifier(table), role))
            admin.execute(sql.SQL("GRANT SELECT ({}) ON TABLE public.{} TO {}").format(
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                sql.Identifier(table), role))
        for name, value in {
            "default_transaction_read_only": "on",
            "search_path": "pg_catalog",
            "statement_timeout": "15s",
            "lock_timeout": "2s",
            "idle_in_transaction_session_timeout": "30s",
        }.items():
            admin.execute(sql.SQL("ALTER ROLE {} SET {} TO {}").format(
                role, sql.Identifier(name), sql.Literal(value)))


def _verify_admin_scope(admin, *, database: str) -> None:
    row = admin.execute(
        """SELECT r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,
                  r.rolbypassrls,r.rolinherit,r.rolcanlogin,
                  EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m
                          WHERE m.member=r.oid) AS membership,
                  pg_catalog.has_schema_privilege(r.oid,'public','CREATE') AS schema_create,
                  pg_catalog.has_database_privilege(r.oid,%s,'CREATE') AS database_create
           FROM pg_catalog.pg_roles r WHERE r.rolname=%s""",
        (database, ROLE_NAME),
    ).fetchone()
    if (not row or any(row[key] is not False for key in (
            "rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication",
            "rolbypassrls", "rolinherit", "membership", "schema_create",
            "database_create")) or row["rolcanlogin"] is not True):
        raise RealtimeSnapshotAuditError("dedicated_role_scope_rejected")

    allowed = {(table, column) for table, columns in ALLOWED_COLUMNS.items()
               for column in columns}
    rows = admin.execute(
        """SELECT c.relname AS table_name,a.attname AS column_name
           FROM pg_catalog.pg_attribute a
           JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
           JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           JOIN pg_catalog.pg_roles r ON r.rolname=%s
           WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
             AND a.attnum>0 AND NOT a.attisdropped
             AND pg_catalog.has_column_privilege(r.oid,c.oid,a.attnum,'SELECT')""",
        (ROLE_NAME,),
    ).fetchall()
    observed = {(row["table_name"], row["column_name"]) for row in rows}
    if observed != allowed:
        raise RealtimeSnapshotAuditError("dedicated_role_scope_rejected")

    write = admin.execute(
        """SELECT EXISTS (
             SELECT 1 FROM pg_catalog.pg_class c
             JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
             JOIN pg_catalog.pg_roles r ON r.rolname=%s
             WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
               AND pg_catalog.has_table_privilege(
                   r.oid,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
           ) AS table_write""",
        (ROLE_NAME,),
    ).fetchone()
    if not write or write["table_write"] is not False:
        raise RealtimeSnapshotAuditError("dedicated_role_scope_rejected")


def _reader_conninfo(*, host: str, port: int, database: str, password: str) -> str:
    from psycopg.conninfo import make_conninfo
    return make_conninfo(
        "", host=host, port=port, dbname=database, user=ROLE_NAME, password=password,
        sslmode="require", gssencmode="disable", connect_timeout=10,
        application_name="odds_evidence_realtime_snapshot_20260908",
        options="-c search_path=pg_catalog -c default_transaction_read_only=on "
                "-c statement_timeout=15000 -c lock_timeout=2000 "
                "-c idle_in_transaction_session_timeout=30000",
    )


def _safe_dt(value):
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RealtimeSnapshotAuditError("unexpected_snapshot_result")
    return value.astimezone(timezone.utc).isoformat()


def _read(reader_conninfo: str, *, database: str) -> dict:
    import psycopg
    from psycopg.rows import dict_row
    ids = list(audit.TARGET_RACES)
    with psycopg.connect(reader_conninfo, row_factory=dict_row, autocommit=False,
                         connect_timeout=10) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                cur.execute("SET LOCAL statement_timeout='15000ms'")
                identity = cur.execute(
                    """SELECT current_setting('transaction_read_only') AS read_only,
                              session_user AS session_role,current_user AS active_role,
                              current_database() AS database_name"""
                ).fetchone()
                if (not identity or identity["read_only"] != "on"
                        or identity["session_role"] != ROLE_NAME
                        or identity["active_role"] != ROLE_NAME
                        or identity["database_name"] != database):
                    raise RealtimeSnapshotAuditError("reader_identity_rejected")
                cur.execute(
                    """SELECT race_id,deadline_at FROM public.v2_races
                       WHERE race_id=ANY(%s) ORDER BY race_id""",
                    (ids,),
                )
                races = cur.fetchmany(20)
                if len(races) > 19:
                    raise RealtimeSnapshotAuditError("unexpected_snapshot_result")
                cur.execute(
                    """SELECT race_id,snapshot_label,
                              count(*)::int AS row_count,
                              count(DISTINCT ticket)::int AS distinct_tickets,
                              count(*) FILTER (
                                WHERE ticket !~ '^[1-6]-[1-6]-[1-6]$'
                                   OR split_part(ticket,'-',1)=split_part(ticket,'-',2)
                                   OR split_part(ticket,'-',1)=split_part(ticket,'-',3)
                                   OR split_part(ticket,'-',2)=split_part(ticket,'-',3)
                              )::int AS invalid_tickets,
                              min(snapshot_at) AS snapshot_at_min,
                              max(snapshot_at) AS snapshot_at_max
                       FROM public.v2_realtime_odds_snapshots
                       WHERE race_id=ANY(%s)
                       GROUP BY race_id,snapshot_label
                       ORDER BY race_id,snapshot_label""",
                    (ids,),
                )
                groups = cur.fetchmany(MAX_GROUP_ROWS + 1)
                if len(groups) > MAX_GROUP_ROWS:
                    raise RealtimeSnapshotAuditError("snapshot_group_limit_exceeded")
        finally:
            conn.rollback()

    deadlines = {str(row["race_id"]): row["deadline_at"] for row in races}
    by_race = defaultdict(list)
    for row in groups:
        rid = str(row["race_id"])
        if rid not in audit.TARGET_RACES:
            raise RealtimeSnapshotAuditError("unexpected_snapshot_result")
        by_race[rid].append(dict(row))

    output = []
    all_predeadline_complete = True
    races_with_any_complete = 0
    races_with_predeadline_complete = 0
    for rid in audit.TARGET_RACES:
        deadline = deadlines.get(rid)
        if not isinstance(deadline, datetime) or deadline.tzinfo is None:
            raise RealtimeSnapshotAuditError("unexpected_snapshot_result")
        expected_deadline = audit.reference_deadline(rid)
        deadline_match = deadline.astimezone(audit.JST) == expected_deadline
        summaries = []
        any_complete = False
        predeadline_complete = False
        for row in by_race[rid]:
            complete = (row["row_count"] == 120 and row["distinct_tickets"] == 120
                        and row["invalid_tickets"] == 0)
            maximum = row["snapshot_at_max"]
            minimum = row["snapshot_at_min"]
            before = bool(
                complete and isinstance(maximum, datetime) and maximum.tzinfo is not None
                and maximum.astimezone(audit.JST) <= expected_deadline
            )
            any_complete = any_complete or complete
            predeadline_complete = predeadline_complete or before
            label = row["snapshot_label"]
            if not isinstance(label, str) or len(label) > 64 or any(ord(ch) < 32 for ch in label):
                raise RealtimeSnapshotAuditError("unexpected_snapshot_result")
            summaries.append({
                "snapshot_label": label,
                "row_count": int(row["row_count"]),
                "distinct_tickets": int(row["distinct_tickets"]),
                "invalid_tickets": int(row["invalid_tickets"]),
                "complete_120": complete,
                "all_rows_at_or_before_reference_deadline": before,
                "snapshot_at_min": _safe_dt(minimum),
                "snapshot_at_max": _safe_dt(maximum),
            })
        races_with_any_complete += int(any_complete)
        races_with_predeadline_complete += int(predeadline_complete)
        all_predeadline_complete = all_predeadline_complete and predeadline_complete
        output.append({
            "race_id": rid,
            "deadline_matches_reference": deadline_match,
            "snapshot_group_count": len(summaries),
            "any_complete_120_group": any_complete,
            "predeadline_complete_120_group": predeadline_complete,
            "groups": summaries,
        })

    interpretation = (
        "SEPARATE_REALTIME_SNAPSHOT_PATH_CONFIRMED_ALL_19_PREDEADLINE_COMPLETE"
        if all_predeadline_complete else
        "SEPARATE_REALTIME_SNAPSHOT_PATH_PARTIALLY_SUPPORTED"
        if races_with_any_complete else
        "NO_COMPLETE_REALTIME_SNAPSHOT_GROUP_FOUND"
    )
    return {
        "audit_date": audit.TARGET_DATE,
        "execution_status": "READ_ONLY_QUERY_COMPLETED",
        "scope": "fixed_19_races_realtime_odds_snapshots",
        "races_with_any_complete_120_group": races_with_any_complete,
        "races_with_predeadline_complete_120_group": races_with_predeadline_complete,
        "interpretation": interpretation,
        "races": output,
        "historical_authentication": "NOT_ESTABLISHED_BY_STORED_METADATA",
        "historical_roi_approval": "BLOCKED",
        "production_promotion": "BLOCKED",
    }


def _write_result(payload: dict) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(env=None) -> int:
    env = os.environ if env is None else env
    stage = "authorization"
    admin = None
    created = False
    cleanup = "NOT_NEEDED"
    try:
        authorize(env)
        stage = "admin_connection_validation"
        admin_conninfo, host, port, database = base_executor.admin_connection(
            env["ADMIN_DATABASE_URL"]
        )
        stage = "admin_connection"
        import psycopg
        from psycopg.rows import dict_row
        admin = psycopg.connect(admin_conninfo, autocommit=True, row_factory=dict_row)

        stage = "target_schema"
        _assert_target_schema(admin)
        stage = "role_provisioning"
        password = secrets.token_urlsafe(32)
        _provision(admin, database=database, password=password)
        created = True

        stage = "role_scope_preflight"
        _verify_admin_scope(admin, database=database)

        stage = "snapshot_read"
        result = _read(
            _reader_conninfo(host=host, port=port, database=database, password=password),
            database=database,
        )

        stage = "role_cleanup"
        cleanup = "COMPLETE" if _drop_role(admin) else "FAILED"
        created = False
        if cleanup != "COMPLETE":
            raise RealtimeSnapshotAuditError("dedicated_role_cleanup_failed")

        result["role_cleanup"] = cleanup
        result["root_cause"] = (
            "BASE_TABLE_SEMANTICS_OR_STORAGE_PATH_MISMATCH_SUPPORTED"
            if result["interpretation"] ==
            "SEPARATE_REALTIME_SNAPSHOT_PATH_CONFIRMED_ALL_19_PREDEADLINE_COMPLETE"
            else "UNDETERMINED"
        )
        stage = "result_write"
        _write_result(result)
    except Exception:
        failure_stage = stage
        if admin is not None and created:
            try:
                cleanup = "COMPLETE" if _drop_role(admin) else "FAILED"
            except Exception:
                cleanup = "FAILED"
        try:
            _write_result({
                "audit_date": audit.TARGET_DATE,
                "execution_status": "BLOCKED",
                "stage": failure_stage,
                "role_cleanup": cleanup,
                "root_cause": "UNDETERMINED",
                "historical_roi_approval": "BLOCKED",
                "production_promotion": "BLOCKED",
            })
        except Exception:
            pass
        print("REALTIME_SNAPSHOT_AUDIT_FAILED=" + failure_stage +
              ";ROLE_CLEANUP=" + cleanup, file=sys.stderr)
        return 1
    finally:
        if admin is not None:
            try:
                admin.close()
            except Exception:
                pass

    print("REALTIME_SNAPSHOT_AUDIT_COMPLETED=2026-09-08;RACES=19;"
          "ROLE_CLEANUP=COMPLETE;ROI=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
