# -*- coding: utf-8 -*-
"""Read-only Forward audit of position-aware Opponent Pressure integration.

Pre-declared fixed mapping:
- first place: existing additive win effect, then normalize six lanes
- second/third conditionals: current v24 conditional weights multiplied by
  Opponent Pressure top3 relative risk `adj_top3 / base_top3`

This uses the two signals for the outcome they were estimated on instead of
reusing the win effect for every finish position.  No fitted coefficient,
threshold search, subgroup selection, or Production mutation.
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
START = date.fromisoformat(os.getenv("OPP_STAGE_FORWARD_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_STAGE_FORWARD_END", "2026-08-24"))
EPS = 1e-12


def first_additive(v24_p: list[float], base_win: list[Any], adj_win: list[Any]) -> list[float]:
    delta = [tri.sf(adj_win[i]) - tri.sf(base_win[i]) for i in range(6)]
    return tri.norm([max(EPS, min(.999999, v24_p[i] + delta[i])) for i in range(6)])


def top3_relative_risk(base_top3: list[Any], adj_top3: list[Any]) -> list[float]:
    out: list[float] = []
    for i in range(6):
        b = max(EPS, tri.sf(base_top3[i]))
        a = max(EPS, tri.sf(adj_top3[i]))
        out.append(a / b)
    return out


def stage_aware_trifecta(base_p: list[float], first_p: list[float], tail_rr: list[float]) -> dict[str, float]:
    probs: dict[str, float] = {}
    for a in range(6):
        rem_b = [j for j in range(6) if j != a]
        wb = {j: max(EPS, base_p[j] * tail_rr[j]) for j in rem_b}
        sb = sum(wb.values())
        for b in rem_b:
            pb = wb[b] / sb
            rem_c = [j for j in rem_b if j != b]
            wc = {j: max(EPS, base_p[j] * tail_rr[j]) for j in rem_c}
            sc = sum(wc.values())
            for c in rem_c:
                pc = wc[c] / sc
                probs[f"{a+1}-{b+1}-{c+1}"] = first_p[a] * pb * pc
    total = sum(probs.values())
    if total <= 0:
        raise RuntimeError("invalid stage-aware probability sum")
    return {k: v / total for k, v in probs.items()}


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
    out = {"n": float(n)}
    for key in (
        "brier_base", "brier_head", "brier_stage",
        "ll_base", "ll_head", "ll_stage",
        "rank_base", "rank_head", "rank_stage",
    ):
        out[key] = sum(r[key] for r in rows) / n if n else 0.0
    for k in (1, 3, 5, 10):
        for mode in ("base", "head", "stage"):
            out[f"top{k}_{mode}"] = sum(r[f"rank_{mode}"] <= k for r in rows) / n if n else 0.0
    return out


def emit(label: str, m: dict[str, float]) -> None:
    print(
        f"OPP_STAGE_FORWARD={label} n:{int(m['n'])} "
        f"brier base:{m['brier_base']:.8f} head:{m['brier_head']:.8f} stage:{m['brier_stage']:.8f} "
        f"stage_delta:{m['brier_stage']-m['brier_base']:+.8f} "
        f"logloss base:{m['ll_base']:.8f} head:{m['ll_head']:.8f} stage:{m['ll_stage']:.8f} "
        f"stage_delta:{m['ll_stage']-m['ll_base']:+.8f} "
        f"ticket_rank base:{m['rank_base']:.3f} head:{m['rank_head']:.3f} stage:{m['rank_stage']:.3f} "
        f"stage_delta:{m['rank_stage']-m['rank_base']:+.3f} "
        f"top1:{m['top1_base']*100:.2f}%/{m['top1_head']*100:.2f}%/{m['top1_stage']*100:.2f}% "
        f"top3:{m['top3_base']*100:.2f}%/{m['top3_head']*100:.2f}%/{m['top3_stage']*100:.2f}% "
        f"top5:{m['top5_base']*100:.2f}%/{m['top5_head']*100:.2f}%/{m['top5_stage']*100:.2f}% "
        f"top10:{m['top10_base']*100:.2f}%/{m['top10_head']*100:.2f}%/{m['top10_stage']*100:.2f}%",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_STAGE_FORWARD_MODE=read_only_fixed_position_aware_no_tuning", flush=True)
    print(f"OPP_STAGE_FORWARD_PERIOD={START}..{END}", flush=True)
    print("OPP_STAGE_FORWARD_MAPPING=first_additive_win_delta_second_third_v24_weights_times_top3_relative_risk", flush=True)
    print("OPP_STAGE_FORWARD_REFERENCE=base_v24_and_existing_additive_head_only", flush=True)
    print("OPP_STAGE_FORWARD_POLICY=no_coefficient_no_search_no_subgroup_selection_no_writes_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select s.race_id,s.race_date,s.model_version,s.train_end,s.matched_opponents,
                       s.base_win,s.adj_win,s.base_top3,s.adj_top3,
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

    rows: list[dict[str, Any]] = []
    skipped = 0
    for s in shadows:
        finish = [tri.si(s.get(k), 0) for k in ("first_lane", "second_lane", "third_lane")]
        if str(s.get("result_status") or "") != "official" or any(not 1 <= x <= 6 for x in finish) or len(set(finish)) != 3:
            skipped += 1; continue
        if int(s.get("model_version") or 0) != 2 or s.get("train_end") >= s.get("race_date"):
            skipped += 1; continue
        arrays = [s.get(k) for k in ("base_win", "adj_win", "base_top3", "adj_top3")]
        if any(not isinstance(a, list) or len(a) != 6 for a in arrays):
            skipped += 1; continue
        supports = s.get("matched_opponents")
        if not isinstance(supports, list) or len(supports) != 6 or any(int(x) < 4 for x in supports):
            skipped += 1; continue
        rid = str(s["race_id"])
        venue = str(s.get("venue_id") or s.get("venue_code") or "").zfill(2)
        p0 = tri.lane_probs(entries_by_race.get(rid, []), venue)
        if p0 is None:
            skipped += 1; continue
        pfirst = first_additive(p0, s["base_win"], s["adj_win"])
        rr = top3_relative_risk(s["base_top3"], s["adj_top3"])
        base_tri = tri.pl_trifecta(p0)
        head_tri = head.head_only_trifecta(p0, pfirst)
        stage_tri = stage_aware_trifecta(p0, pfirst, rr)
        ticket = f"{finish[0]}-{finish[1]}-{finish[2]}"
        rec: dict[str, Any] = {
            "race_date": str(s["race_date"]),
            "race_band": race_band(tri.si(s.get("race_no"), 0)),
        }
        for mode, probs in (("base", base_tri), ("head", head_tri), ("stage", stage_tri)):
            rec[f"brier_{mode}"] = sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in probs.items())
            rec[f"ll_{mode}"] = -math.log(max(EPS, probs.get(ticket, 0.0)))
            rec[f"rank_{mode}"] = float(tri.ticket_rank(probs, ticket))
        rows.append(rec)

    print(f"OPP_STAGE_FORWARD_COVERAGE=shadow:{len(shadows)} evaluated:{len(rows)} skipped:{skipped}", flush=True)
    emit("OVERALL", aggregate(rows))
    by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_band[r["race_band"]].append(r)
        by_date[r["race_date"]].append(r)
    for band in ("R01_04", "R05_08", "R09_12"):
        if by_band.get(band): emit(f"RACE_BAND:{band}", aggregate(by_band[band]))
    for d in sorted(by_date): emit(f"DATE:{d}", aggregate(by_date[d]))

    overall = aggregate(rows)
    deltas = (
        overall["brier_stage"] - overall["brier_base"],
        overall["ll_stage"] - overall["ll_base"],
        overall["rank_stage"] - overall["rank_base"],
    )
    if rows and all(x < 0 for x in deltas):
        interpretation = "PROMISING_POSITION_AWARE_FORWARD_RESEARCH_ONLY"
    elif rows and sum(x < 0 for x in deltas) >= 2:
        interpretation = "MIXED_POSITION_AWARE_FORWARD_KEEP_RESEARCH_ONLY"
    elif rows:
        interpretation = "NO_POSITION_AWARE_FORWARD_SUPPORT_YET"
    else:
        interpretation = "NO_REALIZED_SAMPLE"
    print(f"OPP_STAGE_FORWARD_INTERPRETATION={interpretation}", flush=True)
    print("OPP_STAGE_FORWARD_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_STAGE_FORWARD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_STAGE_FORWARD_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
