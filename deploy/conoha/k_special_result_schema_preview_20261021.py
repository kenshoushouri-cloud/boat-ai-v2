# -*- coding: utf-8 -*-
"""Read-only schema and final-state preflight before handling a 3連単不成立 result.

No INSERT/UPDATE/DELETE/DDL. Do NOT count trifecta_invalid as a losing bet.
"""
from __future__ import annotations

import os

import psycopg

RID = "20261008_14_05"
DB = "postgresql:///railway"
DAYS = (
    ("20261008_", "20261009_", 143),
    ("20261015_", "20261016_", 156),
    ("20261016_", "20261017_", 156),
    ("20261017_", "20261018_", 168),
)


def main():
    if os.geteuid() == 0:
        raise SystemExit("STOP: run as postgres")
    print("MODE=READ_ONLY_SPECIAL_SCHEMA_PREFLIGHT", flush=True)
    with psycopg.connect(
        DB, options="-c default_transaction_read_only=on -c statement_timeout=15000"
    ) as conn:
        with conn.cursor() as cur:
            for lower, upper, expected in DAYS:
                cur.execute(
                    "SELECT count(*) FROM public.v2_results "
                    "WHERE race_id >= %s AND race_id < %s", (lower, upper)
                )
                n = int(cur.fetchone()[0])
                print("DAY=" + lower[:8] + " RESULTS=" + str(n) +
                      " EXPECTED=" + str(expected), flush=True)
                if n != expected:
                    raise RuntimeError("STOP: results count changed; do not write")
            cur.execute(
                "SELECT (SELECT count(*) FROM public.v2_races WHERE race_id=%s),"
                "(SELECT count(*) FROM public.v2_race_entries WHERE race_id=%s),"
                "(SELECT count(*) FROM public.v2_results WHERE race_id=%s),"
                "(SELECT count(*) FROM public.v2_result_entries WHERE race_id=%s)",
                (RID, RID, RID, RID),
            )
            counts = tuple(int(x) for x in cur.fetchone())
            print("SPECIAL_RACE_ENTRIES_RESULTS_DETAILS=" + str(counts), flush=True)
            if counts[:3] != (1, 6, 0):
                raise RuntimeError("STOP: missing race/roster or existing result")

            cur.execute(
                "SELECT column_name,udt_name,is_nullable,column_default "
                "FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='v2_results' "
                "ORDER BY ordinal_position"
            )
            cols = cur.fetchall()
            required = [row[0] for row in cols if row[2] == "NO" and row[3] is None]
            print("RESULTS_REQUIRED_NO_DEFAULT=" + str(required), flush=True)
            wanted = {
                "race_id", "race_date", "venue_code", "race_no",
                "result_status", "race_status", "trifecta_ticket",
                "trifecta_payout_yen", "official", "source", "fetched_at",
                "finish_order", "winning_method", "raw",
            }
            print("RESULTS_RELEVANT_COLUMN_TYPES=" +
                  str([(row[0], row[1], row[2]) for row in cols
                       if row[0] in wanted]), flush=True)
            cur.execute(
                "SELECT conname,pg_get_constraintdef(oid) "
                "FROM pg_constraint "
                "WHERE conrelid='public.v2_results'::regclass "
                "AND contype IN ('c','f','p','u') ORDER BY conname"
            )
            print("RESULTS_CONSTRAINTS=" + str(cur.fetchall()), flush=True)
            cur.execute(
                "SELECT result_status,race_status,count(*) "
                "FROM public.v2_results "
                "WHERE race_id >= '20261008_' AND race_id < '20261009_' "
                "GROUP BY 1,2 ORDER BY 1,2"
            )
            print("OCT08_RESULT_STATUS_COUNTS=" + str(cur.fetchall()), flush=True)
    print("SPECIAL_SCHEMA_PREFLIGHT_PASS_NO_DB_WRITES", flush=True)
    print("HISTORICAL_RETRIEVAL_NOT_PREDECISION", flush=True)


if __name__ == "__main__":
    main()
