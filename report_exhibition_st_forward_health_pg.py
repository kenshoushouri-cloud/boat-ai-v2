# -*- coding: utf-8 -*-
"""Read-only realized health report for frozen exhibition-ST Forward Shadow.

Reads only v2_exhibition_st_forward_shadow and current realized v2_results.
No writes, no promotion, and no Production/LINE behavior changes.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import psycopg
from psycopg.rows import dict_row

DB = (os.getenv("DATABASE_URL") or "").strip()
EPS = 1e-15
TICKETS: Tuple[str, ...] = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7) if b != a
    for c in range(1, 7) if c not in (a, b)
)
TICKET_INDEX = {t: i for i, t in enumerate(TICKETS)}


def race_band(race_no: int) -> str:
    if 1 <= race_no <= 4:
        return "R01_04"
    if 5 <= race_no <= 8:
        return "R05_08"
    if 9 <= race_no <= 12:
        return "R09_12"
    return "R_OTHER"


def _si(v: Any, d: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else d
    except Exception:
        return d


def _valid_prob_vector(values: Any) -> bool:
    if not isinstance(values, (list, tuple)) or len(values) != 120:
        return False
    try:
        xs = [float(x) for x in values]
    except Exception:
        return False
    return all(math.isfinite(x) and x >= 0.0 for x in xs) and abs(sum(xs) - 1.0) <= 2e-5


def _rank(values: List[float], idx: int) -> int:
    target = values[idx]
    return 1 + sum(1 for j, p in enumerate(values) if j != idx and p > target)


def _first_marginal(values: List[float]) -> List[float]:
    out = [0.0] * 6
    for ticket, p in zip(TICKETS, values):
        out[int(ticket[0]) - 1] += p
    return out


def _lane_rank(values: List[float], idx: int) -> int:
    target = values[idx]
    return 1 + sum(1 for j, p in enumerate(values) if j != idx and p > target)


def _metric(base: List[float], st: List[float], actual: str) -> Dict[str, float]:
    idx = TICKET_INDEX[actual]
    rb = _rank(base, idx)
    rs = _rank(st, idx)
    bfirst = _first_marginal(base)
    sfirst = _first_marginal(st)
    fi = int(actual[0]) - 1
    yfirst = [1.0 if i == fi else 0.0 for i in range(6)]
    return {
        "tri_brier_base": sum((p - (1.0 if i == idx else 0.0)) ** 2 for i, p in enumerate(base)),
        "tri_brier_st": sum((p - (1.0 if i == idx else 0.0)) ** 2 for i, p in enumerate(st)),
        "tri_ll_base": -math.log(max(EPS, base[idx])),
        "tri_ll_st": -math.log(max(EPS, st[idx])),
        "tri_rank_base": float(rb),
        "tri_rank_st": float(rs),
        "top1_base": float(rb <= 1), "top1_st": float(rs <= 1),
        "top3_base": float(rb <= 3), "top3_st": float(rs <= 3),
        "top5_base": float(rb <= 5), "top5_st": float(rs <= 5),
        "top10_base": float(rb <= 10), "top10_st": float(rs <= 10),
        "first_brier_base": sum((yfirst[i] - bfirst[i]) ** 2 for i in range(6)) / 6.0,
        "first_brier_st": sum((yfirst[i] - sfirst[i]) ** 2 for i in range(6)) / 6.0,
        "first_ll_base": -math.log(max(EPS, bfirst[fi])),
        "first_ll_st": -math.log(max(EPS, sfirst[fi])),
        "first_rank_base": float(_lane_rank(bfirst, fi)),
        "first_rank_st": float(_lane_rank(sfirst, fi)),
    }


def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    if not rows:
        return {"n": 0.0}
    keys = [k for k in rows[0] if k not in {"race_id", "race_date", "venue_id", "race_band"}]
    out: Dict[str, float] = {"n": float(len(rows))}
    for key in keys:
        out[key] = sum(float(r[key]) for r in rows) / len(rows)
    return out


def emit(label: str, m: Dict[str, float]) -> None:
    n = int(m.get("n", 0.0))
    if not n:
        print(f"EXH_ST_FORWARD_HEALTH={label} n:0", flush=True)
        return
    print(
        f"EXH_ST_FORWARD_HEALTH={label} n:{n} "
        f"tri_brier_delta:{m['tri_brier_st']-m['tri_brier_base']:+.8f} "
        f"tri_logloss_delta:{m['tri_ll_st']-m['tri_ll_base']:+.8f} "
        f"tri_rank_delta:{m['tri_rank_st']-m['tri_rank_base']:+.4f} "
        f"top1:{m['top1_base']*100:.2f}%->{m['top1_st']*100:.2f}% "
        f"top3:{m['top3_base']*100:.2f}%->{m['top3_st']*100:.2f}% "
        f"top5:{m['top5_base']*100:.2f}%->{m['top5_st']*100:.2f}% "
        f"top10:{m['top10_base']*100:.2f}%->{m['top10_st']*100:.2f}% "
        f"first_brier_delta:{m['first_brier_st']-m['first_brier_base']:+.8f} "
        f"first_logloss_delta:{m['first_ll_st']-m['first_ll_base']:+.8f} "
        f"first_rank_delta:{m['first_rank_st']-m['first_rank_base']:+.4f}",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("EXH_ST_FORWARD_HEALTH_MODE=read_only_realized_frozen_shadow", flush=True)
    print("EXH_ST_FORWARD_HEALTH_POLICY=block_manual_review_only_no_writes_no_production_no_line", flush=True)
    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("select to_regclass('public.v2_exhibition_st_forward_shadow') tbl")
            if not cur.fetchone()["tbl"]:
                print("EXH_ST_FORWARD_HEALTH_TABLE=missing", flush=True)
                print("EXH_ST_FORWARD_HEALTH_RESULT=PASS_READ_ONLY", flush=True)
                return
            cur.execute(
                """
                select race_id,race_date,venue_id,race_no,st_beta,deadline_at,snapshot_at,
                       minutes_before,start_timing_ranks,base_probs,st_probs,source
                  from v2_exhibition_st_forward_shadow
                 order by race_date,race_no,race_id
                """
            )
            shadow = [dict(x) for x in cur.fetchall()]
            race_ids = [str(x["race_id"]) for x in shadow]
            if race_ids:
                cur.execute(
                    """
                    select race_id,first_lane,second_lane,third_lane,result_status
                      from v2_results
                     where race_id=any(%s)
                    """,
                    (race_ids,),
                )
                results = {str(x["race_id"]): dict(x) for x in cur.fetchall()}
            else:
                results = {}

    records: List[Dict[str, Any]] = []
    pending = invalid_shadow = invalid_result = timing_invalid = source_invalid = 0
    for row in shadow:
        if row.get("snapshot_at") is None or row.get("deadline_at") is None or row["snapshot_at"] >= row["deadline_at"]:
            timing_invalid += 1
            continue
        mb = float(row.get("minutes_before") or 0.0)
        if not (8.0 <= mb <= 15.0):
            timing_invalid += 1
            continue
        if str(row.get("source") or "") != "official_beforeinfo":
            source_invalid += 1
            continue
        ranks = list(row.get("start_timing_ranks") or [])
        base = list(row.get("base_probs") or [])
        st = list(row.get("st_probs") or [])
        if sorted(_si(x) for x in ranks) != [1, 2, 3, 4, 5, 6] or not _valid_prob_vector(base) or not _valid_prob_vector(st):
            invalid_shadow += 1
            continue
        res = results.get(str(row["race_id"]))
        if not res:
            pending += 1
            continue
        lanes = [_si(res.get("first_lane")), _si(res.get("second_lane")), _si(res.get("third_lane"))]
        if not all(1 <= x <= 6 for x in lanes) or len(set(lanes)) != 3:
            status = str(res.get("result_status") or "").lower()
            if status in {"", "pending", "scheduled", "not_official"}:
                pending += 1
            else:
                invalid_result += 1
            continue
        actual = f"{lanes[0]}-{lanes[1]}-{lanes[2]}"
        m = _metric([float(x) for x in base], [float(x) for x in st], actual)
        m.update({
            "race_id": str(row["race_id"]),
            "race_date": row["race_date"],
            "venue_id": str(row["venue_id"]),
            "race_band": race_band(_si(row.get("race_no"))),
        })
        records.append(m)

    print(
        f"EXH_ST_FORWARD_HEALTH_COVERAGE=shadow:{len(shadow)} evaluated:{len(records)} pending:{pending} "
        f"invalid_shadow:{invalid_shadow} invalid_result:{invalid_result} timing_invalid:{timing_invalid} source_invalid:{source_invalid}",
        flush=True,
    )
    emit("OVERALL", aggregate(records))

    by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_band: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_venue: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_date[str(r["race_date"])].append(r)
        by_band[r["race_band"]].append(r)
        by_venue[r["venue_id"]].append(r)
    for d in sorted(by_date):
        emit(f"DATE:{d}", aggregate(by_date[d]))
    for b in ("R01_04", "R05_08", "R09_12"):
        if by_band.get(b):
            emit(f"RACE_BAND:{b}", aggregate(by_band[b]))

    venue_metrics = [aggregate(by_venue[v]) for v in sorted(by_venue)]
    if venue_metrics:
        print(
            f"EXH_ST_FORWARD_HEALTH_VENUE_SIGN_COUNT=venues:{len(venue_metrics)} "
            f"tri_ll_better:{sum(m['tri_ll_st'] < m['tri_ll_base'] for m in venue_metrics)} "
            f"tri_brier_better:{sum(m['tri_brier_st'] < m['tri_brier_base'] for m in venue_metrics)} "
            f"tri_rank_better:{sum(m['tri_rank_st'] < m['tri_rank_base'] for m in venue_metrics)}",
            flush=True,
        )
    print("EXH_ST_FORWARD_HEALTH_PROMOTION=BLOCK_MANUAL_REVIEW_ONLY", flush=True)
    print("EXH_ST_FORWARD_HEALTH_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"EXH_ST_FORWARD_HEALTH_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
