# -*- coding: utf-8 -*-
"""Read-only dry run: annotate the immutable 2026-09-13 V4 freeze with late-market TOP2 support.

This validates wiring only. It must never count as prospective evidence for the
MKT_LATE07_TOP2_SUPPORT_V1 study, whose start date is 2026-09-14 JST.

The six core-order-1 trifecta tickets below come from the independently hashed
pre-result artifact from Actions run 34726186753. No candidate is regenerated.
No outcome table or official K result is read.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

OUTPUT = Path(os.getenv("CANDIDATE_V4_MARKET_DRYRUN_OUTPUT", "candidate-discovery-v4-market-annotation-dryrun.json"))
FREEZE_RUN_ID = 34726186753
FREEZE_ARTIFACT_ID = 10308110102
FREEZE_ZIP_SHA256 = "3930d272fa826d907454e418f4800b3018c4fda9246933f40351311e9bfe3236"
FREEZE_JSON_SHA256 = "50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c"
PROSPECTIVE_START = "2026-09-14"
MAX_SPREAD_SECONDS = 60.0
LATE_MIN_LO = 0.0
LATE_MIN_HI = 7.0

FROZEN_CORE_TOP1 = (
    {"race_id": "20260913_11_02", "venue_id": "11", "race_no": 2, "tier": "A", "ticket": "2-3-5"},
    {"race_id": "20260913_08_08", "venue_id": "08", "race_no": 8, "tier": "A", "ticket": "2-3-6"},
    {"race_id": "20260913_22_03", "venue_id": "22", "race_no": 3, "tier": "B", "ticket": "3-4-5"},
    {"race_id": "20260913_19_05", "venue_id": "19", "race_no": 5, "tier": "B", "ticket": "1-4-3"},
    {"race_id": "20260913_07_07", "venue_id": "07", "race_no": 7, "tier": "C", "ticket": "1-3-4"},
    {"race_id": "20260913_08_05", "venue_id": "08", "race_no": 5, "tier": "C", "ticket": "2-5-1"},
)


def norm_ticket(value: Any) -> str:
    s = str(value or "").replace("=", "-").replace(" ", "")
    parts = [x for x in s.split("-") if x]
    if len(parts) == 3 and all(x in {"1", "2", "3", "4", "5", "6"} for x in parts):
        return "-".join(parts)
    return s


def fetch_latest_late_labels(conn: psycopg.Connection[Any]) -> dict[str, dict[str, Any]]:
    race_ids = [x["race_id"] for x in FROZEN_CORE_TOP1]
    with conn.cursor() as cur:
        cur.execute(
            """
            with grouped as (
              select r.race_id,r.deadline_at,o.snapshot_label,
                     count(*)::bigint row_count,
                     count(distinct o.ticket)::bigint ticket_count,
                     count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint positive_odds_count,
                     min(o.snapshot_at) first_snapshot_at,
                     max(o.snapshot_at) last_snapshot_at
                from v2_races r
                join v2_realtime_odds_snapshots o on o.race_id=r.race_id
               where r.race_id=any(%s)
                 and r.deadline_at is not null
                 and o.snapshot_label is not null
               group by r.race_id,r.deadline_at,o.snapshot_label
            ), valid as (
              select *,
                     extract(epoch from (last_snapshot_at-first_snapshot_at)) spread_seconds,
                     extract(epoch from (deadline_at-last_snapshot_at))/60.0 lead_minutes
                from grouped
               where row_count=120
                 and ticket_count=120
                 and positive_odds_count=120
                 and last_snapshot_at <= deadline_at
                 and extract(epoch from (last_snapshot_at-first_snapshot_at)) <= %s
            ), late as (
              select * from valid
               where lead_minutes >= %s and lead_minutes <= %s
            )
            select distinct on (race_id)
                   race_id,snapshot_label,last_snapshot_at,lead_minutes,spread_seconds
              from late
             order by race_id,last_snapshot_at desc,snapshot_label
            """,
            (race_ids, MAX_SPREAD_SECONDS, LATE_MIN_LO, LATE_MIN_HI),
        )
        return {str(row["race_id"]): dict(row) for row in cur.fetchall()}


def fetch_odds(conn: psycopg.Connection[Any], labels: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    if not labels:
        return {}
    race_ids = list(labels)
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,snapshot_label,ticket,odds
              from v2_realtime_odds_snapshots
             where race_id=any(%s)
               and odds is not null and odds>1.0
             order by race_id,snapshot_label,ticket
            """,
            (race_ids,),
        )
        out: dict[str, dict[str, float]] = {rid: {} for rid in race_ids}
        for row in cur.fetchall():
            rid = str(row["race_id"])
            if str(row.get("snapshot_label") or "") != str(labels[rid]["snapshot_label"]):
                continue
            ticket = norm_ticket(row.get("ticket"))
            if ticket:
                out[rid][ticket] = float(row["odds"])
        return out


def market_top2(odds: dict[str, float]) -> tuple[str, str] | None:
    if len(odds) != 120:
        return None
    scored = []
    for ticket, odd in odds.items():
        if not math.isfinite(odd) or odd <= 1.0:
            return None
        scored.append((1.0 / odd, ticket))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][1], scored[1][1]


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("CANDIDATE_V4_MARKET_DRYRUN_MODE=immutable_freeze_annotation_no_outcome", flush=True)
    print(f"CANDIDATE_V4_MARKET_DRYRUN_FREEZE_RUN={FREEZE_RUN_ID} ARTIFACT={FREEZE_ARTIFACT_ID}", flush=True)
    print(f"CANDIDATE_V4_MARKET_DRYRUN_FREEZE_ZIP_SHA256={FREEZE_ZIP_SHA256}", flush=True)
    print(f"CANDIDATE_V4_MARKET_DRYRUN_FREEZE_JSON_SHA256={FREEZE_JSON_SHA256}", flush=True)
    print(f"CANDIDATE_V4_MARKET_DRYRUN_PROSPECTIVE_START={PROSPECTIVE_START} CURRENT_FREEZE_COUNTS_AS_PROSPECTIVE=0", flush=True)
    print("CANDIDATE_V4_MARKET_DRYRUN_RESULT_READ=0 PAYOUT_READ=0 DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        labels = fetch_latest_late_labels(conn)
        odds_by = fetch_odds(conn, labels)
        conn.rollback()

    rows = []
    for frozen in FROZEN_CORE_TOP1:
        rid = frozen["race_id"]
        label = labels.get(rid)
        top2 = market_top2(odds_by.get(rid, {})) if label else None
        rows.append({
            **frozen,
            "late_snapshot_available": bool(label and top2),
            "snapshot_label": str(label["snapshot_label"]) if label else None,
            "lead_minutes": round(float(label["lead_minutes"]), 3) if label else None,
            "market_top2": list(top2) if top2 else [],
            "market_top2_support": bool(top2 and frozen["ticket"] in set(top2)),
        })

    available = sum(1 for x in rows if x["late_snapshot_available"])
    supported = sum(1 for x in rows if x["market_top2_support"])
    print(f"CANDIDATE_V4_MARKET_DRYRUN_COVERAGE=core_top1:6 late_available:{available} top2_supported:{supported}", flush=True)
    for row in rows:
        print("CANDIDATE_V4_MARKET_DRYRUN_ROW=" + json.dumps(row, ensure_ascii=False, sort_keys=True), flush=True)

    out = {
        "contract": "candidate_discovery_v4_market_annotation_dryrun_20260913_v1",
        "freeze_run_id": FREEZE_RUN_ID,
        "freeze_artifact_id": FREEZE_ARTIFACT_ID,
        "freeze_zip_sha256": FREEZE_ZIP_SHA256,
        "freeze_json_sha256": FREEZE_JSON_SHA256,
        "prospective_study_start": PROSPECTIVE_START,
        "counts_as_prospective": False,
        "late_window_minutes": [LATE_MIN_LO, LATE_MIN_HI],
        "rows": rows,
        "coverage": {"core_top1": 6, "late_available": available, "top2_supported": supported},
        "result_read": False,
        "payout_read": False,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CANDIDATE_V4_MARKET_DRYRUN_PROMOTION=BLOCK_WIRING_ONLY", flush=True)
    print("CANDIDATE_V4_MARKET_DRYRUN_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
