# -*- coding: utf-8 -*-
"""Read-only Forward health audit for the existing sparse Motor2 Shadow.

The production Shadow intentionally stores only candidate tickets or probability-
rank boundary tickets (save_policy=candidate_or_prob_rank_boundary), not all 120
trifecta tickets. Therefore a full-vector Brier score cannot be recovered from
this table alone.

This audit uses one latest valid PRE snapshot per race to avoid multiplying a
race across overlapping morning/day/night windows. It reports:
- sparse snapshot coverage and row-count distribution;
- candidate hit/ROI comparison, which is valid for the saved candidate set;
- conditional log-loss / probability-rank comparison only when the realized
  result ticket happened to be present in the sparse saved set. That conditional
  metric is selection-biased and must not be used as promotion evidence.

No DB writes, no Production/LINE changes, no threshold/coefficient search.
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

# This file lives under .github/scripts, while db_pg.py lives at repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))
START_DATE = (os.getenv("MOTOR2_FORWARD_PROB_START") or "2026-08-20").strip()
END_DATE = (os.getenv("MOTOR2_FORWARD_PROB_END") or datetime.now(JST).strftime("%Y-%m-%d")).strip()
UNIT_YEN = 100
EPS = 1e-15


def sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else d
    except Exception:
        return d


def si(v: Any, d: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else d
    except Exception:
        return d


def as_dt(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v
    if v in (None, ""):
        return None
    try:
        x = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if x.tzinfo is None:
            x = x.replace(tzinfo=timezone.utc)
        return x
    except Exception:
        return None


def fetch_rows() -> List[Dict[str, Any]]:
    return [dict(r) for r in fetch_all(
        """
        select s.race_id,s.race_date::date race_date,s.venue_id,s.race_no,s.ticket,
               s.odds,s.market_rank,
               s.base_prob,s.base_prob_rank,s.motor2_prob,s.motor2_prob_rank,
               s.base_low_candidate,s.motor2_low_candidate,
               s.base_mid_candidate,s.motor2_mid_candidate,
               s.candidate_transition,
               s.window_name,s.run_class,s.snapshot_key,s.snapshot_at,
               s.result_ticket,s.payout_yen,s.evaluated_at,
               r.deadline_at
          from v2_v24_motor2_forward_shadow s
          left join v2_races r on r.race_id=s.race_id
         where s.race_date between %s and %s
           and s.window_name in ('morning','day','night')
           and s.evaluated_at is not null
           and s.result_ticket is not null
           and s.base_prob is not null
           and s.motor2_prob is not null
         order by s.race_date,s.race_id,s.snapshot_at,s.id
        """,
        (START_DATE, END_DATE),
    )]


def snapshot_groups(rows: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str, str, str], List[Dict[str, Any]]]:
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


def group_time(rs: List[Dict[str, Any]]) -> datetime | None:
    vals = [as_dt(r.get("snapshot_at")) for r in rs]
    vals = [x for x in vals if x is not None]
    return max(vals) if vals else None


def group_deadline(rs: List[Dict[str, Any]]) -> datetime | None:
    vals = [as_dt(r.get("deadline_at")) for r in rs]
    vals = [x for x in vals if x is not None]
    return min(vals) if vals else None


def latest_sparse_pre_per_race(rows: Iterable[Dict[str, Any]]):
    groups = snapshot_groups(rows)
    by_race: Dict[str, Tuple[datetime, List[Dict[str, Any]]]] = {}
    no_time = no_deadline = after_deadline = bad_result = 0

    for key, rs in groups.items():
        actuals = {str(r.get("result_ticket") or "") for r in rs if r.get("result_ticket")}
        if len(actuals) != 1:
            bad_result += 1
            continue
        sat = group_time(rs)
        deadline = group_deadline(rs)
        if sat is None:
            no_time += 1
            continue
        if deadline is None:
            no_deadline += 1
            continue
        if sat >= deadline:
            after_deadline += 1
            continue
        rid = key[0]
        if rid not in by_race or sat >= by_race[rid][0]:
            by_race[rid] = (sat, rs)

    return [x[1] for x in by_race.values()], len(groups), no_time, no_deadline, after_deadline, bad_result


def percentile(values: List[int], q: float) -> int:
    if not values:
        return 0
    xs = sorted(values)
    idx = int(round((len(xs) - 1) * q))
    return xs[max(0, min(idx, len(xs) - 1))]


def selected(row: Dict[str, Any], model: str) -> bool:
    if model == "base":
        return bool(row.get("base_low_candidate")) or bool(row.get("base_mid_candidate"))
    return bool(row.get("motor2_low_candidate")) or bool(row.get("motor2_mid_candidate"))


def candidate_stat(groups: List[List[Dict[str, Any]]], model: str) -> Dict[str, float]:
    bets = hits = returned = 0
    for rs in groups:
        actual = str(rs[0].get("result_ticket") or "")
        payout = si(rs[0].get("payout_yen"), 0)
        for r in rs:
            if not selected(r, model):
                continue
            bets += 1
            if str(r.get("ticket") or "") == actual:
                hits += 1
                returned += payout
    investment = bets * UNIT_YEN
    roi = (returned / investment * 100.0) if investment else 0.0
    return {
        "bets": float(bets),
        "hits": float(hits),
        "returned": float(returned),
        "investment": float(investment),
        "roi": roi,
    }


def conditional_result_metrics(groups: List[List[Dict[str, Any]]]) -> Dict[str, float]:
    n = 0
    sum_ll_b = sum_ll_m = 0.0
    sum_rk_b = sum_rk_m = 0.0
    ll_improve = rank_improve = 0
    for rs in groups:
        actual = str(rs[0].get("result_ticket") or "")
        row = next((r for r in rs if str(r.get("ticket") or "") == actual), None)
        if row is None:
            continue
        pb = max(sf(row.get("base_prob"), 0.0), EPS)
        pm = max(sf(row.get("motor2_prob"), 0.0), EPS)
        rb = sf(row.get("base_prob_rank"), 0.0)
        rm = sf(row.get("motor2_prob_rank"), 0.0)
        if rb <= 0 or rm <= 0:
            continue
        llb = -math.log(pb)
        llm = -math.log(pm)
        n += 1
        sum_ll_b += llb
        sum_ll_m += llm
        sum_rk_b += rb
        sum_rk_m += rm
        ll_improve += int(llm < llb)
        rank_improve += int(rm < rb)
    if not n:
        return {"n": 0.0}
    return {
        "n": float(n),
        "base_ll": sum_ll_b / n,
        "motor_ll": sum_ll_m / n,
        "delta_ll": (sum_ll_m - sum_ll_b) / n,
        "base_rank": sum_rk_b / n,
        "motor_rank": sum_rk_m / n,
        "delta_rank": (sum_rk_m - sum_rk_b) / n,
        "ll_improve": float(ll_improve),
        "rank_improve": float(rank_improve),
    }


def fmt_scope(label: str, groups: List[List[Dict[str, Any]]]) -> None:
    base = candidate_stat(groups, "base")
    motor = candidate_stat(groups, "motor")
    cond = conditional_result_metrics(groups)
    n = len(groups)
    rows = sum(len(rs) for rs in groups)
    saved_actual = int(cond.get("n", 0.0))
    if saved_actual:
        cond_text = (
            f"conditional_saved_result:{saved_actual}/{n} "
            f"base_ll:{cond['base_ll']:.8f} motor_ll:{cond['motor_ll']:.8f} delta_ll:{cond['delta_ll']:+.8f} "
            f"ll_improve:{int(cond['ll_improve'])}/{saved_actual} "
            f"base_rank:{cond['base_rank']:.4f} motor_rank:{cond['motor_rank']:.4f} delta_rank:{cond['delta_rank']:+.4f} "
            f"rank_improve:{int(cond['rank_improve'])}/{saved_actual}"
        )
    else:
        cond_text = f"conditional_saved_result:0/{n} conditional_ll:NA conditional_rank:NA"
    print(
        f"MOTOR2_FORWARD_PROB_SCOPE={label} races:{n} sparse_rows:{rows} "
        f"base_bets:{int(base['bets'])} base_hits:{int(base['hits'])} base_roi:{base['roi']:.2f}% "
        f"motor_bets:{int(motor['bets'])} motor_hits:{int(motor['hits'])} motor_roi:{motor['roi']:.2f}% "
        f"candidate_roi_delta:{motor['roi'] - base['roi']:+.2f}pt {cond_text}",
        flush=True,
    )


def main() -> None:
    print("MOTOR2_FORWARD_PROB_MODE=read_only_existing_sparse_shadow_health_no_tuning", flush=True)
    print(f"MOTOR2_FORWARD_PROB_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "MOTOR2_FORWARD_PROB_POLICY=latest_sparse_pre_snapshot_per_race_"
        "save_policy_candidate_or_prob_rank_boundary_no_writes_no_production_no_line_"
        "no_threshold_or_coefficient_search",
        flush=True,
    )
    rows = fetch_rows()
    snapshots, group_count, no_time, no_deadline, after_deadline, bad_result = latest_sparse_pre_per_race(rows)
    counts = [len({str(r.get('ticket') or '') for r in rs}) for rs in snapshots]
    full120 = sum(1 for x in counts if x == 120)
    print(
        f"MOTOR2_FORWARD_PROB_COVERAGE=raw_rows:{len(rows)} snapshot_groups:{group_count} "
        f"latest_valid_pre_races:{len(snapshots)} no_snapshot_time_groups:{no_time} "
        f"no_deadline_groups:{no_deadline} at_or_after_deadline_groups:{after_deadline} bad_result_groups:{bad_result}",
        flush=True,
    )
    print(
        f"MOTOR2_FORWARD_PROB_SPARSE_ROWS=min:{min(counts) if counts else 0} "
        f"median:{percentile(counts,0.5)} p90:{percentile(counts,0.9)} max:{max(counts) if counts else 0} "
        f"full120_latest:{full120}",
        flush=True,
    )
    print(
        "MOTOR2_FORWARD_PROB_VECTOR=brier:NA reason:sparse_save_policy_candidate_or_prob_rank_boundary_"
        "brier_unavailable_without_full_vector",
        flush=True,
    )

    fmt_scope("OVERALL", snapshots)
    dates = sorted({str(rs[0].get("race_date")) for rs in snapshots})
    for d in dates:
        fmt_scope(f"DATE:{d}", [rs for rs in snapshots if str(rs[0].get("race_date")) == d])
    venues = sorted({str(rs[0].get("venue_id") or "") for rs in snapshots})
    for v in venues:
        fmt_scope(f"VENUE:{v}", [rs for rs in snapshots if str(rs[0].get("venue_id") or "") == v])

    print(
        "MOTOR2_FORWARD_PROB_INTERPRETATION=candidate_roi_is_forward_for_latest_sparse_pre_snapshot;"
        "conditional_ll_rank_is_selection_biased_diagnostic_only;brier_unavailable;"
        "no_automatic_production_promotion",
        flush=True,
    )
    print("MOTOR2_FORWARD_PROB_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
