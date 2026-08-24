# -*- coding: utf-8 -*-
"""Read-only realized Forward audit of Opponent Pressure on v24 trifecta probabilities.

Fixed integration only:
- reconstruct current v24 lane weights / first-place probabilities;
- add frozen Opponent Pressure (adj_win-base_win) with coefficient 1.0;
- renormalize six lane weights;
- feed those weights into the same Plackett-Luce ordered-finish construction;
- compare all 120 trifecta probabilities to official first/second/third lanes.

No coefficient search, DB writes, Production/LINE changes, threshold tuning, or promotion.
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
START = date.fromisoformat(os.getenv("OPP_V24_TRI_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_V24_TRI_END", date.today().isoformat()))
UNIT_PRESSURE_COEF = 1.0
EPS = 1e-15


def sf(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except Exception:
        return default


def si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def norm(xs: list[float]) -> list[float]:
    ys = [max(1e-12, float(x)) for x in xs]
    s = sum(ys)
    return [x / s for x in ys]


def race_band(race_no: int) -> str:
    if 1 <= race_no <= 4:
        return "R01_04"
    if 5 <= race_no <= 8:
        return "R05_08"
    if 9 <= race_no <= 12:
        return "R09_12"
    return "R_OTHER"


def lane_probs(entries: list[dict[str, Any]], venue: str) -> list[float] | None:
    by = v24._entry_by_lane(entries)
    if sorted(by) != [1, 2, 3, 4, 5, 6]:
        return None
    raw = {lane: v24._lane_raw_strength(by[lane], lane, venue) for lane in range(1, 7)}
    return norm([math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)])


def pl_trifecta(weights: list[float]) -> dict[str, float]:
    if len(weights) != 6:
        raise ValueError("six weights required")
    w = {lane: max(EPS, float(weights[lane - 1])) for lane in range(1, 7)}
    total = sum(w.values())
    out: dict[str, float] = {}
    for a in range(1, 7):
        pa = w[a] / total
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


def ticket_rank(probs: dict[str, float], ticket: str) -> int:
    target = probs.get(ticket, -1.0)
    return 1 + sum(1 for t, p in probs.items() if t != ticket and p > target)


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


def emit(prefix: str, m: dict[str, float]) -> None:
    print(
        f"{prefix}=n:{int(m['n'])} "
        f"brier120_v24:{m['brier_base']:.8f} brier120_plus_opp:{m['brier_plus']:.8f} "
        f"brier_delta:{m['brier_plus']-m['brier_base']:+.8f} "
        f"winner_logloss_v24:{m['ll_base']:.8f} winner_logloss_plus_opp:{m['ll_plus']:.8f} "
        f"logloss_delta:{m['ll_plus']-m['ll_base']:+.8f} "
        f"winner_ticket_rank_v24:{m['rank_base']:.3f} winner_ticket_rank_plus_opp:{m['rank_plus']:.3f} "
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
    print("OPP_V24_TRI_MODE=read_only_forward_fixed_unit_no_tuning", flush=True)
    print(f"OPP_V24_TRI_PERIOD={START}..{END}", flush=True)
    print("OPP_V24_TRI_BASE=current_v24_plackett_luce_fixed_motor33_boat34_prob_temp_2.20", flush=True)
    print("OPP_V24_TRI_PRESSURE=frozen_adj_win_minus_base_win_then_same_plackett_luce", flush=True)
    print(f"OPP_V24_TRI_COEF={UNIT_PRESSURE_COEF:.1f}_fixed", flush=True)
    print("OPP_V24_TRI_RESULT_SOURCE=v2_results_first_second_third_lane", flush=True)
    print("OPP_V24_TRI_POLICY=no_writes_no_production_no_line_no_threshold_search", flush=True)

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
            eb: dict[str, list[dict[str, Any]]] = defaultdict(list)
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
                    eb[str(d["race_id"])].append(d)

    records: list[dict[str, Any]] = []
    pending = integrity_skip = missing_entries = 0
    for s in shadows:
        lanes = [si(s.get(k), 0) for k in ("first_lane", "second_lane", "third_lane")]
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
        p_lane = lane_probs(eb.get(rid, []), venue)
        if p_lane is None:
            missing_entries += 1
            continue
        delta = [sf(s["adj_win"][i]) - sf(s["base_win"][i]) for i in range(6)]
        p_plus_lane = norm([max(1e-12, min(.999, p_lane[i] + delta[i])) for i in range(6)])
        pb = pl_trifecta(p_lane)
        pp = pl_trifecta(p_plus_lane)
        ticket = f"{lanes[0]}-{lanes[1]}-{lanes[2]}"
        rb = ticket_rank(pb, ticket)
        rp = ticket_rank(pp, ticket)
        brier_b = sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in pb.items())
        brier_p = sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in pp.items())
        records.append({
            "race_band": race_band(si(s.get("race_no"), 0)),
            "brier_base": brier_b,
            "brier_plus": brier_p,
            "ll_base": -math.log(max(EPS, pb.get(ticket, 0.0))),
            "ll_plus": -math.log(max(EPS, pp.get(ticket, 0.0))),
            "rank_base": float(rb),
            "rank_plus": float(rp),
            "avg_abs_delta": sum(abs(x) for x in delta) / 6.0,
        })

    print(
        f"OPP_V24_TRI_COVERAGE=shadow:{len(shadows)} evaluated:{len(records)} pending:{pending} "
        f"integrity_skip:{integrity_skip} missing_entries:{missing_entries}",
        flush=True,
    )
    overall = aggregate(records)
    emit("OPP_V24_TRI_OVERALL", overall)
    by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_band[r["race_band"]].append(r)
    for band in ("R01_04", "R05_08", "R09_12", "R_OTHER"):
        if by_band.get(band):
            emit(f"OPP_V24_TRI_RACE_BAND={band}", aggregate(by_band[band]))

    deltas = (
        overall["brier_plus"] - overall["brier_base"],
        overall["ll_plus"] - overall["ll_base"],
        overall["rank_plus"] - overall["rank_base"],
    )
    if records and all(x < 0 for x in deltas):
        interpretation = "PROMISING_TRIFECTA_INCREMENTAL_FORWARD_RESEARCH_ONLY"
    elif records and sum(x < 0 for x in deltas) >= 1:
        interpretation = "MIXED_TRIFECTA_INCREMENTAL_FORWARD_KEEP_COLLECTING"
    elif records:
        interpretation = "NO_TRIFECTA_INCREMENTAL_FORWARD_SUPPORT_YET"
    else:
        interpretation = "NO_REALIZED_SAMPLE_YET"
    print(f"OPP_V24_TRI_INTERPRETATION={interpretation}", flush=True)
    print("OPP_V24_TRI_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_V24_TRI_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_V24_TRI_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
