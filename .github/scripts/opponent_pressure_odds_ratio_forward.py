# -*- coding: utf-8 -*-
"""Read-only Forward audit of a fixed log-odds transfer for Opponent Pressure.

The Opponent Pressure model estimates a marginal binary win probability before
and after opponent effects (`base_win` -> `adj_win`).  Instead of transporting
that effect into v24 as an absolute probability difference, this audit transports
the fixed binary log-odds shift:

  shift_i = logit(adj_win_i) - logit(base_win_i)
  q_i     = logistic(logit(v24_first_i) + shift_i)
  p_i     = normalize(q_1..q_6)

Only first-place probabilities change.  v24 second/third conditional
probabilities stay unchanged.  There is no fitted coefficient, search, subgroup
selection, or Production mutation.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

import opponent_pressure_v24_trifecta_forward as tri
import opponent_pressure_v24_trifecta_head_only_forward as head

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat(os.getenv("OPP_OR_FORWARD_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_OR_FORWARD_END", "2026-08-24"))
EPS = 1e-9


def clip01(x: float) -> float:
    return max(EPS, min(1.0 - EPS, float(x)))


def logit(x: float) -> float:
    x = clip01(x)
    return math.log(x / (1.0 - x))


def logistic(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def additive_first(v24_p: list[float], base_win: list[Any], adj_win: list[Any]) -> list[float]:
    delta = [tri.sf(adj_win[i]) - tri.sf(base_win[i]) for i in range(6)]
    return tri.norm([max(EPS, min(1.0 - EPS, v24_p[i] + delta[i])) for i in range(6)])


def odds_ratio_first(v24_p: list[float], base_win: list[Any], adj_win: list[Any]) -> list[float]:
    shifted: list[float] = []
    for i in range(6):
        shift = logit(tri.sf(adj_win[i])) - logit(tri.sf(base_win[i]))
        shifted.append(logistic(logit(v24_p[i]) + shift))
    return tri.norm(shifted)


def first_rank(ps: list[float], idx: int) -> int:
    return 1 + sum(1 for j, p in enumerate(ps) if j != idx and p > ps[idx])


def race_band(race_no: int) -> str:
    if 1 <= race_no <= 4:
        return "R01_04"
    if 5 <= race_no <= 8:
        return "R05_08"
    if 9 <= race_no <= 12:
        return "R09_12"
    return "R_OTHER"


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    keys = (
        "first_brier_base", "first_brier_add", "first_brier_or",
        "first_ll_base", "first_ll_add", "first_ll_or",
        "first_rank_base", "first_rank_add", "first_rank_or",
        "tri_brier_base", "tri_brier_add", "tri_brier_or",
        "tri_ll_base", "tri_ll_add", "tri_ll_or",
        "tri_rank_base", "tri_rank_add", "tri_rank_or",
    )
    out = {"n": float(n)}
    for key in keys:
        out[key] = sum(r[key] for r in rows) / n if n else 0.0
    for k in (1, 3, 5, 10):
        for mode in ("base", "add", "or"):
            out[f"top{k}_{mode}"] = sum(r[f"tri_rank_{mode}"] <= k for r in rows) / n if n else 0.0
    return out


def emit(label: str, m: dict[str, float]) -> None:
    print(
        f"OPP_OR_FORWARD={label} n:{int(m['n'])} "
        f"first_brier base:{m['first_brier_base']:.8f} add:{m['first_brier_add']:.8f} or:{m['first_brier_or']:.8f} "
        f"or_delta:{m['first_brier_or']-m['first_brier_base']:+.8f} "
        f"first_logloss base:{m['first_ll_base']:.8f} add:{m['first_ll_add']:.8f} or:{m['first_ll_or']:.8f} "
        f"or_delta:{m['first_ll_or']-m['first_ll_base']:+.8f} "
        f"first_rank base:{m['first_rank_base']:.3f} add:{m['first_rank_add']:.3f} or:{m['first_rank_or']:.3f} "
        f"or_delta:{m['first_rank_or']-m['first_rank_base']:+.3f} "
        f"tri_brier base:{m['tri_brier_base']:.8f} add:{m['tri_brier_add']:.8f} or:{m['tri_brier_or']:.8f} "
        f"or_delta:{m['tri_brier_or']-m['tri_brier_base']:+.8f} "
        f"tri_logloss base:{m['tri_ll_base']:.8f} add:{m['tri_ll_add']:.8f} or:{m['tri_ll_or']:.8f} "
        f"or_delta:{m['tri_ll_or']-m['tri_ll_base']:+.8f} "
        f"tri_rank base:{m['tri_rank_base']:.3f} add:{m['tri_rank_add']:.3f} or:{m['tri_rank_or']:.3f} "
        f"or_delta:{m['tri_rank_or']-m['tri_rank_base']:+.3f} "
        f"top1:{m['top1_base']*100:.2f}%/{m['top1_add']*100:.2f}%/{m['top1_or']*100:.2f}% "
        f"top3:{m['top3_base']*100:.2f}%/{m['top3_add']*100:.2f}%/{m['top3_or']*100:.2f}% "
        f"top5:{m['top5_base']*100:.2f}%/{m['top5_add']*100:.2f}%/{m['top5_or']*100:.2f}% "
        f"top10:{m['top10_base']*100:.2f}%/{m['top10_add']*100:.2f}%/{m['top10_or']*100:.2f}%",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_OR_FORWARD_MODE=read_only_fixed_log_odds_transfer_no_tuning", flush=True)
    print(f"OPP_OR_FORWARD_PERIOD={START}..{END}", flush=True)
    print("OPP_OR_FORWARD_MAPPING=logit_v24_plus_logit_adj_minus_logit_base_then_normalize_first_place_only", flush=True)
    print("OPP_OR_FORWARD_REFERENCE=base_v24_and_existing_absolute_delta_head_only", flush=True)
    print("OPP_OR_FORWARD_POLICY=no_coefficient_no_search_no_subgroup_selection_no_writes_no_production_no_line", flush=True)

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
                    from v2_race_entries where race_id=any(%s) order by race_id,lane
                    """,
                    (ids,),
                )
                for e in cur.fetchall():
                    d = dict(e)
                    entries_by_race[str(d["race_id"])].append(d)

    records: list[dict[str, Any]] = []
    skipped = 0
    for s in shadows:
        finish = [tri.si(s.get(k), 0) for k in ("first_lane", "second_lane", "third_lane")]
        if str(s.get("result_status") or "") != "official" or any(not 1 <= x <= 6 for x in finish) or len(set(finish)) != 3:
            skipped += 1
            continue
        if int(s.get("model_version") or 0) != 2 or s.get("train_end") >= s.get("race_date"):
            skipped += 1
            continue
        if not isinstance(s.get("base_win"), list) or not isinstance(s.get("adj_win"), list) or len(s["base_win"]) != 6 or len(s["adj_win"]) != 6:
            skipped += 1
            continue
        supports = s.get("matched_opponents")
        if not isinstance(supports, list) or len(supports) != 6 or any(int(x) < 4 for x in supports):
            skipped += 1
            continue
        rid = str(s["race_id"])
        venue = str(s.get("venue_id") or s.get("venue_code") or "").zfill(2)
        p0 = tri.lane_probs(entries_by_race.get(rid, []), venue)
        if p0 is None:
            skipped += 1
            continue
        padd = additive_first(p0, s["base_win"], s["adj_win"])
        por = odds_ratio_first(p0, s["base_win"], s["adj_win"])
        idx = finish[0] - 1
        y = [1.0 if i == idx else 0.0 for i in range(6)]
        tb = tri.pl_trifecta(p0)
        ta = head.head_only_trifecta(p0, padd)
        tor = head.head_only_trifecta(p0, por)
        ticket = f"{finish[0]}-{finish[1]}-{finish[2]}"
        rec: dict[str, Any] = {
            "race_date": str(s["race_date"]),
            "race_band": race_band(tri.si(s.get("race_no"), 0)),
        }
        for mode, ps in (("base", p0), ("add", padd), ("or", por)):
            rec[f"first_brier_{mode}"] = sum((y[i] - ps[i]) ** 2 for i in range(6)) / 6.0
            rec[f"first_ll_{mode}"] = -math.log(max(EPS, ps[idx]))
            rec[f"first_rank_{mode}"] = float(first_rank(ps, idx))
        for mode, probs in (("base", tb), ("add", ta), ("or", tor)):
            rec[f"tri_brier_{mode}"] = sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in probs.items())
            rec[f"tri_ll_{mode}"] = -math.log(max(EPS, probs.get(ticket, 0.0)))
            rec[f"tri_rank_{mode}"] = float(tri.ticket_rank(probs, ticket))
        records.append(rec)

    print(f"OPP_OR_FORWARD_COVERAGE=shadow:{len(shadows)} evaluated:{len(records)} skipped:{skipped}", flush=True)
    emit("OVERALL", aggregate(records))
    by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_band[r["race_band"]].append(r)
        by_date[r["race_date"]].append(r)
    for band in ("R01_04", "R05_08", "R09_12"):
        if by_band.get(band):
            emit(f"RACE_BAND:{band}", aggregate(by_band[band]))
    for d in sorted(by_date):
        emit(f"DATE:{d}", aggregate(by_date[d]))

    overall = aggregate(records)
    core = (
        overall["first_brier_or"] - overall["first_brier_base"],
        overall["first_ll_or"] - overall["first_ll_base"],
        overall["tri_brier_or"] - overall["tri_brier_base"],
        overall["tri_ll_or"] - overall["tri_ll_base"],
        overall["tri_rank_or"] - overall["tri_rank_base"],
    )
    if records and all(x < 0 for x in core):
        interpretation = "PROMISING_FIXED_LOG_ODDS_FORWARD_RESEARCH_ONLY"
    elif records and sum(x < 0 for x in core) >= 3:
        interpretation = "MIXED_FIXED_LOG_ODDS_FORWARD_KEEP_RESEARCH_ONLY"
    elif records:
        interpretation = "NO_FIXED_LOG_ODDS_FORWARD_SUPPORT_YET"
    else:
        interpretation = "NO_REALIZED_SAMPLE"
    print(f"OPP_OR_FORWARD_INTERPRETATION={interpretation}", flush=True)
    print("OPP_OR_FORWARD_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_OR_FORWARD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_OR_FORWARD_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
