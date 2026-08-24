# -*- coding: utf-8 -*-
"""Read-only historical OOS composition cross-check for R05-08 Opponent Pressure.

Purpose: compare the lane-wise effect geometry seen in recent Forward R05-08
with the same fixed historical OOS design. This is descriptive only and must not
be used for coefficient tuning or subgroup selection.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

import opponent_pressure_v24_incremental_oos as oos

DB = oos.DB
EPS = 1e-12


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def rank_desc(xs: list[float], idx: int) -> int:
    return 1 + sum(1 for j, x in enumerate(xs) if j != idx and x > xs[idx])


def build_r0508(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if 5 <= int(row.get("race_no") or 0) <= 8:
            by_race[str(row["race_id"])].append(row)

    records: list[dict[str, Any]] = []
    incomplete = 0
    for rid, rr in by_race.items():
        rr = sorted(rr, key=lambda x: int(x["lane"]))
        if len(rr) != 6 or [int(x["lane"]) for x in rr] != [1,2,3,4,5,6]:
            incomplete += 1
            continue
        winners = [i for i,x in enumerate(rr) if int(x["finish_position"]) == 1]
        if len(winners) != 1:
            incomplete += 1
            continue
        idx = winners[0]
        venue = str(rr[0].get("venue") or "").zfill(2)
        base = oos.v24_probs(rr, venue)
        if base is None:
            incomplete += 1
            continue
        delta = [oos.sf(x.get("pressure_delta")) for x in rr]
        adj = oos.norm([max(EPS, min(.999, base[i] + delta[i])) for i in range(6)])
        norm_change = [adj[i]-base[i] for i in range(6)]
        records.append({
            "winner_lane": idx+1,
            "winner_raw_delta": delta[idx],
            "winner_raw_is_max": delta[idx] >= max(delta)-1e-15,
            "winner_norm_change": norm_change[idx],
            "winner_base_p": base[idx],
            "winner_adj_p": adj[idx],
            "winner_rank_base": float(rank_desc(base,idx)),
            "winner_rank_adj": float(rank_desc(adj,idx)),
            "raw_delta_sum": sum(delta),
            "lane_raw_delta": delta,
            "lane_norm_change": norm_change,
            "a1_count": float(sum(1 for x in rr if int(x.get("racer_class") or 0)==4)),
        })
    return records, incomplete


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    n=len(records)
    lanes=Counter(int(x["winner_lane"]) for x in records)
    return {
        "n":n,
        "raw_delta_sum":mean([x["raw_delta_sum"] for x in records]),
        "winner_raw_delta":mean([x["winner_raw_delta"] for x in records]),
        "winner_raw_positive":mean([1.0 if x["winner_raw_delta"]>0 else 0.0 for x in records]),
        "winner_raw_is_max":mean([1.0 if x["winner_raw_is_max"] else 0.0 for x in records]),
        "winner_norm_change":mean([x["winner_norm_change"] for x in records]),
        "winner_norm_positive":mean([1.0 if x["winner_norm_change"]>0 else 0.0 for x in records]),
        "winner_base_p":mean([x["winner_base_p"] for x in records]),
        "winner_adj_p":mean([x["winner_adj_p"] for x in records]),
        "winner_rank_base":mean([x["winner_rank_base"] for x in records]),
        "winner_rank_adj":mean([x["winner_rank_adj"] for x in records]),
        "lane_raw_delta":[mean([x["lane_raw_delta"][i] for x in records]) for i in range(6)],
        "lane_norm_change":[mean([x["lane_norm_change"][i] for x in records]) for i in range(6)],
        "a1_count":mean([x["a1_count"] for x in records]),
        "winner_lanes":lanes,
    }


def emit(split: Any, m: dict[str, Any]) -> None:
    raw_lane=",".join(f"{i+1}:{m['lane_raw_delta'][i]:+.5f}" for i in range(6))
    norm_lane=",".join(f"{i+1}:{m['lane_norm_change'][i]:+.5f}" for i in range(6))
    winner_lanes=",".join(f"{i}:{m['winner_lanes'].get(i,0)}" for i in range(1,7))
    print(
        f"OPP_R0508_OOS_COMP={split} n:{m['n']} raw_delta_sum:{m['raw_delta_sum']:+.6f} "
        f"winner_raw_delta:{m['winner_raw_delta']:+.6f} winner_raw_positive:{m['winner_raw_positive']*100:.1f}% "
        f"winner_raw_is_max:{m['winner_raw_is_max']*100:.1f}% "
        f"winner_norm_change:{m['winner_norm_change']:+.6f} winner_norm_positive:{m['winner_norm_positive']*100:.1f}% "
        f"winner_first_p:{m['winner_base_p']:.4f}->{m['winner_adj_p']:.4f} "
        f"winner_first_rank:{m['winner_rank_base']:.3f}->{m['winner_rank_adj']:.3f} "
        f"raw_lane_delta:{raw_lane} norm_lane_change:{norm_lane} "
        f"a1_count:{m['a1_count']:.2f} winner_lanes:{winner_lanes}",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_R0508_OOS_COMP_MODE=read_only_historical_composition_crosscheck_no_tuning", flush=True)
    print(f"OPP_R0508_OOS_COMP_PERIOD={oos.START}..{oos.END}", flush=True)
    print("OPP_R0508_OOS_COMP_SPLITS=2026-03-31,2026-04-30,2026-05-31", flush=True)
    print(f"OPP_R0508_OOS_COMP_GATES=train_cond>={oos.TRAIN_COND_MIN},train_base>={oos.TRAIN_BASE_MIN},shrink_k={oos.SHRINK_K}", flush=True)
    print("OPP_R0508_OOS_COMP_POLICY=R05_08_descriptive_only_no_subgroup_selection_no_coefficient_search_no_writes_no_production_no_line", flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='240s'")
        for split in oos.SPLITS:
            rows=oos.fetch_scored(conn,split)
            records,incomplete=build_r0508(rows)
            print(f"OPP_R0508_OOS_COMP_COVERAGE={split}=lane_rows:{len(rows)} r0508:{len(records)} incomplete:{incomplete}",flush=True)
            emit(split,summarize(records))
    print("OPP_R0508_OOS_COMP_INTERPRETATION=HISTORICAL_GEOMETRY_CROSSCHECK_ONLY",flush=True)
    print("OPP_R0508_OOS_COMP_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE",flush=True)
    print("OPP_R0508_OOS_COMP_RESULT=PASS_READ_ONLY",flush=True)

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        msg=str(exc).replace("\n"," ").replace("\r"," ")[:700]
        print(f"OPP_R0508_OOS_COMP_ERROR={type(exc).__name__}:{msg}",flush=True)
        raise
