# -*- coding: utf-8 -*-
"""Read-only daily decomposition of head-only Opponent Pressure Forward results.

This does not select or tune on dates. It only decomposes the already-fixed
head-only mapping by race_date to explain the gap between strong historical OOS
support and mixed realized Forward ranking.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

import opponent_pressure_v24_trifecta_forward as naive
import opponent_pressure_v24_trifecta_head_only_forward as head

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat(os.getenv("OPP_V24_HEAD_DAILY_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_V24_HEAD_DAILY_END", date.today().isoformat()))
EPS = 1e-15
UNIT_PRESSURE_COEF = 1.0


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    if not n:
        return {k: 0.0 for k in (
            "n", "brier_base", "brier_plus", "ll_base", "ll_plus",
            "rank_base", "rank_plus", "top1_base", "top1_plus",
            "top3_base", "top3_plus", "top5_base", "top5_plus",
            "top10_base", "top10_plus", "avg_abs_delta",
        )}
    return {
        "n": float(n),
        "brier_base": sum(x["brier_base"] for x in rows) / n,
        "brier_plus": sum(x["brier_plus"] for x in rows) / n,
        "ll_base": sum(x["ll_base"] for x in rows) / n,
        "ll_plus": sum(x["ll_plus"] for x in rows) / n,
        "rank_base": sum(x["rank_base"] for x in rows) / n,
        "rank_plus": sum(x["rank_plus"] for x in rows) / n,
        "top1_base": sum(x["rank_base"] <= 1 for x in rows) / n,
        "top1_plus": sum(x["rank_plus"] <= 1 for x in rows) / n,
        "top3_base": sum(x["rank_base"] <= 3 for x in rows) / n,
        "top3_plus": sum(x["rank_plus"] <= 3 for x in rows) / n,
        "top5_base": sum(x["rank_base"] <= 5 for x in rows) / n,
        "top5_plus": sum(x["rank_plus"] <= 5 for x in rows) / n,
        "top10_base": sum(x["rank_base"] <= 10 for x in rows) / n,
        "top10_plus": sum(x["rank_plus"] <= 10 for x in rows) / n,
        "avg_abs_delta": sum(x["avg_abs_delta"] for x in rows) / n,
    }


def emit(label: str, m: dict[str, float]) -> None:
    print(
        f"OPP_V24_HEAD_DAILY={label} n:{int(m['n'])} "
        f"brier_delta:{m['brier_plus']-m['brier_base']:+.8f} "
        f"logloss_delta:{m['ll_plus']-m['ll_base']:+.8f} "
        f"rank_delta:{m['rank_plus']-m['rank_base']:+.3f} "
        f"top1:{m['top1_base']*100:.2f}%->{m['top1_plus']*100:.2f}% "
        f"top3:{m['top3_base']*100:.2f}%->{m['top3_plus']*100:.2f}% "
        f"top5:{m['top5_base']*100:.2f}%->{m['top5_plus']*100:.2f}% "
        f"top10:{m['top10_base']*100:.2f}%->{m['top10_plus']*100:.2f}% "
        f"avg_abs_pressure_delta:{m['avg_abs_delta']:.6f}",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_V24_HEAD_DAILY_MODE=read_only_forward_date_decomposition_no_tuning", flush=True)
    print(f"OPP_V24_HEAD_DAILY_PERIOD={START}..{END}", flush=True)
    print("OPP_V24_HEAD_DAILY_MAPPING=pressure_changes_first_place_only_second_third_conditionals_stay_v24", flush=True)
    print("OPP_V24_HEAD_DAILY_COEF=1.0_fixed", flush=True)
    print("OPP_V24_HEAD_DAILY_POLICY=no_date_selection_no_writes_no_production_no_line_no_threshold_search", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select s.race_id,s.race_date,s.model_version,s.train_end,
                       s.matched_opponents,s.base_win,s.adj_win,
                       r.first_lane,r.second_lane,r.third_lane,r.result_status,
                       q.venue_id,q.venue_code,q.race_no
                from v2_opponent_pressure_shadow_v2 s
                left join v2_results r on r.race_id=s.race_id
                left join v2_races q on q.race_id=s.race_id
                where s.race_date between %s and %s
                order by s.race_date,s.race_id
                """,
                (START, END),
            )
            shadows = [dict(x) for x in cur.fetchall()]
            ids = [str(x["race_id"]) for x in shadows]
            entries_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if ids:
                cur.execute(
                    """
                    select race_id,lane,racer_class,national_win_rate,national_place2_rate,
                           local_place2_rate,avg_st
                    from v2_race_entries
                    where race_id=any(%s)
                    order by race_id,lane
                    """,
                    (ids,),
                )
                for e in cur.fetchall():
                    d = dict(e)
                    entries_by_race[str(d["race_id"])].append(d)

    records: list[dict[str, Any]] = []
    pending = integrity_skip = missing_entries = 0
    for s in shadows:
        lanes = [naive.si(s.get(k), 0) for k in ("first_lane", "second_lane", "third_lane")]
        if str(s.get("result_status") or "") != "official" or any(x == 0 for x in lanes):
            pending += 1
            continue
        if len(set(lanes)) != 3 or any(not 1 <= x <= 6 for x in lanes):
            integrity_skip += 1
            continue
        if int(s.get("model_version") or 0) != 2 or s.get("train_end") >= s.get("race_date"):
            integrity_skip += 1
            continue
        if not isinstance(s.get("base_win"), list) or not isinstance(s.get("adj_win"), list):
            integrity_skip += 1
            continue
        if len(s["base_win"]) != 6 or len(s["adj_win"]) != 6:
            integrity_skip += 1
            continue
        if not isinstance(s.get("matched_opponents"), list) or len(s["matched_opponents"]) != 6 or any(int(x) < 4 for x in s["matched_opponents"]):
            integrity_skip += 1
            continue

        rid = str(s["race_id"])
        venue = str(s.get("venue_id") or s.get("venue_code") or "").zfill(2)
        base_lane = naive.lane_probs(entries_by_race.get(rid, []), venue)
        if base_lane is None:
            missing_entries += 1
            continue
        delta = [naive.sf(s["adj_win"][i]) - naive.sf(s["base_win"][i]) for i in range(6)]
        adjusted_first = naive.norm([
            max(1e-12, min(.999, base_lane[i] + UNIT_PRESSURE_COEF * delta[i]))
            for i in range(6)
        ])
        pb = naive.pl_trifecta(base_lane)
        ph = head.head_only_trifecta(base_lane, adjusted_first)
        ticket = f"{lanes[0]}-{lanes[1]}-{lanes[2]}"
        rb = naive.ticket_rank(pb, ticket)
        rh = naive.ticket_rank(ph, ticket)
        records.append({
            "race_date": str(s["race_date"]),
            "race_band": naive.race_band(naive.si(s.get("race_no"), 0)),
            "brier_base": sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in pb.items()),
            "brier_plus": sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in ph.items()),
            "ll_base": -math.log(max(EPS, pb.get(ticket, 0.0))),
            "ll_plus": -math.log(max(EPS, ph.get(ticket, 0.0))),
            "rank_base": float(rb),
            "rank_plus": float(rh),
            "avg_abs_delta": sum(abs(x) for x in delta) / 6.0,
        })

    print(
        f"OPP_V24_HEAD_DAILY_COVERAGE=shadow:{len(shadows)} evaluated:{len(records)} pending:{pending} "
        f"integrity_skip:{integrity_skip} missing_entries:{missing_entries}",
        flush=True,
    )
    emit("OVERALL", aggregate(records))
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_date_band: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_date[r["race_date"]].append(r)
        by_date_band[(r["race_date"], r["race_band"])].append(r)
    for d in sorted(by_date):
        emit(f"DATE:{d}", aggregate(by_date[d]))
        for band in ("R01_04", "R05_08", "R09_12"):
            rr = by_date_band.get((d, band), [])
            if rr:
                emit(f"DATE_BAND:{d}:{band}", aggregate(rr))

    print("OPP_V24_HEAD_DAILY_INTERPRETATION=DESCRIPTIVE_FORWARD_STABILITY_ONLY_NO_DATE_FILTER", flush=True)
    print("OPP_V24_HEAD_DAILY_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_V24_HEAD_DAILY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_V24_HEAD_DAILY_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
