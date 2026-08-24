# -*- coding: utf-8 -*-
"""Read-only historical OOS audit of head-only Opponent Pressure trifecta mapping.

Fixed mapping:
P(a,b,c) = P_opp_first(a) * P_v24(b|a) * P_v24(c|a,b)

Opponent Pressure changes only first-place probability. Current v24 second/third
conditional probabilities are preserved. The pressure coefficient stays fixed at
1.0 and the historical Opponent Pressure design is reused unchanged.

No coefficient search, subgroup selection, DB writes, Production/LINE changes,
Railway setting changes, threshold tuning, or promotion.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

import opponent_pressure_v24_incremental_oos as lane_oos
import opponent_pressure_v24_trifecta_forward as tri_forward
import opponent_pressure_v24_trifecta_head_only_forward as head_forward
import opponent_pressure_v24_trifecta_oos as tri_oos

DB = os.getenv("DATABASE_URL", "").strip()
EPS = 1e-15
UNIT_PRESSURE_COEF = 1.0


def build_records(lane_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lane_rows:
        by_race[str(row["race_id"])].append(row)

    out: list[dict[str, Any]] = []
    incomplete = 0
    for rid, rr in by_race.items():
        rr = sorted(rr, key=lambda x: int(x["lane"]))
        if len(rr) != 6 or [int(x["lane"]) for x in rr] != [1, 2, 3, 4, 5, 6]:
            incomplete += 1
            continue
        pos_to_lane = {int(x["finish_position"]): int(x["lane"]) for x in rr}
        if sorted(pos_to_lane) != [1, 2, 3, 4, 5, 6]:
            incomplete += 1
            continue

        venue = str(rr[0].get("venue") or "").zfill(2)
        base_lane = lane_oos.v24_probs(rr, venue)
        if base_lane is None:
            incomplete += 1
            continue
        delta = [lane_oos.sf(x.get("pressure_delta")) for x in rr]
        adjusted_first = tri_forward.norm([
            max(1e-12, min(.999, base_lane[i] + UNIT_PRESSURE_COEF * delta[i]))
            for i in range(6)
        ])

        pb = tri_forward.pl_trifecta(base_lane)
        ph = head_forward.head_only_trifecta(base_lane, adjusted_first)
        ticket = f"{pos_to_lane[1]}-{pos_to_lane[2]}-{pos_to_lane[3]}"
        rb = tri_forward.ticket_rank(pb, ticket)
        rh = tri_forward.ticket_rank(ph, ticket)
        out.append({
            "venue": venue,
            "race_band": lane_oos.race_band(int(rr[0].get("race_no") or 0)),
            "brier_base": sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in pb.items()),
            "brier_plus": sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in ph.items()),
            "ll_base": -math.log(max(EPS, pb.get(ticket, 0.0))),
            "ll_plus": -math.log(max(EPS, ph.get(ticket, 0.0))),
            "rank_base": float(rb),
            "rank_plus": float(rh),
        })
    return out, incomplete


def emit(split: Any, label: str, m: dict[str, float]) -> None:
    print(
        f"OPP_V24_HEAD_TRI_OOS={split}|{label} n:{int(m['n'])} "
        f"brier120_v24:{m['brier_base']:.8f} brier120_plus_opp:{m['brier_plus']:.8f} "
        f"brier_delta:{m['brier_plus']-m['brier_base']:+.8f} "
        f"winner_logloss_v24:{m['ll_base']:.8f} winner_logloss_plus_opp:{m['ll_plus']:.8f} "
        f"logloss_delta:{m['ll_plus']-m['ll_base']:+.8f} "
        f"winner_ticket_rank_v24:{m['rank_base']:.3f} winner_ticket_rank_plus_opp:{m['rank_plus']:.3f} "
        f"rank_delta:{m['rank_plus']-m['rank_base']:+.3f} "
        f"top1:{m['top1_base']*100:.2f}%->{m['top1_plus']*100:.2f}% "
        f"top3:{m['top3_base']*100:.2f}%->{m['top3_plus']*100:.2f}% "
        f"top5:{m['top5_base']*100:.2f}%->{m['top5_plus']*100:.2f}% "
        f"top10:{m['top10_base']*100:.2f}%->{m['top10_plus']*100:.2f}%",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_V24_HEAD_TRI_OOS_MODE=read_only_fixed_historical_first_place_only_no_tuning", flush=True)
    print(f"OPP_V24_HEAD_TRI_OOS_PERIOD={lane_oos.START}..{lane_oos.END}", flush=True)
    print("OPP_V24_HEAD_TRI_OOS_SPLITS=2026-03-31,2026-04-30,2026-05-31", flush=True)
    print(
        f"OPP_V24_HEAD_TRI_OOS_GATES=train_cond>={lane_oos.TRAIN_COND_MIN},train_base>={lane_oos.TRAIN_BASE_MIN},shrink_k={lane_oos.SHRINK_K}",
        flush=True,
    )
    print("OPP_V24_HEAD_TRI_OOS_BASE=current_v24_fixed_motor33_boat34_prob_temp_2.20", flush=True)
    print("OPP_V24_HEAD_TRI_OOS_MAPPING=pressure_changes_first_place_only_second_third_conditionals_stay_v24", flush=True)
    print(f"OPP_V24_HEAD_TRI_OOS_COEF={UNIT_PRESSURE_COEF:.1f}_fixed", flush=True)
    print("OPP_V24_HEAD_TRI_OOS_POLICY=train_only_pressure_effects_no_writes_no_production_no_line_no_coefficient_search_no_subgroup_selection", flush=True)

    split_deltas: list[tuple[float, float, float]] = []
    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='240s'")
        for split in lane_oos.SPLITS:
            lane_rows = lane_oos.fetch_scored(conn, split)
            records, incomplete = build_records(lane_rows)
            print(
                f"OPP_V24_HEAD_TRI_OOS_COVERAGE={split}=lane_rows:{len(lane_rows)} evaluated_races:{len(records)} incomplete:{incomplete}",
                flush=True,
            )
            overall = tri_oos.aggregate(records)
            emit(split, "OVERALL", overall)
            split_deltas.append((
                overall["brier_plus"] - overall["brier_base"],
                overall["ll_plus"] - overall["ll_base"],
                overall["rank_plus"] - overall["rank_base"],
            ))

            by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
            by_venue: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for r in records:
                by_band[r["race_band"]].append(r)
                by_venue[r["venue"]].append(r)
            for band in ("R01_04", "R05_08", "R09_12", "R_OTHER"):
                if by_band.get(band):
                    emit(split, f"RACE_BAND:{band}", tri_oos.aggregate(by_band[band]))
            venue_metrics = [tri_oos.aggregate(by_venue[v]) for v in sorted(by_venue)]
            print(
                f"OPP_V24_HEAD_TRI_OOS_VENUE_SIGN_COUNT={split}=venues:{len(venue_metrics)} "
                f"brier_better:{sum((m['brier_plus']-m['brier_base']) < 0 for m in venue_metrics)} "
                f"logloss_better:{sum((m['ll_plus']-m['ll_base']) < 0 for m in venue_metrics)} "
                f"rank_better:{sum((m['rank_plus']-m['rank_base']) < 0 for m in venue_metrics)}",
                flush=True,
            )

    if split_deltas and all(b < 0 and l < 0 and r < 0 for b, l, r in split_deltas):
        interpretation = "CONSISTENT_HEAD_ONLY_TRIFECTA_OOS_SUPPORT"
    elif split_deltas and all(b < 0 and l < 0 for b, l, _ in split_deltas):
        interpretation = "CONSISTENT_PROBABILITY_SCORE_GAIN_BUT_RANK_MIXED_RESEARCH_ONLY"
    else:
        interpretation = "MIXED_HEAD_ONLY_TRIFECTA_OOS_KEEP_RESEARCH_ONLY"
    print(f"OPP_V24_HEAD_TRI_OOS_INTERPRETATION={interpretation}", flush=True)
    print("OPP_V24_HEAD_TRI_OOS_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_V24_HEAD_TRI_OOS_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_V24_HEAD_TRI_OOS_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
