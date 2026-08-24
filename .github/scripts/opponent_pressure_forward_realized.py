# -*- coding: utf-8 -*-
"""Read-only realized Forward evaluation for opponent-pressure Shadow v2.

Compares the stored train-only baseline probabilities with the stored
opponent-pressure adjusted probabilities on realized race outcomes.

Current production nightly results are stored one row per race in v2_results
(first_lane..sixth_lane), so this report reads that table directly.

Metrics:
- lane-level binary Brier for win and top3;
- normalized winner log loss (win probabilities normalized within race);
- realized winner probability rank;
- per-day paired summaries.

No DB writes, no Production/LINE/Railway setting changes.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat(os.getenv("OPP_PRESSURE_REALIZED_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_PRESSURE_REALIZED_END", date.today().isoformat()))
EPS = 1e-12


def _rank_desc(xs: list[float], idx: int) -> int:
    target = xs[idx]
    return 1 + sum(1 for j, x in enumerate(xs) if j != idx and x > target)


def _norm(xs: list[float]) -> list[float]:
    ys = [max(EPS, float(x)) for x in xs]
    s = sum(ys)
    if s <= 0:
        return [1.0 / len(ys)] * len(ys)
    return [x / s for x in ys]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _aggregate(records: list[dict[str, Any]]) -> dict[str, float]:
    n = len(records)
    if not n:
        return {
            "n": 0,
            "win_brier_base": 0.0,
            "win_brier_adj": 0.0,
            "top3_brier_base": 0.0,
            "top3_brier_adj": 0.0,
            "winner_logloss_base": 0.0,
            "winner_logloss_adj": 0.0,
            "winner_rank_base": 0.0,
            "winner_rank_adj": 0.0,
            "win_brier_improved_races": 0.0,
            "top3_brier_improved_races": 0.0,
            "logloss_improved_races": 0.0,
        }
    return {
        "n": float(n),
        "win_brier_base": _mean([r["win_brier_base"] for r in records]),
        "win_brier_adj": _mean([r["win_brier_adj"] for r in records]),
        "top3_brier_base": _mean([r["top3_brier_base"] for r in records]),
        "top3_brier_adj": _mean([r["top3_brier_adj"] for r in records]),
        "winner_logloss_base": _mean([r["winner_logloss_base"] for r in records]),
        "winner_logloss_adj": _mean([r["winner_logloss_adj"] for r in records]),
        "winner_rank_base": _mean([r["winner_rank_base"] for r in records]),
        "winner_rank_adj": _mean([r["winner_rank_adj"] for r in records]),
        "win_brier_improved_races": sum(r["win_brier_adj"] < r["win_brier_base"] for r in records) / n,
        "top3_brier_improved_races": sum(r["top3_brier_adj"] < r["top3_brier_base"] for r in records) / n,
        "logloss_improved_races": sum(r["winner_logloss_adj"] < r["winner_logloss_base"] for r in records) / n,
    }


def _print_metrics(prefix: str, m: dict[str, float]) -> None:
    n = int(m["n"])
    print(
        f"{prefix}=n:{n} "
        f"win_brier_base:{m['win_brier_base']:.8f} win_brier_adj:{m['win_brier_adj']:.8f} "
        f"win_delta:{m['win_brier_adj']-m['win_brier_base']:+.8f} "
        f"top3_brier_base:{m['top3_brier_base']:.8f} top3_brier_adj:{m['top3_brier_adj']:.8f} "
        f"top3_delta:{m['top3_brier_adj']-m['top3_brier_base']:+.8f} "
        f"winner_logloss_base:{m['winner_logloss_base']:.8f} winner_logloss_adj:{m['winner_logloss_adj']:.8f} "
        f"logloss_delta:{m['winner_logloss_adj']-m['winner_logloss_base']:+.8f} "
        f"winner_rank_base:{m['winner_rank_base']:.4f} winner_rank_adj:{m['winner_rank_adj']:.4f} "
        f"rank_delta:{m['winner_rank_adj']-m['winner_rank_base']:+.4f} "
        f"win_brier_improved:{m['win_brier_improved_races']*100:.1f}% "
        f"top3_brier_improved:{m['top3_brier_improved_races']*100:.1f}% "
        f"logloss_improved:{m['logloss_improved_races']*100:.1f}%",
        flush=True,
    )


def _finish_map(row: dict[str, Any]) -> dict[int, int]:
    out: dict[int, int] = {}
    for pos, key in enumerate(
        ("first_lane", "second_lane", "third_lane", "fourth_lane", "fifth_lane", "sixth_lane"),
        start=1,
    ):
        lane = row.get(key)
        if lane is None:
            continue
        lane_i = int(lane)
        if 1 <= lane_i <= 6 and lane_i not in out:
            out[lane_i] = pos
    return out


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    if END < START:
        raise RuntimeError("end before start")

    print("OPP_PRESSURE_REALIZED_MODE=read_only", flush=True)
    print(f"OPP_PRESSURE_REALIZED_PERIOD={START}..{END}", flush=True)
    print("OPP_PRESSURE_REALIZED_RESULT_SOURCE=v2_results_first_to_sixth_lane", flush=True)
    print("OPP_PRESSURE_REALIZED_POLICY=frozen_shadow_vs_realized_no_writes_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select race_id,race_date,model_version,train_end,
                       matched_opponents,base_win,base_top3,adj_win,adj_top3
                from v2_opponent_pressure_shadow_v2
                where race_date between %s and %s
                order by race_date,race_id
                """,
                (START, END),
            )
            shadows = [dict(r) for r in cur.fetchall()]

        ids = [str(r["race_id"]) for r in shadows]
        results: dict[str, dict[int, int]] = {}
        if ids:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select race_id,result_status,race_status,
                           first_lane,second_lane,third_lane,
                           fourth_lane,fifth_lane,sixth_lane
                    from v2_results
                    where race_id=any(%s)
                    order by race_id
                    """,
                    (ids,),
                )
                for row in cur.fetchall():
                    d = dict(row)
                    if str(d.get("result_status") or "") != "official":
                        continue
                    results[str(d["race_id"])] = _finish_map(d)

    print(f"OPP_PRESSURE_REALIZED_SHADOW_ROWS={len(shadows)}", flush=True)
    print(f"OPP_PRESSURE_REALIZED_RESULT_ROWS={len(results)}", flush=True)

    records: list[dict[str, Any]] = []
    pending = malformed = integrity_skip = 0
    for s in shadows:
        rid = str(s["race_id"])
        rr = results.get(rid, {})
        if len(rr) < 6:
            pending += 1
            continue
        if sorted(rr.keys()) != [1, 2, 3, 4, 5, 6] or sorted(rr.values()) != [1, 2, 3, 4, 5, 6]:
            malformed += 1
            continue
        arrays = [s[k] for k in ("matched_opponents", "base_win", "base_top3", "adj_win", "adj_top3")]
        if any(not isinstance(x, list) or len(x) != 6 for x in arrays):
            integrity_skip += 1
            continue
        if int(s["model_version"] or 0) != 2 or s["train_end"] >= s["race_date"]:
            integrity_skip += 1
            continue
        if any(int(x) < 4 for x in s["matched_opponents"]):
            integrity_skip += 1
            continue

        base_win = [float(x) for x in s["base_win"]]
        adj_win = [float(x) for x in s["adj_win"]]
        base_top3 = [float(x) for x in s["base_top3"]]
        adj_top3 = [float(x) for x in s["adj_top3"]]
        winner_lane = next(l for l, pos in rr.items() if pos == 1)
        winner_idx = winner_lane - 1
        y_win = [1.0 if rr[l] == 1 else 0.0 for l in range(1, 7)]
        y_top3 = [1.0 if rr[l] <= 3 else 0.0 for l in range(1, 7)]
        nb = _norm(base_win)
        na = _norm(adj_win)
        rec = {
            "race_id": rid,
            "race_date": s["race_date"],
            "win_brier_base": _mean([(y_win[i] - base_win[i]) ** 2 for i in range(6)]),
            "win_brier_adj": _mean([(y_win[i] - adj_win[i]) ** 2 for i in range(6)]),
            "top3_brier_base": _mean([(y_top3[i] - base_top3[i]) ** 2 for i in range(6)]),
            "top3_brier_adj": _mean([(y_top3[i] - adj_top3[i]) ** 2 for i in range(6)]),
            "winner_logloss_base": -math.log(max(EPS, nb[winner_idx])),
            "winner_logloss_adj": -math.log(max(EPS, na[winner_idx])),
            "winner_rank_base": float(_rank_desc(base_win, winner_idx)),
            "winner_rank_adj": float(_rank_desc(adj_win, winner_idx)),
        }
        records.append(rec)

    print(
        f"OPP_PRESSURE_REALIZED_COVERAGE=evaluated:{len(records)} pending:{pending} malformed:{malformed} integrity_skip:{integrity_skip}",
        flush=True,
    )

    by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_day[r["race_date"]].append(r)
    for d in sorted(by_day):
        _print_metrics(f"OPP_PRESSURE_REALIZED_DAY={d}", _aggregate(by_day[d]))

    overall = _aggregate(records)
    _print_metrics("OPP_PRESSURE_REALIZED_OVERALL", overall)

    if records:
        deltas = (
            overall["win_brier_adj"] - overall["win_brier_base"],
            overall["top3_brier_adj"] - overall["top3_brier_base"],
            overall["winner_logloss_adj"] - overall["winner_logloss_base"],
            overall["winner_rank_adj"] - overall["winner_rank_base"],
        )
        better = sum(x < 0 for x in deltas)
        if better == 4:
            decision = "PROMISING_FORWARD_RESEARCH_ONLY"
        elif better >= 2:
            decision = "MIXED_FORWARD_KEEP_COLLECTING"
        else:
            decision = "NO_FORWARD_SUPPORT_YET"
    else:
        decision = "NO_REALIZED_SAMPLE_YET"
    print(f"OPP_PRESSURE_REALIZED_INTERPRETATION={decision}", flush=True)
    print("OPP_PRESSURE_REALIZED_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_PRESSURE_REALIZED_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_PRESSURE_REALIZED_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
