#!/usr/bin/env python3
"""One-shot read-only comparison of base odds tickets and realtime snapshot tickets."""
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
import odds_evidence_realtime_snapshot_audit as shared

REPO = shared.REPO
BRANCH = shared.BRANCH
OWNER = shared.OWNER
ROLE_NAME = "boat_odds_realtime_compare_ro"
CONFIRMATION = "REALTIME-SET-COMPARE-2026-09-08-ONCE"
COMMIT_MESSAGE = "REALTIME-SET-COMPARE-2026-09-08-APPROVED-ONCE"
RESULT_DIR = Path(".audit-results")
RESULT_PATH = RESULT_DIR / "realtime-set-compare-20260908.json"
ALLOWED_COLUMNS = {
    "v2_races": ("race_id", "deadline_at"),
    "v2_odds_trifecta": ("race_id", "ticket"),
    "v2_realtime_odds_snapshots": (
        "race_id", "snapshot_label", "snapshot_at", "ticket", "source",
    ),
}
BASE_ROW_CAP = 2500
SNAPSHOT_ROW_CAP = 5000


class RealtimeSetCompareError(RuntimeError):
    """Fixed, non-sensitive error code."""


def authorize(env) -> None:
    expected = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_REF": "refs/heads/" + BRANCH,
        "GITHUB_ACTOR": OWNER,
        "GITHUB_RUN_ATTEMPT": "1",
        "REALTIME_SET_COMPARE_CONFIRMATION": CONFIRMATION,
        "REALTIME_SET_COMPARE_COMMIT_MESSAGE": COMMIT_MESSAGE,
    }
    if any(env.get(key) != value for key, value in expected.items()):
        raise RealtimeSetCompareError("execution_context_rejected")
    if not re.fullmatch(r"[0-9a-f]{40}", env.get("GITHUB_SHA", "")):
        raise RealtimeSetCompareError("execution_context_rejected")
    if not env.get("ADMIN_DATABASE_URL"):
        raise RealtimeSetCompareError("admin_database_credentials_missing")


def _configure_shared_scope() -> None:
    shared.ROLE_NAME = ROLE_NAME
    shared.ALLOWED_COLUMNS = ALLOWED_COLUMNS


def _safe_text(value, *, max_length=64) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise RealtimeSetCompareError("unexpected_compare_result")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise RealtimeSetCompareError("unexpected_compare_result")
    return value


def _safe_dt(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RealtimeSetCompareError("unexpected_compare_result")
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
                    raise RealtimeSetCompareError("reader_identity_rejected")

                cur.execute(
                    """SELECT race_id,deadline_at FROM public.v2_races
                       WHERE race_id=ANY(%s) ORDER BY race_id""", (ids,))
                races = cur.fetchmany(20)
                if len(races) != 19:
                    raise RealtimeSetCompareError("unexpected_compare_result")

                cur.execute(
                    """SELECT race_id,ticket FROM public.v2_odds_trifecta
                       WHERE race_id=ANY(%s) ORDER BY race_id,ticket""", (ids,))
                base_rows = cur.fetchmany(BASE_ROW_CAP + 1)
                if len(base_rows) > BASE_ROW_CAP:
                    raise RealtimeSetCompareError("base_row_limit_exceeded")

                cur.execute(
                    """SELECT race_id,snapshot_label,snapshot_at,ticket,source
                       FROM public.v2_realtime_odds_snapshots
                       WHERE race_id=ANY(%s)
                       ORDER BY race_id,snapshot_label,ticket""", (ids,))
                snapshot_rows = cur.fetchmany(SNAPSHOT_ROW_CAP + 1)
                if len(snapshot_rows) > SNAPSHOT_ROW_CAP:
                    raise RealtimeSetCompareError("snapshot_row_limit_exceeded")
        finally:
            conn.rollback()

    deadlines = {str(row["race_id"]): row["deadline_at"] for row in races}
    base_by = defaultdict(list)
    for row in base_rows:
        rid = str(row["race_id"])
        if rid not in audit.TARGET_RACES:
            raise RealtimeSetCompareError("unexpected_compare_result")
        base_by[rid].append(str(row["ticket"]))

    snap_by = defaultdict(list)
    for row in snapshot_rows:
        rid = str(row["race_id"])
        if rid not in audit.TARGET_RACES:
            raise RealtimeSetCompareError("unexpected_compare_result")
        label = _safe_text(row["snapshot_label"])
        source = _safe_text(row["source"])
        snap_by[(rid, label)].append({
            "ticket": str(row["ticket"]),
            "snapshot_at": row["snapshot_at"],
            "source": source,
        })

    race_reports = []
    final_equal = learning_equal = all_groups_equal = 0
    fallback_groups = official_groups = 0

    for rid in audit.TARGET_RACES:
        deadline = deadlines.get(rid)
        if not isinstance(deadline, datetime) or deadline.tzinfo is None:
            raise RealtimeSetCompareError("unexpected_compare_result")
        reference = audit.reference_deadline(rid)
        base_list = base_by[rid]
        base_set = set(base_list)
        base_invalid = sorted(ticket for ticket in base_set if ticket not in audit.ALL_TICKETS)
        if base_invalid:
            raise RealtimeSetCompareError("unexpected_compare_result")

        groups = []
        labels = sorted(label for race_id, label in snap_by if race_id == rid)
        for label in labels:
            rows = snap_by[(rid, label)]
            tickets = [row["ticket"] for row in rows]
            ticket_set = set(tickets)
            invalid = sum(ticket not in audit.ALL_TICKETS for ticket in tickets)
            sources = sorted({row["source"] for row in rows})
            times = [row["snapshot_at"] for row in rows]
            if any(not isinstance(value, datetime) or value.tzinfo is None for value in times):
                raise RealtimeSetCompareError("unexpected_compare_result")
            minimum, maximum = min(times), max(times)
            equal = ticket_set == base_set
            fallback_groups += int("v2_odds_trifecta_fallback" in sources)
            official_groups += int("official_odds3t" in sources)
            groups.append({
                "snapshot_label": label,
                "sources": sources,
                "row_count": len(rows),
                "distinct_tickets": len(ticket_set),
                "invalid_tickets": invalid,
                "duplicates": len(rows) - len(ticket_set),
                "base_distinct_tickets": len(base_set),
                "ticket_set_equal_base": equal,
                "intersection_count": len(ticket_set & base_set),
                "base_only_count": len(base_set - ticket_set),
                "realtime_only_count": len(ticket_set - base_set),
                "snapshot_at_min": _safe_dt(minimum),
                "snapshot_at_max": _safe_dt(maximum),
                "all_rows_at_or_before_reference_deadline":
                    maximum.astimezone(audit.JST) <= reference,
            })

        by_label = {group["snapshot_label"]: group for group in groups}
        f_equal = bool(by_label.get("final_ab", {}).get("ticket_set_equal_base"))
        l_equal = bool(by_label.get("learning_all", {}).get("ticket_set_equal_base"))
        a_equal = bool(groups) and all(group["ticket_set_equal_base"] for group in groups)
        final_equal += int(f_equal)
        learning_equal += int(l_equal)
        all_groups_equal += int(a_equal)
        race_reports.append({
            "race_id": rid,
            "deadline_matches_reference": deadline.astimezone(audit.JST) == reference,
            "base_distinct_tickets": len(base_set),
            "snapshot_group_count": len(groups),
            "final_ab_equal_base": f_equal,
            "learning_all_equal_base": l_equal,
            "all_snapshot_groups_equal_base": a_equal,
            "groups": groups,
        })

    if final_equal == learning_equal == all_groups_equal == 19:
        interpretation = "REALTIME_FINAL_AND_LEARNING_TICKET_SETS_EXACTLY_MATCH_BASE_ALL_19"
    elif final_equal or learning_equal or all_groups_equal:
        interpretation = "REALTIME_TICKET_SET_MATCH_WITH_BASE_PARTIAL"
    else:
        interpretation = "REALTIME_TICKET_SETS_DIFFER_FROM_BASE"

    return {
        "audit_date": audit.TARGET_DATE,
        "execution_status": "READ_ONLY_QUERY_COMPLETED",
        "scope": "fixed_19_races_base_vs_realtime_ticket_sets",
        "races_with_final_ab_equal_base": final_equal,
        "races_with_learning_all_equal_base": learning_equal,
        "races_with_all_snapshot_groups_equal_base": all_groups_equal,
        "groups_using_base_fallback": fallback_groups,
        "groups_using_official_odds3t": official_groups,
        "interpretation": interpretation,
        "races": race_reports,
        "diagnosis": (
            "COMMON_UPSTREAM_PARTIAL_TICKET_SET_PROPAGATION_SUPPORTED"
            if all_groups_equal == 19 else "UNDETERMINED"
        ),
        "root_cause": "UNDETERMINED",
        "historical_authentication": "NOT_ESTABLISHED_BY_STORED_METADATA",
        "historical_roi_approval": "BLOCKED",
        "production_promotion": "BLOCKED",
    }


def _write(payload: dict) -> None:
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
        _configure_shared_scope()
        stage = "admin_connection_validation"
        admin_conninfo, host, port, database = shared.base_executor.admin_connection(
            env["ADMIN_DATABASE_URL"])
        stage = "admin_connection"
        import psycopg
        from psycopg.rows import dict_row
        admin = psycopg.connect(admin_conninfo, autocommit=True, row_factory=dict_row)

        stage = "target_schema"
        shared._assert_target_schema(admin)
        stage = "role_provisioning"
        password = secrets.token_urlsafe(32)
        shared._provision(admin, database=database, password=password)
        created = True

        stage = "role_scope_preflight"
        shared._verify_admin_scope(admin, database=database)

        stage = "set_comparison"
        result = _read(
            shared._reader_conninfo(
                host=host, port=port, database=database, password=password),
            database=database)

        stage = "role_cleanup"
        cleanup = "COMPLETE" if shared._drop_role(admin) else "FAILED"
        created = False
        if cleanup != "COMPLETE":
            raise RealtimeSetCompareError("dedicated_role_cleanup_failed")
        result["role_cleanup"] = cleanup

        stage = "result_write"
        _write(result)
    except Exception:
        failure_stage = stage
        if admin is not None and created:
            try:
                cleanup = "COMPLETE" if shared._drop_role(admin) else "FAILED"
            except Exception:
                cleanup = "FAILED"
        try:
            _write({
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
        print("REALTIME_SET_COMPARE_FAILED=" + failure_stage +
              ";ROLE_CLEANUP=" + cleanup, file=sys.stderr)
        return 1
    finally:
        if admin is not None:
            try:
                admin.close()
            except Exception:
                pass

    print("REALTIME_SET_COMPARE_COMPLETED=2026-09-08;RACES=19;"
          "ROLE_CLEANUP=COMPLETE;ROI=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
