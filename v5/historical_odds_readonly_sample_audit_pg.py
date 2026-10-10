# -*- coding: utf-8 -*-
"""V5: BOUNDED readonly samples of already stored historical trifecta odds.

OFF by default, ≤3 exact race IDs, requires valid race_id-leading indexes.
This audits fields, not official provenance or first-observed at decision time.
Never fetch odds, run DDL, write DB, deploy, select live bets, or approve BUY.

Example (only in an independently authorised read-only DB environment):
  V5_READONLY_ODDS_AUDIT=YES_READ_ONLY \
  V5_AUDIT_RACE_IDS=20261005_03_01 \
  DATABASE_URL=... python -m v5.historical_odds_readonly_sample_audit_pg
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

RACE = re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")
REQUIRED = {
    "v2_odds_trifecta": {"race_id", "ticket", "odds", "is_final", "fetched_at"},
    "v2_results": {"race_id", "result_status", "race_status",
                   "trifecta_ticket", "trifecta_payout_yen"},
    "v2_result_entries": {"race_id", "lane", "is_flying", "is_late"},
}
TABLES = tuple(REQUIRED)
INDEX_FIRST_KEY = re.compile(r'\(\s*"?race_id"?\s*[,)]')


def checked_race_ids(raw: object) -> tuple[str, ...]:
    if type(raw) is not str:
        raise ValueError("RACE_IDS_REQUIRED")
    ids = tuple(x.strip() for x in raw.split(","))
    if not 1 <= len(ids) <= 3 or len(set(ids)) != len(ids):
        raise ValueError("RACE_IDS_COUNT_OR_DUPLICATE_INVALID")
    for rid in ids:
        if RACE.fullmatch(rid) is None:
            raise ValueError("RACE_ID_SYNTAX_INVALID")
        try:
            day = datetime.strptime(rid[:8], "%Y%m%d")
        except ValueError as exc:
            raise ValueError("RACE_ID_DATE_INVALID") from exc
        if day < datetime(2025, 7, 1):
            raise ValueError("BEFORE_V5_HISTORY_RANGE")
    return ids


def summarize_odds(n: int, valid: int, distinct_tickets: int,
                   final: int, nonfinal: int, missing_final: int) -> str:
    """A stored is_final flag is a claim, not independent source proof."""
    if n == 0:
        return "NO_ROWS_FOR_SAMPLED_RACE"
    if n != 120 or valid != 120 or distinct_tickets != 120:
        return "NOT_120_COMPLETE_OR_INVALID_TICKETS"
    if final == 120 and nonfinal == 0 and missing_final == 0:
        return "120_RECORDED_FINAL_FLAG_CANDIDATE_NOT_SOURCE_PROOF"
    if final == 0 and nonfinal == 120:
        return "120_RECORDED_NONFINAL_FLAG_NOT_CLOSING_PROOF"
    return "FINAL_FLAG_MIXED_OR_NULL"


def run_sample_audit() -> dict:
    """No connection attempted without opt-in, validated IDs and psycopg."""
    if os.environ.get("V5_READONLY_ODDS_AUDIT") != "YES_READ_ONLY":
        return {"status": "DISABLED_BY_DEFAULT", "database_read_executed": False}
    ids = checked_race_ids(os.environ.get("V5_AUDIT_RACE_IDS"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL_REQUIRED")
    import psycopg
    from psycopg.rows import dict_row
    results: dict = {"status": "SAMPLED_ONLY_NOT_ASOF_CERTIFIED",
                     "database_write_executed": False,
                     "source_authenticated": False,
                     "before_deadline_odds_verified": False,
                     "v5_roi_verified": False,
                     "forward_eligible": False, "buy_eligible": False,
                     "race_ids": list(ids)}
    # Autocommit only for explicit BEGIN READ ONLY + guaranteed ROLLBACK.
    # No variable secrets or raw racer/HTML contents ever printed.
    with psycopg.connect(url, connect_timeout=4, autocommit=True,
                         row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            try:
                cur.execute("SET LOCAL statement_timeout='2000ms'")
                cur.execute("SET LOCAL lock_timeout='250ms'")
                cur.execute("""
                    SELECT table_name, column_name
                      FROM information_schema.columns
                     WHERE table_schema='public'
                       AND table_name = ANY(%s)
                """, (list(TABLES),))
                columns = {table: set() for table in TABLES}
                for r in cur.fetchall():
                    columns[r["table_name"]].add(r["column_name"])
                for table, required in REQUIRED.items():
                    if not required.issubset(columns[table]):
                        return {**results, "status": "REQUIRED_COLUMNS_UNAVAILABLE",
                                "table": table,
                                "missing_fields": sorted(required - columns[table])}
                cur.execute("""
                    SELECT tablename, indexdef
                      FROM pg_indexes
                     WHERE schemaname='public' AND tablename = ANY(%s)
                """, (list(TABLES),))
                indices: dict[str, list[str]] = {table: [] for table in TABLES}
                for r in cur.fetchall():
                    indices[r["tablename"]].append(r["indexdef"])
                for table in TABLES:
                    if not any(INDEX_FIRST_KEY.search(defn) for defn in indices[table]):
                        return {**results, "status": "RACE_ID_LEADING_INDEX_UNVERIFIED",
                                "table": table}
                # Every data query is indexed on race_id with at most 3 keys.
                cur.execute("""
                    SELECT race_id, count(*)::int AS n,
                           count(DISTINCT ticket)::int AS distinct_tickets,
                           count(*) FILTER
                             (WHERE ticket ~ '^[1-6]-[1-6]-[1-6]
                           count(*) FILTER (WHERE is_final IS TRUE)::int AS final,
                           count(*) FILTER (WHERE is_final IS FALSE)::int AS nonfinal,
                           count(*) FILTER (WHERE is_final IS NULL)::int AS missing_final,
                           min(fetched_at) AS oldest_stored_fetch,
                           max(fetched_at) AS newest_stored_fetch
                      FROM v2_odds_trifecta
                     WHERE race_id = ANY(%s)
                     GROUP BY race_id
                """, (list(ids),))
                odds = {r["race_id"]: dict(r) for r in cur.fetchall()}
                cur.execute("""
                    SELECT race_id, result_status, race_status,
                           trifecta_ticket, trifecta_payout_yen
                      FROM v2_results
                     WHERE race_id = ANY(%s)
                """, (list(ids),))
                settlements = {r["race_id"]: dict(r) for r in cur.fetchall()}
                cur.execute("""
                    SELECT race_id, count(*)::int AS rows,
                           count(*) FILTER (WHERE is_flying IS TRUE)::int AS flying,
                           count(*) FILTER (WHERE is_late IS TRUE)::int AS late
                      FROM v2_result_entries
                     WHERE race_id = ANY(%s)
                     GROUP BY race_id
                """, (list(ids),))
                incidents = {r["race_id"]: dict(r) for r in cur.fetchall()}
                races = []
                for rid in ids:
                    o = odds.get(rid, {})
                    s = settlements.get(rid, {})
                    i = incidents.get(rid, {})
                    n, valid, distinct, final = (
                        int(o.get(k, 0)) for k in ("n", "valid", "distinct_tickets", "final"))
                    nonfinal = int(o.get("nonfinal", 0))
                    missing_final = int(o.get("missing_final", 0))
                    races.append({
                        "race_id": rid,
                        "odds_rows": n, "valid_odds_rows": valid,
                        "distinct_tickets": distinct,
                        "is_final_true_rows": final,
                        "is_final_false_rows": nonfinal,
                        "is_final_null_rows": missing_final,
                        "odds_shape_verdict": summarize_odds(
                            n, valid, distinct, final, nonfinal, missing_final),
                        "stored_fetch_oldest": (
                            o["oldest_stored_fetch"].isoformat()
                            if o.get("oldest_stored_fetch") else None),
                        "stored_fetch_newest": (
                            o["newest_stored_fetch"].isoformat()
                            if o.get("newest_stored_fetch") else None),
                        "result_present": bool(s),
                        "result_status": s.get("result_status"),
                        "race_status": s.get("race_status"),
                        "trifecta_ticket_present": bool(s.get("trifecta_ticket")),
                        "trifecta_payout_positive": (
                            type(s.get("trifecta_payout_yen")) is int
                            and s["trifecta_payout_yen"] > 0),
                        "entry_rows": int(i.get("rows", 0)),
                        "flying_lanes": int(i.get("flying", 0)),
                        "late_lanes": int(i.get("late", 0)),
                        "refund_eligible_tickets_verified": False,
                        "predecision_first_capture_verified": False,
                    })
                return {**results, "sample": races}
            finally:
                cur.execute("ROLLBACK")


if __name__ == "__main__":
    print(json.dumps(run_sample_audit(), ensure_ascii=False, sort_keys=True))

                               AND split_part(ticket, '-', 1) <> split_part(ticket, '-', 2)
                               AND split_part(ticket, '-', 1) <> split_part(ticket, '-', 3)
                               AND split_part(ticket, '-', 2) <> split_part(ticket, '-', 3)
                               AND odds > 0
                               AND odds::text NOT IN ('NaN','Infinity','-Infinity'))::int AS valid,
                           count(*) FILTER (WHERE is_final IS TRUE)::int AS final,
                           count(*) FILTER (WHERE is_final IS FALSE)::int AS nonfinal,
                           count(*) FILTER (WHERE is_final IS NULL)::int AS missing_final,
                           min(fetched_at) AS oldest_stored_fetch,
                           max(fetched_at) AS newest_stored_fetch
                      FROM v2_odds_trifecta
                     WHERE race_id = ANY(%s)
                     GROUP BY race_id
                """, (list(ids),))
                odds = {r["race_id"]: dict(r) for r in cur.fetchall()}
                cur.execute("""
                    SELECT race_id, result_status, race_status,
                           trifecta_ticket, trifecta_payout_yen
                      FROM v2_results
                     WHERE race_id = ANY(%s)
                """, (list(ids),))
                settlements = {r["race_id"]: dict(r) for r in cur.fetchall()}
                cur.execute("""
                    SELECT race_id, count(*)::int AS rows,
                           count(*) FILTER (WHERE is_flying IS TRUE)::int AS flying,
                           count(*) FILTER (WHERE is_late IS TRUE)::int AS late
                      FROM v2_result_entries
                     WHERE race_id = ANY(%s)
                     GROUP BY race_id
                """, (list(ids),))
                incidents = {r["race_id"]: dict(r) for r in cur.fetchall()}
                races = []
                for rid in ids:
                    o = odds.get(rid, {})
                    s = settlements.get(rid, {})
                    i = incidents.get(rid, {})
                    n, valid, final = (int(o.get(k, 0)) for k in ("n", "valid", "final"))
                    nonfinal = int(o.get("nonfinal", 0))
                    missing_final = int(o.get("missing_final", 0))
                    races.append({
                        "race_id": rid,
                        "odds_rows": n, "valid_odds_rows": valid,
                        "is_final_true_rows": final,
                        "is_final_false_rows": nonfinal,
                        "is_final_null_rows": missing_final,
                        "odds_shape_verdict": summarize_odds(
                            n, valid, final, nonfinal, missing_final),
                        "stored_fetch_oldest": (
                            o["oldest_stored_fetch"].isoformat()
                            if o.get("oldest_stored_fetch") else None),
                        "stored_fetch_newest": (
                            o["newest_stored_fetch"].isoformat()
                            if o.get("newest_stored_fetch") else None),
                        "result_present": bool(s),
                        "result_status": s.get("result_status"),
                        "race_status": s.get("race_status"),
                        "trifecta_ticket_present": bool(s.get("trifecta_ticket")),
                        "trifecta_payout_positive": (
                            type(s.get("trifecta_payout_yen")) is int
                            and s["trifecta_payout_yen"] > 0),
                        "entry_rows": int(i.get("rows", 0)),
                        "flying_lanes": int(i.get("flying", 0)),
                        "late_lanes": int(i.get("late", 0)),
                        "refund_eligible_tickets_verified": False,
                        "predecision_first_capture_verified": False,
                    })
                return {**results, "sample": races}
            finally:
                cur.execute("ROLLBACK")


if __name__ == "__main__":
    print(json.dumps(run_sample_audit(), ensure_ascii=False, sort_keys=True))
