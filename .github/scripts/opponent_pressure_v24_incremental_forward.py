# -*- coding: utf-8 -*-
"""Read-only realized Forward audit of Opponent Pressure incremental value over v24.

This is deliberately NOT a new fitted model.

For each already-frozen Opponent Pressure Shadow race:
1. reconstruct current v24 first-place lane probabilities from the unchanged
   v24 lane strength formula and PROB_TEMP;
2. take the frozen Opponent Pressure probability delta exactly as
   (adj_win - base_win);
3. add that delta with fixed coefficient 1.0 to v24 lane win probability;
4. clip positive and renormalize across six lanes;
5. compare v24 vs v24+Opponent Pressure on official realized winners.

No coefficient search/tuning, no subgroup selection, no DB writes, no
Production/LINE/Railway setting changes, and no promotion decision.
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

# The audit lives under .github/scripts while v24 is at repository root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import v24_pre_candidate_notifier_pg as v24

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat(os.getenv("OPP_V24_INCREMENTAL_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_V24_INCREMENTAL_END", date.today().isoformat()))
EPS = 1e-12
UNIT_PRESSURE_COEF = 1.0


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


def v24_lane_win_probs(entries: list[dict[str, Any]], venue: str) -> list[float] | None:
    by_lane = v24._entry_by_lane(entries)
    if sorted(by_lane) != [1, 2, 3, 4, 5, 6]:
        return None
    raw = {
        lane: v24._lane_raw_strength(by_lane[lane], lane, venue)
        for lane in range(1, 7)
    }
    weights = [math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)]
    return norm(weights)


def aggregate(records: list[dict[str, Any]]) -> dict[str, float]:
    n = len(records)
    if not n:
        return {k: 0.0 for k in (
            "n", "brier_v24", "brier_opp", "logloss_v24", "logloss_opp",
            "rank_v24", "rank_opp", "brier_improved", "logloss_improved",
            "rank_improved", "avg_abs_pressure_delta",
        )}
    return {
        "n": float(n),
        "brier_v24": sum(r["brier_v24"] for r in records) / n,
        "brier_opp": sum(r["brier_opp"] for r in records) / n,
        "logloss_v24": sum(r["logloss_v24"] for r in records) / n,
        "logloss_opp": sum(r["logloss_opp"] for r in records) / n,
        "rank_v24": sum(r["rank_v24"] for r in records) / n,
        "rank_opp": sum(r["rank_opp"] for r in records) / n,
        "brier_improved": sum(r["brier_opp"] < r["brier_v24"] for r in records) / n,
        "logloss_improved": sum(r["logloss_opp"] < r["logloss_v24"] for r in records) / n,
        "rank_improved": sum(r["rank_opp"] < r["rank_v24"] for r in records) / n,
        "avg_abs_pressure_delta": sum(r["avg_abs_pressure_delta"] for r in records) / n,
    }


def emit(prefix: str, m: dict[str, float]) -> None:
    print(
        f"{prefix}=n:{int(m['n'])} "
        f"winner_brier_v24:{m['brier_v24']:.8f} winner_brier_plus_opp:{m['brier_opp']:.8f} "
        f"brier_delta:{m['brier_opp']-m['brier_v24']:+.8f} "
        f"winner_logloss_v24:{m['logloss_v24']:.8f} winner_logloss_plus_opp:{m['logloss_opp']:.8f} "
        f"logloss_delta:{m['logloss_opp']-m['logloss_v24']:+.8f} "
        f"winner_rank_v24:{m['rank_v24']:.4f} winner_rank_plus_opp:{m['rank_opp']:.4f} "
        f"rank_delta:{m['rank_opp']-m['rank_v24']:+.4f} "
        f"brier_improved:{m['brier_improved']*100:.1f}% "
        f"logloss_improved:{m['logloss_improved']*100:.1f}% "
        f"rank_improved:{m['rank_improved']*100:.1f}% "
        f"avg_abs_pressure_delta:{m['avg_abs_pressure_delta']:.6f}",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    if END < START:
        raise RuntimeError("end before start")

    print("OPP_V24_INCREMENTAL_MODE=read_only_forward_no_tuning", flush=True)
    print(f"OPP_V24_INCREMENTAL_PERIOD={START}..{END}", flush=True)
    print("OPP_V24_INCREMENTAL_BASE=current_v24_lane_strength_fixed_motor33_boat34_prob_temp_2.20", flush=True)
    print("OPP_V24_INCREMENTAL_PRESSURE=frozen_adj_win_minus_base_win", flush=True)
    print(f"OPP_V24_INCREMENTAL_COEF={UNIT_PRESSURE_COEF:.1f}_fixed_unit_pressure_delta_no_tuning", flush=True)
    print("OPP_V24_INCREMENTAL_RESULT_SOURCE=v2_results_first_lane", flush=True)
    print("OPP_V24_INCREMENTAL_POLICY=no_writes_no_production_no_line_no_railway_change_no_threshold_search", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select s.race_id,s.race_date,s.model_version,s.train_end,
                       s.matched_opponents,s.base_win,s.adj_win,
                       r.first_lane,r.result_status,r.race_status,
                       q.venue_id,q.venue_code,q.race_no
                from v2_opponent_pressure_shadow_v2 s
                left join v2_results r on r.race_id=s.race_id
                left join v2_races q on q.race_id=s.race_id
                where s.race_date between %s and %s
                order by s.race_date,s.race_id
                """,
                (START, END),
            )
            shadows = [dict(r) for r in cur.fetchall()]

            race_ids = [str(r["race_id"]) for r in shadows]
            entries_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if race_ids:
                cur.execute(
                    """
                    select race_id,lane,racer_class,national_win_rate,national_place2_rate,
                           local_place2_rate,avg_st
                    from v2_race_entries
                    where race_id=any(%s)
                    order by race_id,lane
                    """,
                    (race_ids,),
                )
                for e in cur.fetchall():
                    d = dict(e)
                    entries_by_race[str(d["race_id"])].append(d)

    records: list[dict[str, Any]] = []
    pending = integrity_skip = missing_entries = 0
    for s in shadows:
        if str(s.get("result_status") or "") != "official" or s.get("first_lane") is None:
            pending += 1
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
        if not isinstance(s.get("matched_opponents"), list) or len(s["matched_opponents"]) != 6:
            integrity_skip += 1
            continue
        if any(int(x) < 4 for x in s["matched_opponents"]):
            integrity_skip += 1
            continue

        rid = str(s["race_id"])
        entries = entries_by_race.get(rid, [])
        venue = str(s.get("venue_id") or s.get("venue_code") or "").zfill(2)
        p_v24 = v24_lane_win_probs(entries, venue)
        if p_v24 is None:
            missing_entries += 1
            continue

        pressure_delta = [sf(s["adj_win"][i]) - sf(s["base_win"][i]) for i in range(6)]
        p_plus = norm([
            max(EPS, min(0.999, p_v24[i] + UNIT_PRESSURE_COEF * pressure_delta[i]))
            for i in range(6)
        ])
        winner_lane = si(s.get("first_lane"), 0)
        if not (1 <= winner_lane <= 6):
            integrity_skip += 1
            continue
        idx = winner_lane - 1
        y = [1.0 if i == idx else 0.0 for i in range(6)]
        rec = {
            "race_id": rid,
            "race_date": s["race_date"],
            "race_band": race_band(si(s.get("race_no"), 0)),
            "brier_v24": sum((y[i] - p_v24[i]) ** 2 for i in range(6)) / 6.0,
            "brier_opp": sum((y[i] - p_plus[i]) ** 2 for i in range(6)) / 6.0,
            "logloss_v24": -math.log(max(EPS, p_v24[idx])),
            "logloss_opp": -math.log(max(EPS, p_plus[idx])),
            "rank_v24": float(rank_desc(p_v24, idx)),
            "rank_opp": float(rank_desc(p_plus, idx)),
            "avg_abs_pressure_delta": sum(abs(x) for x in pressure_delta) / 6.0,
        }
        records.append(rec)

    print(
        f"OPP_V24_INCREMENTAL_COVERAGE=shadow:{len(shadows)} evaluated:{len(records)} "
        f"pending:{pending} integrity_skip:{integrity_skip} missing_entries:{missing_entries}",
        flush=True,
    )
    emit("OPP_V24_INCREMENTAL_OVERALL", aggregate(records))

    by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_band[r["race_band"]].append(r)
    for band in ("R01_04", "R05_08", "R09_12", "R_OTHER"):
        if by_band.get(band):
            emit(f"OPP_V24_INCREMENTAL_RACE_BAND={band}", aggregate(by_band[band]))

    overall = aggregate(records)
    brier_delta = overall["brier_opp"] - overall["brier_v24"]
    logloss_delta = overall["logloss_opp"] - overall["logloss_v24"]
    rank_delta = overall["rank_opp"] - overall["rank_v24"]
    better = sum(x < 0 for x in (brier_delta, logloss_delta, rank_delta))
    if records and better == 3:
        interpretation = "PROMISING_INCREMENTAL_FORWARD_RESEARCH_ONLY"
    elif records and better >= 1:
        interpretation = "MIXED_INCREMENTAL_FORWARD_KEEP_COLLECTING"
    elif records:
        interpretation = "NO_INCREMENTAL_FORWARD_SUPPORT_YET"
    else:
        interpretation = "NO_REALIZED_SAMPLE_YET"
    print(f"OPP_V24_INCREMENTAL_INTERPRETATION={interpretation}", flush=True)
    print("OPP_V24_INCREMENTAL_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_V24_INCREMENTAL_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_V24_INCREMENTAL_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
