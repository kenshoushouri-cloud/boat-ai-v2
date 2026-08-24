# -*- coding: utf-8 -*-
"""Read-only historical OOS audit of Opponent Pressure incremental value over v24.

Uses the existing frozen historical Opponent Pressure design without tuning:
- START=2025-07-01 / END=2026-08-22
- splits=2026-03-31, 2026-04-30, 2026-05-31
- SHRINK_K=100
- conditional support >=40
- baseline support >=500
- train-only effects

For each OOS six-lane race, current v24 first-place probabilities are
reconstructed from the race-card features using the unchanged v24 lane formula.
The historical train-only pressure delta is added with coefficient exactly 1.0,
then probabilities are clipped positive and renormalized. No coefficient search,
subgroup selection, DB writes, Production/LINE changes, or promotion.
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import v24_pre_candidate_notifier_pg as v24

DB = os.getenv("DATABASE_URL", "").strip()
START = date(2025, 7, 1)
END = date(2026, 8, 22)
SPLITS = (date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 31))
SHRINK_K = 100.0
TRAIN_COND_MIN = 40
TRAIN_BASE_MIN = 500
UNIT_PRESSURE_COEF = 1.0
EPS = 1e-12


def sf(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except Exception:
        return default


def norm(xs: list[float]) -> list[float]:
    ys = [max(EPS, float(x)) for x in xs]
    total = sum(ys)
    return [x / total for x in ys] if total > 0 else [1.0 / len(ys)] * len(ys)


def rank_desc(xs: list[float], idx: int) -> int:
    target = xs[idx]
    return 1 + sum(1 for j, x in enumerate(xs) if j != idx and x > target)


def race_band(race_no: int) -> str:
    if 1 <= race_no <= 4:
        return "R01_04"
    if 5 <= race_no <= 8:
        return "R05_08"
    if 9 <= race_no <= 12:
        return "R09_12"
    return "R_OTHER"


def v24_probs(rows: list[dict[str, Any]], venue: str) -> list[float] | None:
    entries = [
        {
            "lane": r["lane"],
            "racer_class": r["racer_class"],
            "national_win_rate": r["national_win_rate"],
            "national_place2_rate": r["national_place2_rate"],
            "local_place2_rate": r["local_place2_rate"],
            "avg_st": r["avg_st"],
        }
        for r in rows
    ]
    by = v24._entry_by_lane(entries)
    if sorted(by) != [1, 2, 3, 4, 5, 6]:
        return None
    raw = {lane: v24._lane_raw_strength(by[lane], lane, venue) for lane in range(1, 7)}
    return norm([math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)])


def fetch_scored(conn: psycopg.Connection, split: date) -> list[dict[str, Any]]:
    q = """
    with base as (
      select r.race_date,r.race_id,
             coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,''),'') venue,
             r.race_no,
             a.lane,a.racer_class,a.national_win_rate,a.national_place2_rate,
             a.local_place2_rate,a.avg_st,
             b.lane opp_lane,b.racer_class opp_class,
             re.finish_position,
             case when re.finish_position=1 then 1.0 else 0.0 end win,
             case when re.finish_position between 1 and 3 then 1.0 else 0.0 end top3
      from v2_race_entries a
      join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date between %s and %s
        and a.racer_class between 1 and 4 and b.racer_class between 1 and 4
        and re.finish_position between 1 and 6
    ),
    tbase as (
      select racer_class own_class,lane own_lane,count(*)/5.0 n,
             avg(win) pwin,avg(top3) ptop3
      from base where race_date<=%s group by 1,2
    ),
    teff as (
      select b.racer_class own_class,b.lane own_lane,b.opp_lane,b.opp_class,count(*) n,
             (avg(b.win)-tb.pwin) * (count(*)::float8/(count(*)+%s)) ewin,
             (avg(b.top3)-tb.ptop3) * (count(*)::float8/(count(*)+%s)) etop3
      from base b join tbase tb on tb.own_class=b.racer_class and tb.own_lane=b.lane
      where b.race_date<=%s and tb.n>=%s
      group by b.racer_class,b.lane,b.opp_lane,b.opp_class,tb.pwin,tb.ptop3
      having count(*)>=%s
    ),
    scored as (
      select b.race_id,b.race_date,b.venue,b.race_no,b.lane,b.racer_class,
             b.national_win_rate,b.national_place2_rate,b.local_place2_rate,b.avg_st,
             max(b.finish_position) finish_position,tb.pwin,
             avg(coalesce(t.ewin,0)) score_win,count(t.opp_lane) matched_opp
      from base b
      join tbase tb on tb.own_class=b.racer_class and tb.own_lane=b.lane
      left join teff t on t.own_class=b.racer_class and t.own_lane=b.lane
                       and t.opp_lane=b.opp_lane and t.opp_class=b.opp_class
      where b.race_date>%s and tb.n>=%s
      group by b.race_id,b.race_date,b.venue,b.race_no,b.lane,b.racer_class,
               b.national_win_rate,b.national_place2_rate,b.local_place2_rate,b.avg_st,tb.pwin
    )
    select race_id,race_date,lpad(venue,2,'0') venue,race_no,lane,racer_class,
           national_win_rate,national_place2_rate,local_place2_rate,avg_st,
           finish_position,matched_opp,
           greatest(.001,least(.999,pwin+score_win))-pwin pressure_delta
    from scored
    where matched_opp>=4
    order by race_id,lane
    """
    params = (
        START, END, split, SHRINK_K, SHRINK_K, split,
        TRAIN_BASE_MIN, TRAIN_COND_MIN, split, TRAIN_BASE_MIN,
    )
    with conn.cursor() as cur:
        cur.execute(q, params)
        return [dict(r) for r in cur.fetchall()]


def build_records(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_race[str(row["race_id"])].append(row)

    records: list[dict[str, Any]] = []
    incomplete = 0
    for rid, rr in by_race.items():
        rr = sorted(rr, key=lambda x: int(x["lane"]))
        if len(rr) != 6 or [int(x["lane"]) for x in rr] != [1, 2, 3, 4, 5, 6]:
            incomplete += 1
            continue
        winners = [i for i, x in enumerate(rr) if int(x["finish_position"]) == 1]
        if len(winners) != 1:
            incomplete += 1
            continue
        idx = winners[0]
        venue = str(rr[0].get("venue") or "").zfill(2)
        base_p = v24_probs(rr, venue)
        if base_p is None:
            incomplete += 1
            continue
        delta = [sf(x.get("pressure_delta")) for x in rr]
        plus_p = norm([
            max(EPS, min(0.999, base_p[i] + UNIT_PRESSURE_COEF * delta[i]))
            for i in range(6)
        ])
        y = [1.0 if i == idx else 0.0 for i in range(6)]
        records.append({
            "race_id": rid,
            "venue": venue,
            "race_band": race_band(int(rr[0].get("race_no") or 0)),
            "brier_v24": sum((y[i] - base_p[i]) ** 2 for i in range(6)) / 6.0,
            "brier_opp": sum((y[i] - plus_p[i]) ** 2 for i in range(6)) / 6.0,
            "logloss_v24": -math.log(max(EPS, base_p[idx])),
            "logloss_opp": -math.log(max(EPS, plus_p[idx])),
            "rank_v24": float(rank_desc(base_p, idx)),
            "rank_opp": float(rank_desc(plus_p, idx)),
            "avg_abs_delta": sum(abs(x) for x in delta) / 6.0,
        })
    return records, incomplete


def aggregate(records: list[dict[str, Any]]) -> dict[str, float]:
    n = len(records)
    if not n:
        return {k: 0.0 for k in (
            "n", "brier_v24", "brier_opp", "logloss_v24", "logloss_opp",
            "rank_v24", "rank_opp", "avg_abs_delta",
        )}
    return {
        "n": float(n),
        "brier_v24": sum(x["brier_v24"] for x in records) / n,
        "brier_opp": sum(x["brier_opp"] for x in records) / n,
        "logloss_v24": sum(x["logloss_v24"] for x in records) / n,
        "logloss_opp": sum(x["logloss_opp"] for x in records) / n,
        "rank_v24": sum(x["rank_v24"] for x in records) / n,
        "rank_opp": sum(x["rank_opp"] for x in records) / n,
        "avg_abs_delta": sum(x["avg_abs_delta"] for x in records) / n,
    }


def emit(split: date, label: str, m: dict[str, float]) -> None:
    print(
        f"OPP_V24_OOS_INCREMENTAL={split}|{label} n:{int(m['n'])} "
        f"winner_brier_v24:{m['brier_v24']:.8f} winner_brier_plus_opp:{m['brier_opp']:.8f} "
        f"brier_delta:{m['brier_opp']-m['brier_v24']:+.8f} "
        f"winner_logloss_v24:{m['logloss_v24']:.8f} winner_logloss_plus_opp:{m['logloss_opp']:.8f} "
        f"logloss_delta:{m['logloss_opp']-m['logloss_v24']:+.8f} "
        f"winner_rank_v24:{m['rank_v24']:.4f} winner_rank_plus_opp:{m['rank_opp']:.4f} "
        f"rank_delta:{m['rank_opp']-m['rank_v24']:+.4f} avg_abs_pressure_delta:{m['avg_abs_delta']:.6f}",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_V24_OOS_INCREMENTAL_MODE=read_only_fixed_historical_design_no_tuning", flush=True)
    print(f"OPP_V24_OOS_INCREMENTAL_PERIOD={START}..{END}", flush=True)
    print("OPP_V24_OOS_INCREMENTAL_SPLITS=2026-03-31,2026-04-30,2026-05-31", flush=True)
    print(
        f"OPP_V24_OOS_INCREMENTAL_GATES=train_cond>={TRAIN_COND_MIN},train_base>={TRAIN_BASE_MIN},shrink_k={SHRINK_K}",
        flush=True,
    )
    print("OPP_V24_OOS_INCREMENTAL_BASE=current_v24_fixed_motor33_boat34_prob_temp_2.20", flush=True)
    print(f"OPP_V24_OOS_INCREMENTAL_COEF={UNIT_PRESSURE_COEF:.1f}_fixed_unit_pressure_delta_no_tuning", flush=True)
    print("OPP_V24_OOS_INCREMENTAL_POLICY=train_only_pressure_effects_no_writes_no_production_no_line_no_subgroup_selection", flush=True)

    split_directions: list[tuple[float, float, float]] = []
    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='240s'")
        for split in SPLITS:
            lane_rows = fetch_scored(conn, split)
            records, incomplete = build_records(lane_rows)
            print(
                f"OPP_V24_OOS_INCREMENTAL_COVERAGE={split}=lane_rows:{len(lane_rows)} evaluated_races:{len(records)} incomplete:{incomplete}",
                flush=True,
            )
            overall = aggregate(records)
            emit(split, "OVERALL", overall)
            split_directions.append((
                overall["brier_opp"] - overall["brier_v24"],
                overall["logloss_opp"] - overall["logloss_v24"],
                overall["rank_opp"] - overall["rank_v24"],
            ))

            by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
            by_venue: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for rec in records:
                by_band[rec["race_band"]].append(rec)
                by_venue[rec["venue"]].append(rec)
            for band in ("R01_04", "R05_08", "R09_12", "R_OTHER"):
                if by_band.get(band):
                    emit(split, f"RACE_BAND:{band}", aggregate(by_band[band]))

            venue_metrics = [aggregate(by_venue[v]) for v in sorted(by_venue)]
            print(
                f"OPP_V24_OOS_INCREMENTAL_VENUE_SIGN_COUNT={split}=venues:{len(venue_metrics)} "
                f"brier_better:{sum((m['brier_opp']-m['brier_v24']) < 0 for m in venue_metrics)} "
                f"logloss_better:{sum((m['logloss_opp']-m['logloss_v24']) < 0 for m in venue_metrics)} "
                f"rank_better:{sum((m['rank_opp']-m['rank_v24']) < 0 for m in venue_metrics)}",
                flush=True,
            )

    all_core_better = bool(split_directions) and all(b < 0 and l < 0 for b, l, _ in split_directions)
    all_three_better = bool(split_directions) and all(b < 0 and l < 0 and r < 0 for b, l, r in split_directions)
    if all_three_better:
        interpretation = "CONSISTENT_INCREMENTAL_OOS_RESEARCH_SUPPORT"
    elif all_core_better:
        interpretation = "CONSISTENT_PROBABILITY_INCREMENTAL_OOS_SUPPORT_RANK_MIXED"
    else:
        interpretation = "MIXED_OR_NO_INCREMENTAL_OOS_SUPPORT"
    print(f"OPP_V24_OOS_INCREMENTAL_INTERPRETATION={interpretation}", flush=True)
    print("OPP_V24_OOS_INCREMENTAL_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_V24_OOS_INCREMENTAL_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_V24_OOS_INCREMENTAL_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
