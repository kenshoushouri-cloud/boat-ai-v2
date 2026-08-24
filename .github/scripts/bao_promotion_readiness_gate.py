# -*- coding: utf-8 -*-
"""Read-only Bao promotion-readiness gate.

This script intentionally separates proxy Forward sample counts from realized-result
sample counts. Reaching 30 market or exhibition proxy pairs never promotes anything
by itself. Even when all sample-count gates are met, the output only says that a
manual review may begin.

No DB writes, no Production decision changes, no LINE changes.
"""
from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "").strip()
MIN_PAIRS = int(os.getenv("BAO_PROMOTION_MIN_PAIRS", "30"))


def _state(count: int) -> str:
    return "READY" if count >= MIN_PAIRS else "BLOCKED"


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL is required")

    print("BAO_PROMOTION_GATE_MODE=read_only", flush=True)
    print(f"BAO_PROMOTION_GATE_MIN_PAIRS={MIN_PAIRS}", flush=True)
    print("BAO_PROMOTION_GATE_POLICY=no_writes_no_production_no_line_manual_review_required", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with market_pairs as (
                    select e.race_id, e.captured_at as early_at, l.captured_at as late_at
                    from v2_bao_market_shadow_snapshots e
                    join v2_bao_market_shadow_snapshots l
                      on l.race_id = e.race_id
                     and l.phase = 'late'
                    where e.phase = 'early'
                ),
                exhibition_pairs as (
                    select distinct m.race_id
                    from market_pairs m
                    join v2_bao_exhibition_shadow_snapshots x
                      on x.race_id = m.race_id
                    where x.captured_at > m.early_at
                      and x.captured_at < m.late_at
                      and x.minutes_before >= 8.0
                      and x.minutes_before <= 15.0
                ),
                motor_realized as (
                    select distinct m.race_id
                    from market_pairs m
                    join v2_results r on r.race_id = m.race_id
                    where nullif(trim(coalesce(r.trifecta_ticket, '')), '') is not null
                ),
                exhibition_realized as (
                    select distinct x.race_id
                    from exhibition_pairs x
                    join v2_results r on r.race_id = x.race_id
                    where nullif(trim(coalesce(r.trifecta_ticket, '')), '') is not null
                )
                select
                    (select count(*) from market_pairs) as market_pairs,
                    (select count(*) from exhibition_pairs) as exhibition_pairs,
                    (select count(*) from motor_realized) as motor_realized,
                    (select count(*) from exhibition_realized) as exhibition_realized
                """
            )
            row = dict(cur.fetchone())

    market_pairs = int(row.get("market_pairs") or 0)
    exhibition_pairs = int(row.get("exhibition_pairs") or 0)
    motor_realized = int(row.get("motor_realized") or 0)
    exhibition_realized = int(row.get("exhibition_realized") or 0)

    print(
        f"BAO_PROMOTION_GATE_MARKET_PROXY={_state(market_pairs)} count:{market_pairs}/{MIN_PAIRS}",
        flush=True,
    )
    print(
        f"BAO_PROMOTION_GATE_EXHIBITION_PROXY={_state(exhibition_pairs)} count:{exhibition_pairs}/{MIN_PAIRS}",
        flush=True,
    )
    print(
        f"BAO_PROMOTION_GATE_MOTOR_REALIZED={_state(motor_realized)} count:{motor_realized}/{MIN_PAIRS}",
        flush=True,
    )
    print(
        f"BAO_PROMOTION_GATE_EXHIBITION_REALIZED={_state(exhibition_realized)} count:{exhibition_realized}/{MIN_PAIRS}",
        flush=True,
    )

    all_ready = all(
        count >= MIN_PAIRS
        for count in (market_pairs, exhibition_pairs, motor_realized, exhibition_realized)
    )
    if all_ready:
        print("BAO_PROMOTION_GATE_OVERALL=READY_FOR_MANUAL_REVIEW", flush=True)
    else:
        print("BAO_PROMOTION_GATE_OVERALL=BLOCKED_INSUFFICIENT_EVIDENCE", flush=True)
    print("BAO_PROMOTION_GATE_AUTO_PROMOTION=DISABLED", flush=True)
    print("BAO_PROMOTION_GATE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
