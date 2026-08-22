# -*- coding: utf-8 -*-
"""Read-only readiness audit for a full-market (120 trifecta tickets) historical replay.

Goals:
- measure 2025-07-01..2026-08-22 coverage for the inputs used by the existing
  odds-independent v24/motor2 probability model;
- measure 120-ticket odds and result coverage;
- quantify the intersection that can be replayed without DB writes;
- explicitly flag that today's static coefficients are not a genuine historical
  walk-forward model unless coefficients are frozen/trained only on prior data.

No DB writes, no Production/Shadow/LINE changes.
"""
from __future__ import annotations

import os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
START = os.getenv("BAO_REPLAY_START", "2025-07-01")
END = os.getenv("BAO_REPLAY_END", "2026-08-22")


def one(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        r = cur.fetchone()
        return dict(r) if r else {}


def pct(n, d):
    return 0.0 if not d else 100.0 * float(n or 0) / float(d)


def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")

    print("BAO_120_MODE=read_only", flush=True)
    print(f"BAO_120_PERIOD={START}..{END}", flush=True)
    print("BAO_120_DB_WRITES=0", flush=True)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='120s'")
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='12MB'")

        total = one(conn, """
            select count(*)::bigint races
            from v2_races
            where race_date between %s::date and %s::date
        """, (START, END))["races"]

        coverage = one(conn, """
            with e as (
              select r.race_id,
                     count(*)::int n,
                     count(*) filter(where e.racer_class is not null)::int cls,
                     count(*) filter(where e.national_win_rate is not null)::int nwr,
                     count(*) filter(where e.national_place2_rate is not null)::int n2,
                     count(*) filter(where e.local_place2_rate is not null)::int l2,
                     count(*) filter(where e.avg_st is not null)::int ast,
                     count(*) filter(where e.motor_place2_rate is not null)::int m2
              from v2_races r
              left join v2_race_entries e on e.race_id=r.race_id
              where r.race_date between %s::date and %s::date
              group by r.race_id
            )
            select
              count(*) filter(where n=6)::bigint entries6,
              count(*) filter(where n=6 and cls=6 and nwr=6 and n2=6 and l2=6 and ast=6)::bigint base_ready,
              count(*) filter(where n=6 and cls=6 and nwr=6 and n2=6 and l2=6 and ast=6 and m2=6)::bigint motor2_strict_ready,
              count(*) filter(where n=6 and m2<6)::bigint motor2_partial
            from e
        """, (START, END))

        odds = one(conn, """
            with x as (
              select r.race_id, count(o.*)::int n
              from v2_races r
              left join v2_odds_trifecta o on o.race_id=r.race_id
              where r.race_date between %s::date and %s::date
              group by r.race_id
            )
            select
              count(*) filter(where n>=120)::bigint odds120,
              count(*) filter(where n>0)::bigint odds_any
            from x
        """, (START, END))

        results = one(conn, """
            select
              count(*) filter(where res.race_id is not null)::bigint result_rows,
              count(*) filter(where res.trifecta_ticket is not null)::bigint result_ticket,
              count(*) filter(where res.trifecta_payout_yen is not null)::bigint payout
            from v2_races r
            left join v2_results res on res.race_id=r.race_id
            where r.race_date between %s::date and %s::date
        """, (START, END))

        intersection = one(conn, """
            with e as (
              select r.race_id,
                     count(e.*)::int n,
                     count(*) filter(where e.racer_class is not null)::int cls,
                     count(*) filter(where e.national_win_rate is not null)::int nwr,
                     count(*) filter(where e.national_place2_rate is not null)::int n2,
                     count(*) filter(where e.local_place2_rate is not null)::int l2,
                     count(*) filter(where e.avg_st is not null)::int ast,
                     count(*) filter(where e.motor_place2_rate is not null)::int m2
              from v2_races r
              left join v2_race_entries e on e.race_id=r.race_id
              where r.race_date between %s::date and %s::date
              group by r.race_id
            ), o as (
              select r.race_id,count(ot.*)::int n
              from v2_races r
              left join v2_odds_trifecta ot on ot.race_id=r.race_id
              where r.race_date between %s::date and %s::date
              group by r.race_id
            )
            select
              count(*) filter(where e.n=6 and e.cls=6 and e.nwr=6 and e.n2=6 and e.l2=6 and e.ast=6
                                      and o.n>=120 and res.trifecta_ticket is not null and res.trifecta_payout_yen is not null)::bigint base_full,
              count(*) filter(where e.n=6 and e.cls=6 and e.nwr=6 and e.n2=6 and e.l2=6 and e.ast=6 and e.m2=6
                                      and o.n>=120 and res.trifecta_ticket is not null and res.trifecta_payout_yen is not null)::bigint motor2_full
            from e
            join o using(race_id)
            left join v2_results res using(race_id)
        """, (START, END, START, END))

    print(f"BAO_120_RACES={total}", flush=True)
    print(f"BAO_120_ENTRIES6={coverage['entries6']}/{total} ({pct(coverage['entries6'],total):.2f}%)", flush=True)
    print(f"BAO_120_BASE_INPUT_READY={coverage['base_ready']}/{total} ({pct(coverage['base_ready'],total):.2f}%)", flush=True)
    print(f"BAO_120_MOTOR2_STRICT_READY={coverage['motor2_strict_ready']}/{total} ({pct(coverage['motor2_strict_ready'],total):.2f}%)", flush=True)
    print(f"BAO_120_MOTOR2_PARTIAL_RACES={coverage['motor2_partial']}", flush=True)
    print(f"BAO_120_ODDS120={odds['odds120']}/{total} ({pct(odds['odds120'],total):.2f}%)", flush=True)
    print(f"BAO_120_ODDS_ANY={odds['odds_any']}/{total} ({pct(odds['odds_any'],total):.2f}%)", flush=True)
    print(f"BAO_120_RESULT_TICKET={results['result_ticket']}/{total} ({pct(results['result_ticket'],total):.2f}%)", flush=True)
    print(f"BAO_120_PAYOUT={results['payout']}/{total} ({pct(results['payout'],total):.2f}%)", flush=True)
    print(f"BAO_120_BASE_FULL_INTERSECTION={intersection['base_full']}/{total} ({pct(intersection['base_full'],total):.2f}%)", flush=True)
    print(f"BAO_120_MOTOR2_FULL_INTERSECTION={intersection['motor2_full']}/{total} ({pct(intersection['motor2_full'],total):.2f}%)", flush=True)
    print(f"BAO_120_TICKET_EVAL_SCALE_BASE={int(intersection['base_full'] or 0)*120}", flush=True)

    # Code-level leakage/readiness audit. The existing forward collector generates
    # all 120 probabilities independently of odds, but relies on current static
    # constants from v24. Those constants are not historically versioned here.
    collector = Path("collect_v24_motor2_forward_shadow_pg.py").read_text(encoding="utf-8")
    v24 = Path("v24_pre_candidate_notifier_pg.py").read_text(encoding="utf-8")
    odds_independent = "def probs(" in collector and "raw_strength" in collector and "market_ranks" in collector
    uses_static = all(k in collector for k in ["CLASS_WEIGHT", "VENUE_COURSE_BIAS", "PROB_TEMP"])
    has_param_versioning = any(k in v24.lower() for k in ["parameter_version_by_date", "model_version_by_date", "train_cutoff"])
    print(f"BAO_120_ODDS_INDEPENDENT_PROB_GENERATOR={int(odds_independent)}", flush=True)
    print(f"BAO_120_CURRENT_STATIC_PARAMS={int(uses_static)}", flush=True)
    print(f"BAO_120_HISTORICAL_PARAM_VERSIONING={int(has_param_versioning)}", flush=True)

    # A historical replay with today's fixed coefficients is useful as a
    # diagnostic backtest, but cannot be called true OOS/walk-forward.
    if odds_independent and intersection['base_full'] >= 10000:
        print("BAO_120_REPLAY_READINESS=READY_FOR_BACKTEST_REPLAY", flush=True)
    else:
        print("BAO_120_REPLAY_READINESS=LIMITED", flush=True)

    if uses_static and not has_param_versioning:
        print("BAO_120_OOS_STATUS=BLOCKED_UNTIL_TRAIN_ONLY_OR_FROZEN_PARAMETER_POLICY", flush=True)
    else:
        print("BAO_120_OOS_STATUS=REVIEW_REQUIRED", flush=True)

    print("BAO_120_NEXT=train_only_parameter_policy_then_chronological_120_ticket_replay", flush=True)
    print("BAO_120_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
