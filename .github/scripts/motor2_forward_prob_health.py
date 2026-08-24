# -*- coding: utf-8 -*-
"""Read-only Forward probability-quality audit for existing Motor2 Shadow.

Compares current v24 fixed motor2=33 baseline against the already-collected
actual motor_place2_rate Shadow on realized PRE observations. The latest complete
PRE snapshot per race is used so overlapping morning/day/night windows do not
multiply-weight a race.

No DB writes, no Production/LINE changes, no coefficient or threshold search.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Tuple

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))
START_DATE = (os.getenv("MOTOR2_FORWARD_PROB_START") or "2026-08-20").strip()
END_DATE = (os.getenv("MOTOR2_FORWARD_PROB_END") or datetime.now(JST).strftime("%Y-%m-%d")).strip()
EPS = 1e-15


def sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else d
    except Exception:
        return d


def fetch_rows() -> List[Dict[str, Any]]:
    return [dict(r) for r in fetch_all(
        """
        select race_id,race_date::date race_date,venue_id,race_no,ticket,
               base_prob,motor2_prob,window_name,run_class,snapshot_key,snapshot_at,
               result_ticket,evaluated_at
          from v2_v24_motor2_forward_shadow
         where race_date between %s and %s
           and window_name in ('morning','day','night')
           and evaluated_at is not null
           and result_ticket is not null
           and base_prob is not null
           and motor2_prob is not null
         order by race_date,race_id,snapshot_at,id
        """,
        (START_DATE, END_DATE),
    )]


def snapshot_groups(rows: Iterable[Dict[str, Any]]):
    groups: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = (
            str(r.get("race_id") or ""),
            str(r.get("run_class") or ""),
            str(r.get("window_name") or ""),
            str(r.get("snapshot_key") or ""),
        )
        groups[key].append(r)
    return groups


def latest_complete_per_race(rows: Iterable[Dict[str, Any]]):
    groups = snapshot_groups(rows)
    complete: List[Tuple[str, Any, List[Dict[str, Any]]]] = []
    incomplete_groups = 0
    for key, rs in groups.items():
        tickets = {str(r.get("ticket") or "") for r in rs}
        actuals = {str(r.get("result_ticket") or "") for r in rs if r.get("result_ticket")}
        if len(rs) != 120 or len(tickets) != 120 or len(actuals) != 1:
            incomplete_groups += 1
            continue
        latest_at = max(str(r.get("snapshot_at") or "") for r in rs)
        complete.append((key[0], latest_at, rs))

    by_race: Dict[str, Tuple[str, List[Dict[str, Any]]]] = {}
    for race_id, latest_at, rs in complete:
        if race_id not in by_race or latest_at >= by_race[race_id][0]:
            by_race[race_id] = (latest_at, rs)
    return [x[1] for x in by_race.values()], len(groups), incomplete_groups


def race_metric(rs: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    base = {str(r["ticket"]): sf(r.get("base_prob")) for r in rs}
    motor = {str(r["ticket"]): sf(r.get("motor2_prob")) for r in rs}
    actual = str(rs[0].get("result_ticket") or "")
    if actual not in base or actual not in motor:
        return None
    sb = sum(base.values())
    sm = sum(motor.values())
    if sb <= 0 or sm <= 0:
        return None
    base = {k: v / sb for k, v in base.items()}
    motor = {k: v / sm for k, v in motor.items()}
    pb = max(base[actual], EPS)
    pm = max(motor[actual], EPS)
    br_b = sum((p - (1.0 if t == actual else 0.0)) ** 2 for t, p in base.items())
    br_m = sum((p - (1.0 if t == actual else 0.0)) ** 2 for t, p in motor.items())
    rank_b = 1 + sum(1 for t, p in base.items() if (p > base[actual]) or (p == base[actual] and t < actual))
    rank_m = 1 + sum(1 for t, p in motor.items() if (p > motor[actual]) or (p == motor[actual] and t < actual))
    first = rs[0]
    return {
        "race_id": str(first.get("race_id") or ""),
        "race_date": first.get("race_date"),
        "venue": str(first.get("venue_id") or ""),
        "window": str(first.get("window_name") or ""),
        "ll_b": -math.log(pb),
        "ll_m": -math.log(pm),
        "br_b": br_b,
        "br_m": br_m,
        "rk_b": float(rank_b),
        "rk_m": float(rank_m),
        "sum_b": sb,
        "sum_m": sm,
    }


def summarize(label: str, metrics: List[Dict[str, Any]]) -> None:
    n = len(metrics)
    if not n:
        print(f"MOTOR2_FORWARD_PROB_SCOPE={label} n:0", flush=True)
        return
    def avg(k: str) -> float:
        return sum(float(x[k]) for x in metrics) / n
    dll = avg("ll_m") - avg("ll_b")
    dbr = avg("br_m") - avg("br_b")
    drk = avg("rk_m") - avg("rk_b")
    improve_ll = sum(1 for x in metrics if x["ll_m"] < x["ll_b"])
    improve_br = sum(1 for x in metrics if x["br_m"] < x["br_b"])
    improve_rk = sum(1 for x in metrics if x["rk_m"] < x["rk_b"])
    print(
        f"MOTOR2_FORWARD_PROB_SCOPE={label} n:{n} "
        f"base_ll:{avg('ll_b'):.8f} motor_ll:{avg('ll_m'):.8f} delta_ll:{dll:+.8f} ll_improve:{improve_ll}/{n} "
        f"base_brier:{avg('br_b'):.8f} motor_brier:{avg('br_m'):.8f} delta_brier:{dbr:+.8f} brier_improve:{improve_br}/{n} "
        f"base_rank:{avg('rk_b'):.4f} motor_rank:{avg('rk_m'):.4f} delta_rank:{drk:+.4f} rank_improve:{improve_rk}/{n}",
        flush=True,
    )


def main() -> None:
    print("MOTOR2_FORWARD_PROB_MODE=read_only_existing_shadow_probability_quality_no_tuning", flush=True)
    print(f"MOTOR2_FORWARD_PROB_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("MOTOR2_FORWARD_PROB_POLICY=latest_complete_pre_snapshot_per_race_no_writes_no_production_no_line_no_threshold_or_coefficient_search", flush=True)
    rows = fetch_rows()
    snapshots, group_count, incomplete_groups = latest_complete_per_race(rows)
    metrics = [m for rs in snapshots if (m := race_metric(rs)) is not None]
    print(
        f"MOTOR2_FORWARD_PROB_COVERAGE=raw_rows:{len(rows)} snapshot_groups:{group_count} incomplete_groups:{incomplete_groups} latest_complete_races:{len(snapshots)} evaluated_races:{len(metrics)}",
        flush=True,
    )
    summarize("OVERALL", metrics)
    for d in sorted({str(x["race_date"]) for x in metrics}):
        summarize(f"DATE:{d}", [x for x in metrics if str(x["race_date"]) == d])
    for v in sorted({x["venue"] for x in metrics}):
        summarize(f"VENUE:{v}", [x for x in metrics if x["venue"] == v])
    print("MOTOR2_FORWARD_PROB_INTERPRETATION=FORWARD_EVIDENCE_ONLY_NO_AUTOMATIC_PRODUCTION_PROMOTION", flush=True)
    print("MOTOR2_FORWARD_PROB_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
