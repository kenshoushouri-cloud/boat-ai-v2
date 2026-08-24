# -*- coding: utf-8 -*-
"""Read-only Forward audit: apply Opponent Pressure only to trifecta first place.

Evidence so far supports Opponent Pressure as an incremental first-place signal,
while applying the same adjusted lane weights to all Plackett-Luce stages hurts
realized ticket ranking. This fixed alternative therefore changes only P(first):

P(a,b,c) = P_opp_first(a) * P_v24(b | a) * P_v24(c | a,b)

The second/third conditional probabilities remain exactly current v24. The
pressure coefficient remains fixed at 1.0. No tuning, DB writes, Production/LINE
changes, threshold search, or promotion.
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

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat(os.getenv("OPP_V24_HEAD_TRI_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_V24_HEAD_TRI_END", date.today().isoformat()))
UNIT_PRESSURE_COEF = 1.0
EPS = 1e-15


def head_only_trifecta(base_lane: list[float], adjusted_first: list[float]) -> dict[str, float]:
    """Use adjusted P(first), but preserve base v24 conditional P(second/third)."""
    if len(base_lane) != 6 or len(adjusted_first) != 6:
        raise ValueError("six lane probabilities required")
    w = {lane: max(EPS, float(base_lane[lane - 1])) for lane in range(1, 7)}
    first = naive.norm(adjusted_first)
    total = sum(w.values())
    out: dict[str, float] = {}
    for a in range(1, 7):
        pa = first[a - 1]
        tb = total - w[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = w[b] / tb
            tc = tb - w[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * (w[c] / tc)
    return out


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_V24_HEAD_TRI_MODE=read_only_forward_first_place_only_no_tuning", flush=True)
    print(f"OPP_V24_HEAD_TRI_PERIOD={START}..{END}", flush=True)
    print("OPP_V24_HEAD_TRI_BASE=current_v24_plackett_luce_fixed_motor33_boat34_prob_temp_2.20", flush=True)
    print("OPP_V24_HEAD_TRI_MAPPING=pressure_changes_first_place_only_second_third_conditionals_stay_v24", flush=True)
    print(f"OPP_V24_HEAD_TRI_COEF={UNIT_PRESSURE_COEF:.1f}_fixed", flush=True)
    print("OPP_V24_HEAD_TRI_RESULT_SOURCE=v2_results_first_second_third_lane", flush=True)
    print("OPP_V24_HEAD_TRI_POLICY=no_writes_no_production_no_line_no_threshold_search", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select s.race_id,s.race_date,s.model_version,s.train_end,
                       s.matched_opponents,s.base_win,s.adj_win,
                       r.first_lane,r.second_lane,r.third_lane,r.result_status,r.race_status,
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
        ph = head_only_trifecta(base_lane, adjusted_first)
        ticket = f"{lanes[0]}-{lanes[1]}-{lanes[2]}"
        rb = naive.ticket_rank(pb, ticket)
        rh = naive.ticket_rank(ph, ticket)
        records.append({
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
        f"OPP_V24_HEAD_TRI_COVERAGE=shadow:{len(shadows)} evaluated:{len(records)} pending:{pending} "
        f"integrity_skip:{integrity_skip} missing_entries:{missing_entries}",
        flush=True,
    )
    overall = naive.aggregate(records)
    naive.emit("OPP_V24_HEAD_TRI_OVERALL", overall)
    by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_band[r["race_band"]].append(r)
    for band in ("R01_04", "R05_08", "R09_12", "R_OTHER"):
        if by_band.get(band):
            naive.emit(f"OPP_V24_HEAD_TRI_RACE_BAND={band}", naive.aggregate(by_band[band]))

    deltas = (
        overall["brier_plus"] - overall["brier_base"],
        overall["ll_plus"] - overall["ll_base"],
        overall["rank_plus"] - overall["rank_base"],
    )
    if records and all(x < 0 for x in deltas):
        interpretation = "PROMISING_HEAD_ONLY_TRIFECTA_FORWARD_RESEARCH_ONLY"
    elif records and sum(x < 0 for x in deltas) >= 1:
        interpretation = "MIXED_HEAD_ONLY_TRIFECTA_FORWARD_KEEP_COLLECTING"
    elif records:
        interpretation = "NO_HEAD_ONLY_TRIFECTA_FORWARD_SUPPORT_YET"
    else:
        interpretation = "NO_REALIZED_SAMPLE_YET"
    print(f"OPP_V24_HEAD_TRI_INTERPRETATION={interpretation}", flush=True)
    print("OPP_V24_HEAD_TRI_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_V24_HEAD_TRI_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_V24_HEAD_TRI_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
