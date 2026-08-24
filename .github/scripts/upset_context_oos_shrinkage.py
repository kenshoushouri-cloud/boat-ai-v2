# -*- coding: utf-8 -*-
"""Read-only chronological OOS audit for venue x meet-day x race-band upset context.

Goal: test whether venue-specific context adds predictive information beyond a
national manshu baseline, without tuning Production thresholds or coefficients.

Outcome: trifecta payout >= 10,000 yen.
Models are trained only on dates before each test block:
  M0 GLOBAL: train manshu rate.
  M1 VENUE: venue rate shrunk to global with fixed K_VENUE=400 races.
  M2 CONTEXT: venue x meet-day bucket x race-band rate shrunk to M1 with
     fixed K_CONTEXT=200 races.

The shrinkage constants are conservative pre-declared research constants and are
not searched or selected from test results. This is historical OOS research only.
No DB writes, Production/LINE changes, threshold search or promotion.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "").strip()
START = date(2025, 7, 1)
END = date(2026, 8, 24)
BUFFER_DAYS = 7
MAX_MEET_DAYS = 7
MANSHU = 10_000
K_VENUE = 400.0
K_CONTEXT = 200.0
EPS = 1e-12

SPLITS = [
    (date(2025, 7, 1), date(2025, 10, 31), date(2025, 11, 1), date(2026, 2, 28), "OOS1"),
    (date(2025, 7, 1), date(2026, 2, 28), date(2026, 3, 1), date(2026, 5, 31), "OOS2"),
    (date(2025, 7, 1), date(2026, 5, 31), date(2026, 6, 1), date(2026, 8, 24), "OOS3"),
]


def day_bucket(d: int) -> str:
    if d == 1:
        return "D1"
    if d == 2:
        return "D2"
    if d in (3, 4):
        return "D3_4"
    return "D5_PLUS"


def race_band(r: int) -> str:
    if r <= 4:
        return "R01_04"
    if r <= 8:
        return "R05_08"
    return "R09_12"


def metrics(y: list[int], p: list[float]) -> tuple[float, float]:
    n = len(y)
    brier = sum((pp - yy) ** 2 for yy, pp in zip(y, p)) / n
    ll = -sum(yy * math.log(max(EPS, pp)) + (1 - yy) * math.log(max(EPS, 1 - pp)) for yy, pp in zip(y, p)) / n
    return brier, ll


def infer_meet_days(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    venue_dates: dict[str, list[date]] = defaultdict(list)
    for r in raw:
        venue_dates[r["venue"]].append(r["race_date"])
    day_map: dict[tuple[str, date], int] = {}
    ambiguous: set[tuple[str, date]] = set()
    for venue, ds0 in venue_dates.items():
        ds = sorted(set(ds0))
        streak: list[date] = []
        streaks: list[list[date]] = []
        for d in ds:
            if not streak or d == streak[-1] + timedelta(days=1):
                streak.append(d)
            else:
                streaks.append(streak); streak = [d]
        if streak:
            streaks.append(streak)
        for s in streaks:
            if len(s) > MAX_MEET_DAYS:
                ambiguous.update((venue, d) for d in s)
            else:
                for i, d in enumerate(s, 1):
                    day_map[(venue, d)] = i
    out = []
    for r in raw:
        key = (r["venue"], r["race_date"])
        if key in ambiguous or key not in day_map or r["race_date"] < START:
            continue
        x = dict(r)
        x["day_bucket"] = day_bucket(day_map[key])
        x["race_band"] = race_band(x["race_no"])
        x["y"] = 1 if x["payout"] >= MANSHU else 0
        out.append(x)
    return out


def fit_predict(train: list[dict[str, Any]], test: list[dict[str, Any]]) -> tuple[list[float], list[float], list[float]]:
    global_p = sum(r["y"] for r in train) / len(train)
    vstats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    cstats: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in train:
        vstats[r["venue"]][0] += r["y"]; vstats[r["venue"]][1] += 1
        k = (r["venue"], r["day_bucket"], r["race_band"])
        cstats[k][0] += r["y"]; cstats[k][1] += 1
    venue_p: dict[str, float] = {}
    for v, (hits, n) in vstats.items():
        venue_p[v] = (hits + K_VENUE * global_p) / (n + K_VENUE)
    p0: list[float] = []
    p1: list[float] = []
    p2: list[float] = []
    for r in test:
        pv = venue_p.get(r["venue"], global_p)
        hits, n = cstats.get((r["venue"], r["day_bucket"], r["race_band"]), [0, 0])
        pc = (hits + K_CONTEXT * pv) / (n + K_CONTEXT)
        p0.append(global_p); p1.append(pv); p2.append(pc)
    return p0, p1, p2


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("UPSET_CONTEXT_OOS_MODE=read_only_chronological_shrinkage_no_tuning")
    print(f"UPSET_CONTEXT_OOS_PERIOD={START}..{END} buffer_days:{BUFFER_DAYS}")
    print(f"UPSET_CONTEXT_OOS_SHRINKAGE=venue_K:{K_VENUE:.0f} context_K:{K_CONTEXT:.0f}_fixed_not_searched")
    print("UPSET_CONTEXT_OOS_MODELS=M0_global,M1_venue,M2_venue_x_meetday_x_raceband")
    print("UPSET_CONTEXT_OOS_POLICY=train_before_test_no_threshold_search_no_writes_no_production_no_line_no_promotion")
    qstart = START - timedelta(days=BUFFER_DAYS)
    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute("""
                select q.race_date::date race_date,
                       lpad(coalesce(nullif(q.venue_id::text,''),nullif(q.venue_code::text,'')),2,'0') venue,
                       q.race_no::int race_no,
                       r.trifecta_payout_yen::float8 payout
                from v2_results r join v2_races q on q.race_id=r.race_id
                where q.race_date between %s and %s
                  and q.race_no between 1 and 12
                  and r.trifecta_payout_yen is not null and r.trifecta_payout_yen > 0
                  and coalesce(r.result_status,'')='official'
                  and coalesce(r.race_status,'')='official'
                order by q.race_date,venue,q.race_no
            """, (qstart, END))
            raw = [dict(x) for x in cur.fetchall()]
    rows = infer_meet_days(raw)
    print(f"UPSET_CONTEXT_OOS_COVERAGE=evaluated:{len(rows)}")
    total_n = 0
    agg_y: list[int] = []
    agg_p = {"M0": [], "M1": [], "M2": []}
    wins = {"M1_brier": 0, "M1_ll": 0, "M2_brier": 0, "M2_ll": 0, "M2_vs_M1_brier": 0, "M2_vs_M1_ll": 0}
    for tr0, tr1, te0, te1, label in SPLITS:
        train = [r for r in rows if tr0 <= r["race_date"] <= tr1]
        test = [r for r in rows if te0 <= r["race_date"] <= te1]
        y = [r["y"] for r in test]
        p0, p1, p2 = fit_predict(train, test)
        m0 = metrics(y, p0); m1 = metrics(y, p1); m2 = metrics(y, p2)
        print(f"UPSET_CONTEXT_OOS={label} train_n:{len(train)} test_n:{len(test)} event_rate:{sum(y)/len(y)*100:.2f}% "
              f"M0_brier:{m0[0]:.8f} M1_brier:{m1[0]:.8f} M2_brier:{m2[0]:.8f} "
              f"M1_vs_M0_brier:{m1[0]-m0[0]:+.8f} M2_vs_M0_brier:{m2[0]-m0[0]:+.8f} M2_vs_M1_brier:{m2[0]-m1[0]:+.8f} "
              f"M0_ll:{m0[1]:.8f} M1_ll:{m1[1]:.8f} M2_ll:{m2[1]:.8f} "
              f"M1_vs_M0_ll:{m1[1]-m0[1]:+.8f} M2_vs_M0_ll:{m2[1]-m0[1]:+.8f} M2_vs_M1_ll:{m2[1]-m1[1]:+.8f}")
        wins["M1_brier"] += m1[0] < m0[0]; wins["M1_ll"] += m1[1] < m0[1]
        wins["M2_brier"] += m2[0] < m0[0]; wins["M2_ll"] += m2[1] < m0[1]
        wins["M2_vs_M1_brier"] += m2[0] < m1[0]; wins["M2_vs_M1_ll"] += m2[1] < m1[1]
        total_n += len(test); agg_y.extend(y); agg_p["M0"].extend(p0); agg_p["M1"].extend(p1); agg_p["M2"].extend(p2)
    a0 = metrics(agg_y, agg_p["M0"]); a1 = metrics(agg_y, agg_p["M1"]); a2 = metrics(agg_y, agg_p["M2"])
    print(f"UPSET_CONTEXT_OOS=COMBINED test_n:{total_n} M0_brier:{a0[0]:.8f} M1_brier:{a1[0]:.8f} M2_brier:{a2[0]:.8f} "
          f"M1_vs_M0_brier:{a1[0]-a0[0]:+.8f} M2_vs_M0_brier:{a2[0]-a0[0]:+.8f} M2_vs_M1_brier:{a2[0]-a1[0]:+.8f} "
          f"M0_ll:{a0[1]:.8f} M1_ll:{a1[1]:.8f} M2_ll:{a2[1]:.8f} "
          f"M1_vs_M0_ll:{a1[1]-a0[1]:+.8f} M2_vs_M0_ll:{a2[1]-a0[1]:+.8f} M2_vs_M1_ll:{a2[1]-a1[1]:+.8f}")
    print("UPSET_CONTEXT_OOS_SIGN_COUNTS=" + ",".join(f"{k}:{v}/3" for k,v in wins.items()))
    print("UPSET_CONTEXT_OOS_INTERPRETATION=HISTORICAL_OOS_FEATURE_READINESS_ONLY_REQUIRE_FORWARD_BEFORE_MODEL_USE")
    print("UPSET_CONTEXT_OOS_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE")
    print("UPSET_CONTEXT_OOS_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
