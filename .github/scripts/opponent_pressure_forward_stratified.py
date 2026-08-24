# -*- coding: utf-8 -*-
"""Read-only stratified realized Forward evaluation for Opponent Pressure.

Fixed diagnostics only:
- venue
- race-number bands R01-04 / R05-08 / R09-12

Uses the already frozen v2_opponent_pressure_shadow_v2 rows and current official
v2_results. No threshold search, tuning, DB writes, Production/LINE changes, or
promotion decisions.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

import opponent_pressure_forward_realized as base

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat(os.getenv("OPP_PRESSURE_STRAT_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_PRESSURE_STRAT_END", date.today().isoformat()))
EPS = 1e-12


def _race_band(race_no: int) -> str:
    if 1 <= race_no <= 4:
        return "R01_04"
    if 5 <= race_no <= 8:
        return "R05_08"
    if 9 <= race_no <= 12:
        return "R09_12"
    return "R_OTHER"


def _venue_code(row: dict[str, Any]) -> str:
    raw = row.get("venue_id") or row.get("venue_code") or ""
    s = str(raw).strip()
    return s.zfill(2) if s else "UNKNOWN"


def _record(row: dict[str, Any]) -> dict[str, Any] | None:
    if str(row.get("result_status") or "") != "official":
        return None
    rr = base._finish_map(row)
    if sorted(rr.keys()) != [1, 2, 3, 4, 5, 6] or sorted(rr.values()) != [1, 2, 3, 4, 5, 6]:
        return None
    arrays = [row.get(k) for k in ("matched_opponents", "base_win", "base_top3", "adj_win", "adj_top3")]
    if any(not isinstance(x, list) or len(x) != 6 for x in arrays):
        return None
    if int(row.get("model_version") or 0) != 2 or row.get("train_end") >= row.get("race_date"):
        return None
    if any(int(x) < 4 for x in row["matched_opponents"]):
        return None

    base_win = [float(x) for x in row["base_win"]]
    adj_win = [float(x) for x in row["adj_win"]]
    base_top3 = [float(x) for x in row["base_top3"]]
    adj_top3 = [float(x) for x in row["adj_top3"]]
    winner_lane = next(l for l, pos in rr.items() if pos == 1)
    winner_idx = winner_lane - 1
    y_win = [1.0 if rr[l] == 1 else 0.0 for l in range(1, 7)]
    y_top3 = [1.0 if rr[l] <= 3 else 0.0 for l in range(1, 7)]
    nb = base._norm(base_win)
    na = base._norm(adj_win)
    race_no = int(row.get("race_no") or 0)
    return {
        "race_id": str(row["race_id"]),
        "race_date": row["race_date"],
        "venue": _venue_code(row),
        "race_no": race_no,
        "race_band": _race_band(race_no),
        "win_brier_base": base._mean([(y_win[i] - base_win[i]) ** 2 for i in range(6)]),
        "win_brier_adj": base._mean([(y_win[i] - adj_win[i]) ** 2 for i in range(6)]),
        "top3_brier_base": base._mean([(y_top3[i] - base_top3[i]) ** 2 for i in range(6)]),
        "top3_brier_adj": base._mean([(y_top3[i] - adj_top3[i]) ** 2 for i in range(6)]),
        "winner_logloss_base": -math.log(max(EPS, nb[winner_idx])),
        "winner_logloss_adj": -math.log(max(EPS, na[winner_idx])),
        "winner_rank_base": float(base._rank_desc(base_win, winner_idx)),
        "winner_rank_adj": float(base._rank_desc(adj_win, winner_idx)),
    }


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    if END < START:
        raise RuntimeError("end before start")

    print("OPP_PRESSURE_STRAT_MODE=read_only_fixed_strata_no_tuning", flush=True)
    print(f"OPP_PRESSURE_STRAT_PERIOD={START}..{END}", flush=True)
    print("OPP_PRESSURE_STRAT_RESULT_SOURCE=v2_results_first_to_sixth_lane", flush=True)
    print("OPP_PRESSURE_STRAT_STRATA=venue_and_fixed_race_bands_R01_04_R05_08_R09_12", flush=True)
    print("OPP_PRESSURE_STRAT_POLICY=frozen_shadow_only_no_writes_no_production_no_line_no_threshold_search", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select s.race_id,s.race_date,s.model_version,s.train_end,
                       s.matched_opponents,s.base_win,s.base_top3,s.adj_win,s.adj_top3,
                       r.result_status,r.race_status,
                       r.first_lane,r.second_lane,r.third_lane,
                       r.fourth_lane,r.fifth_lane,r.sixth_lane,
                       q.venue_id,q.venue_code,q.race_no
                from v2_opponent_pressure_shadow_v2 s
                left join v2_results r on r.race_id=s.race_id
                left join v2_races q on q.race_id=s.race_id
                where s.race_date between %s and %s
                order by s.race_date,s.race_id
                """,
                (START, END),
            )
            rows = [dict(r) for r in cur.fetchall()]

    records: list[dict[str, Any]] = []
    no_result = malformed_or_integrity = no_meta = 0
    for row in rows:
        if str(row.get("result_status") or "") != "official":
            no_result += 1
            continue
        if not row.get("venue_id") and not row.get("venue_code"):
            no_meta += 1
            continue
        rec = _record(row)
        if rec is None:
            malformed_or_integrity += 1
            continue
        records.append(rec)

    print(
        f"OPP_PRESSURE_STRAT_COVERAGE=shadow:{len(rows)} evaluated:{len(records)} no_result:{no_result} "
        f"malformed_or_integrity:{malformed_or_integrity} no_meta:{no_meta}",
        flush=True,
    )

    base._print_metrics("OPP_PRESSURE_STRAT_OVERALL", base._aggregate(records))

    by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_venue: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        by_band[rec["race_band"]].append(rec)
        by_venue[rec["venue"]].append(rec)

    for band in ("R01_04", "R05_08", "R09_12", "R_OTHER"):
        if by_band.get(band):
            base._print_metrics(f"OPP_PRESSURE_STRAT_RACE_BAND={band}", base._aggregate(by_band[band]))

    for venue in sorted(by_venue):
        base._print_metrics(f"OPP_PRESSURE_STRAT_VENUE={venue}", base._aggregate(by_venue[venue]))

    # Descriptive sign-count only; no venue is selected or excluded by this report.
    venue_metrics = [base._aggregate(by_venue[v]) for v in sorted(by_venue)]
    venue_signs = {
        "win": sum((m["win_brier_adj"] - m["win_brier_base"]) < 0 for m in venue_metrics),
        "top3": sum((m["top3_brier_adj"] - m["top3_brier_base"]) < 0 for m in venue_metrics),
        "logloss": sum((m["winner_logloss_adj"] - m["winner_logloss_base"]) < 0 for m in venue_metrics),
        "rank": sum((m["winner_rank_adj"] - m["winner_rank_base"]) < 0 for m in venue_metrics),
    }
    print(
        f"OPP_PRESSURE_STRAT_VENUE_SIGN_COUNT=venues:{len(venue_metrics)} "
        f"win_brier_better:{venue_signs['win']} top3_brier_better:{venue_signs['top3']} "
        f"logloss_better:{venue_signs['logloss']} rank_better:{venue_signs['rank']}",
        flush=True,
    )
    print("OPP_PRESSURE_STRAT_INTERPRETATION=descriptive_stability_check_only_keep_collecting_forward", flush=True)
    print("OPP_PRESSURE_STRAT_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_PRESSURE_STRAT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_PRESSURE_STRAT_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
