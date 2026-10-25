# -*- coding: utf-8 -*-
"""Read-only walk-forward comparison of preregistered V4 race selectors.

This experiment keeps the V4 probability model and formal top-two tickets fixed.
Only the daily six-race ordering formula changes.

Safety / timing:
- all race distributions, structural metrics, selector scores, selected six races,
  and formal top-two tickets are frozen before any result/payout query;
- selector candidates are fixed in source before execution;
- adaptive walk-forward selector choice uses prior common-evaluable days only;
- PostgreSQL is READ ONLY;
- no odds/EV selection, no replacement, no five-race shrink, no rerank after result.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist

VERSION = "2026-09-23 v4-selector-challenger-walkforward-v1"
START_DATE = date.fromisoformat(os.getenv("V4_SELECTOR_BT_START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("V4_SELECTOR_BT_END_DATE", "2026-09-22"))
BLOCKS = int(os.getenv("V4_SELECTOR_BT_BLOCKS", "10"))
UNIT_YEN = 100
OUTPUT_JSON = Path(
    os.getenv("V4_SELECTOR_BT_OUTPUT_JSON", "v4-selector-challenger-walkforward.json")
)

METRICS = ("head_p1", "head_margin", "top3_mass", "concentration")
SELECTORS: dict[str, tuple[str, ...]] = {
    "current_equal4": METRICS,
    "head_p1_only": ("head_p1",),
    "head_margin_only": ("head_margin",),
    "top3_mass_only": ("top3_mass",),
    "concentration_only": ("concentration",),
    "head_p1_head_margin": ("head_p1", "head_margin"),
    "head_p1_top3_mass": ("head_p1", "top3_mass"),
    "head_p1_concentration": ("head_p1", "concentration"),
    "head_margin_top3_mass": ("head_margin", "top3_mass"),
    "head_margin_concentration": ("head_margin", "concentration"),
    "top3_mass_concentration": ("top3_mass", "concentration"),
    "head_p1_head_margin_top3_mass": ("head_p1", "head_margin", "top3_mass"),
    "head_p1_head_margin_concentration": (
        "head_p1",
        "head_margin",
        "concentration",
    ),
    "head_p1_top3_mass_concentration": (
        "head_p1",
        "top3_mass",
        "concentration",
    ),
    "head_margin_top3_mass_concentration": (
        "head_margin",
        "top3_mass",
        "concentration",
    ),
}

if BLOCKS < 2:
    raise RuntimeError("V4_SELECTOR_BT_BLOCKS must be >= 2")
if END_DATE < START_DATE:
    raise RuntimeError("invalid selector backtest period")
if len(SELECTORS) != 15:
    raise RuntimeError("selector family drift")


def percentile_rank(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    ordered = sorted(rows, key=lambda row: (-float(row[key]), str(row["race_id"])))
    if len(ordered) <= 1:
        return {str(row["race_id"]): 1.0 for row in ordered}
    return {
        str(row["race_id"]): 1.0 - idx / (len(ordered) - 1)
        for idx, row in enumerate(ordered)
    }


def build_day_candidates(
    cur: psycopg.Cursor[Any], day: date
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]]:
    races, entries_by, course_by, opponent_by = hist.fetch_day_inputs(cur, day)
    cutoff = hist.cutoff_for(day)
    distributions: dict[str, dict[str, float]] = {}
    rows: list[dict[str, Any]] = []

    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        deadline = hist.aware_jst(race.get("deadline_at"))
        if len(entries) != 6 or deadline is None:
            continue
        try:
            base = hist.base_raw(entries, str(race.get("venue_id") or ""))
        except Exception:
            continue
        course = hist.course_map(
            entries=entries,
            deadline=deadline,
            cutoff=cutoff,
            course_by=course_by,
        )
        opponent = hist.opponent_delta(
            row=opponent_by.get(rid),
            race_day=day,
            deadline=deadline,
            cutoff=cutoff,
        )
        motor = hist.motor_map(entries)
        probs = v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        metrics = v4.structural_metrics(probs)
        distributions[rid] = probs
        rows.append(
            {
                "race_id": rid,
                "venue_id": str(race.get("venue_id") or "").zfill(2),
                "race_no": int(race.get("race_no") or 0),
                "deadline_at": deadline.isoformat(),
                "course_lane_count": len(course),
                "opponent_available": opponent is not None,
                "motor_available": bool(motor),
                **metrics,
            }
        )
    return distributions, rows


def freeze_selectors(
    distributions: Mapping[str, Mapping[str, float]],
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    if not rows:
        return {name: [] for name in SELECTORS}
    ranks = {metric: percentile_rank(rows, metric) for metric in METRICS}
    frozen: dict[str, list[dict[str, Any]]] = {}

    for selector, metric_keys in SELECTORS.items():
        scored: list[dict[str, Any]] = []
        for source in rows:
            rid = str(source["race_id"])
            score = sum(ranks[key][rid] for key in metric_keys) / len(metric_keys)
            scored.append({**source, "selector_score": score})
        scored.sort(
            key=lambda row: (
                -float(row["selector_score"]),
                -float(row["head_p1"]),
                -float(row["top3_mass"]),
                str(row["race_id"]),
            )
        )
        selected = scored[: min(v4.CORE_RACES, len(scored))]
        frozen[selector] = [
            {
                **row,
                "selector_rank": idx,
                "formal_top2": list(v4.top_tickets(distributions[str(row["race_id"])], 2)),
            }
            for idx, row in enumerate(selected, 1)
        ]

    baseline = v4.select_daily(
        distributions,
        race_cap=v4.CORE_RACES,
        ticket_count=v4.CORE_TICKETS,
    )
    expected = [str(row["race_id"]) for row in baseline]
    observed = [str(row["race_id"]) for row in frozen["current_equal4"]]
    if expected != observed:
        raise RuntimeError(
            f"current selector reproduction drift: expected={expected} observed={observed}"
        )
    return frozen


def fetch_results_after_freeze(
    cur: psycopg.Cursor[Any],
    day: date,
    frozen: Mapping[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    selected_ids = sorted(
        {
            str(row["race_id"])
            for selected in frozen.values()
            for row in selected
        }
    )
    if not selected_ids:
        return {}
    cur.execute(
        """
        select race_id,trifecta_ticket,trifecta_payout_yen,
               result_status,race_status
          from v2_results
         where race_date=%s
           and race_id=any(%s)
           and trifecta_ticket is not null
           and trifecta_payout_yen is not null
           and trifecta_payout_yen > 0
           and coalesce(result_status,'')='official'
           and coalesce(race_status,'')='official'
         order by race_id
        """,
        (day, selected_ids),
    )
    return {str(row["race_id"]): dict(row) for row in cur.fetchall()}


def evaluate_selector_day(
    *,
    day: date,
    selected: list[dict[str, Any]],
    distributions: Mapping[str, Mapping[str, float]],
    results: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    if len(selected) != v4.CORE_RACES:
        return None

    top1_hits = 0
    top2_hits = 0
    head_hits = 0
    gross = 0
    log_loss_sum = 0.0
    actual_prob_sum = 0.0
    rows_out: list[dict[str, Any]] = []

    for row in selected:
        rid = str(row["race_id"])
        result = results.get(rid)
        if not result:
            return None
        actual = hist.norm_ticket(result.get("trifecta_ticket"))
        payout = int(result.get("trifecta_payout_yen") or 0)
        if actual is None or payout <= 0:
            return None
        top2 = list(row["formal_top2"])
        probs = distributions[rid]
        actual_prob = float(probs.get(actual, 0.0))
        if actual_prob <= 0.0 or not math.isfinite(actual_prob):
            return None
        head_actual = int(actual.split("-", 1)[0])
        top1_hit = actual == top2[0]
        top2_hit = actual in top2
        head_hit = head_actual == int(row["head_lane"])
        top1_hits += int(top1_hit)
        top2_hits += int(top2_hit)
        head_hits += int(head_hit)
        gross += payout if top2_hit else 0
        log_loss_sum += -math.log(max(actual_prob, 1e-15))
        actual_prob_sum += actual_prob
        rows_out.append(
            {
                "race_id": rid,
                "selector_rank": int(row["selector_rank"]),
                "selector_score": round(float(row["selector_score"]), 12),
                "formal_top2": top2,
                "head_lane": int(row["head_lane"]),
                "head_p1": round(float(row["head_p1"]), 12),
                "head_margin": round(float(row["head_margin"]), 12),
                "top3_mass": round(float(row["top3_mass"]), 12),
                "concentration": round(float(row["concentration"]), 12),
                "course_lane_count": int(row["course_lane_count"]),
                "opponent_available": bool(row["opponent_available"]),
                "motor_available": bool(row["motor_available"]),
                "actual_trifecta": actual,
                "payout_yen": payout,
                "actual_prob": round(actual_prob, 12),
                "top1_hit": top1_hit,
                "top2_hit": top2_hit,
                "head_hit": head_hit,
            }
        )

    investment = v4.CORE_RACES * v4.CORE_TICKETS * UNIT_YEN
    return {
        "date": day.isoformat(),
        "races": v4.CORE_RACES,
        "investment_yen": investment,
        "gross_return_yen": gross,
        "profit_yen": gross - investment,
        "top1_hits": top1_hits,
        "top2_hits": top2_hits,
        "head_hits": head_hits,
        "log_loss_sum": log_loss_sum,
        "actual_prob_sum": actual_prob_sum,
        "selected": rows_out,
    }


def aggregate_days(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(rows)
    races = sum(int(row["races"]) for row in items)
    investment = sum(int(row["investment_yen"]) for row in items)
    gross = sum(int(row["gross_return_yen"]) for row in items)
    top1_hits = sum(int(row["top1_hits"]) for row in items)
    top2_hits = sum(int(row["top2_hits"]) for row in items)
    head_hits = sum(int(row["head_hits"]) for row in items)
    log_loss_sum = sum(float(row["log_loss_sum"]) for row in items)
    actual_prob_sum = sum(float(row["actual_prob_sum"]) for row in items)
    return {
        "days": len(items),
        "races": races,
        "investment_yen": investment,
        "gross_return_yen": gross,
        "profit_yen": gross - investment,
        "roi_percent": round(gross / investment * 100.0, 3) if investment else 0.0,
        "top1_hits": top1_hits,
        "top1_hit_rate_percent": round(top1_hits / races * 100.0, 3) if races else 0.0,
        "top2_hits": top2_hits,
        "top2_hit_rate_percent": round(top2_hits / races * 100.0, 3) if races else 0.0,
        "head_hits": head_hits,
        "head_hit_rate_percent": round(head_hits / races * 100.0, 3) if races else 0.0,
        "mean_log_loss": round(log_loss_sum / races, 6) if races else 0.0,
        "mean_actual_prob": round(actual_prob_sum / races, 8) if races else 0.0,
    }


def selector_metrics(
    by_selector: Mapping[str, Mapping[str, dict[str, Any]]],
    selector: str,
    days: Iterable[str],
) -> dict[str, Any]:
    return aggregate_days(
        by_selector[selector][day]
        for day in days
        if day in by_selector[selector]
    )


def choose_selector(
    by_selector: Mapping[str, Mapping[str, dict[str, Any]]],
    train_days: list[str],
) -> tuple[str, dict[str, Any]]:
    ranked: list[tuple[float, float, str, dict[str, Any]]] = []
    for selector in sorted(SELECTORS):
        metrics = selector_metrics(by_selector, selector, train_days)
        ranked.append(
            (
                -float(metrics["top2_hit_rate_percent"]),
                float(metrics["mean_log_loss"]),
                selector,
                metrics,
            )
        )
    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    _, _, selector, metrics = ranked[0]
    return selector, metrics


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_SELECTOR_CHALLENGER_VERSION={VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "POLICY=READ_ONLY ALL_SELECTORS_FROZEN_BEFORE_RESULT "
        "PAST_ONLY_WALKFORWARD_SELECTION NO_ODDS NO_REPLACEMENT NO_RETUNE",
        flush=True,
    )
    print(f"SELECTOR_COUNT={len(SELECTORS)}", flush=True)

    by_selector: dict[str, dict[str, dict[str, Any]]] = {
        selector: {} for selector in SELECTORS
    }
    day_audit: list[dict[str, Any]] = []

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

            for idx, day in enumerate(hist.daterange(START_DATE, END_DATE), 1):
                distributions, candidates = build_day_candidates(cur, day)
                frozen = freeze_selectors(distributions, candidates)
                # Result/payout access starts only after every selector is frozen.
                results = fetch_results_after_freeze(cur, day, frozen)

                evaluable: list[str] = []
                for selector, selected in frozen.items():
                    evaluated = evaluate_selector_day(
                        day=day,
                        selected=selected,
                        distributions=distributions,
                        results=results,
                    )
                    if evaluated is not None:
                        by_selector[selector][day.isoformat()] = evaluated
                        evaluable.append(selector)

                day_audit.append(
                    {
                        "date": day.isoformat(),
                        "eligible_races": len(candidates),
                        "selectors_evaluable": len(evaluable),
                        "all_selectors_evaluable": len(evaluable) == len(SELECTORS),
                    }
                )
                if idx % 30 == 0:
                    print(
                        f"PROGRESS day={day} calendar_days={idx} "
                        f"eligible={len(candidates)} all_evaluable="
                        f"{int(len(evaluable) == len(SELECTORS))}",
                        flush=True,
                    )

            conn.rollback()

    common_days = sorted(
        set.intersection(
            *[
                set(by_selector[selector])
                for selector in SELECTORS
            ]
        )
    )
    fixed_selector_comparison = []
    for selector in sorted(SELECTORS):
        fixed_selector_comparison.append(
            {
                "selector": selector,
                "metrics": selector_metrics(by_selector, selector, common_days),
            }
        )

    blocks = hist.split_blocks(common_days, BLOCKS)
    walkforward: list[dict[str, Any]] = []
    adaptive_rows: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    chosen_counts: Counter[str] = Counter()

    for idx in range(1, len(blocks)):
        train_days = sorted(set().union(*blocks[:idx]))
        test_days = sorted(blocks[idx])
        chosen, train_metrics = choose_selector(by_selector, train_days)
        chosen_counts[chosen] += 1
        chosen_test_rows = [by_selector[chosen][day] for day in test_days]
        baseline_test_rows = [
            by_selector["current_equal4"][day] for day in test_days
        ]
        adaptive_rows.extend(chosen_test_rows)
        baseline_rows.extend(baseline_test_rows)
        chosen_test = aggregate_days(chosen_test_rows)
        baseline_test = aggregate_days(baseline_test_rows)
        walkforward.append(
            {
                "test_block": idx + 1,
                "train_start": min(train_days),
                "train_end": max(train_days),
                "train_days": len(train_days),
                "test_start": min(test_days),
                "test_end": max(test_days),
                "test_days": len(test_days),
                "chosen_selector": chosen,
                "chosen_train_metrics": train_metrics,
                "chosen_test_metrics": chosen_test,
                "baseline_test_metrics": baseline_test,
                "test_delta": {
                    "top2_hit_rate_pp": round(
                        chosen_test["top2_hit_rate_percent"]
                        - baseline_test["top2_hit_rate_percent"],
                        3,
                    ),
                    "head_hit_rate_pp": round(
                        chosen_test["head_hit_rate_percent"]
                        - baseline_test["head_hit_rate_percent"],
                        3,
                    ),
                    "roi_pp": round(
                        chosen_test["roi_percent"] - baseline_test["roi_percent"], 3
                    ),
                    "mean_log_loss": round(
                        chosen_test["mean_log_loss"]
                        - baseline_test["mean_log_loss"],
                        6,
                    ),
                },
            }
        )

    adaptive = aggregate_days(adaptive_rows)
    baseline_same_test = aggregate_days(baseline_rows)
    result = {
        "contract": "v4_selector_challenger_walkforward_v1",
        "version": VERSION,
        "period": {
            "start_date": START_DATE.isoformat(),
            "end_date": END_DATE.isoformat(),
        },
        "selector_family": {
            name: list(keys) for name, keys in SELECTORS.items()
        },
        "policy": {
            "model_changed": False,
            "formal_ticket_count": 2,
            "daily_race_count": 6,
            "all_selectors_frozen_before_result": True,
            "walkforward_choice_uses_past_only": True,
            "odds_used_for_selection": False,
            "five_race_shrink": False,
            "replacement_race": False,
            "result_aware_rerank": False,
            "db_write": False,
            "production_change_allowed": False,
            "candidate_count_change_allowed": False,
            "threshold_change_allowed": False,
            "purchase_action": False,
        },
        "coverage": {
            "calendar_days": len(day_audit),
            "common_evaluable_days": len(common_days),
            "common_evaluable_races": len(common_days) * v4.CORE_RACES,
            "baseline_evaluable_days": len(by_selector["current_equal4"]),
        },
        "fixed_selector_comparison_common_days": fixed_selector_comparison,
        "walkforward_blocks": walkforward,
        "adaptive_walkforward": {
            "test_blocks": max(0, len(blocks) - 1),
            "chosen_selector_counts": dict(sorted(chosen_counts.items())),
            "challenger": adaptive,
            "baseline_same_test_days": baseline_same_test,
            "delta": {
                "top2_hit_rate_pp": round(
                    adaptive["top2_hit_rate_percent"]
                    - baseline_same_test["top2_hit_rate_percent"],
                    3,
                ),
                "head_hit_rate_pp": round(
                    adaptive["head_hit_rate_percent"]
                    - baseline_same_test["head_hit_rate_percent"],
                    3,
                ),
                "roi_pp": round(
                    adaptive["roi_percent"] - baseline_same_test["roi_percent"], 3
                ),
                "mean_log_loss": round(
                    adaptive["mean_log_loss"]
                    - baseline_same_test["mean_log_loss"],
                    6,
                ),
            },
        },
        "day_audit": day_audit,
    }
    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== COVERAGE ===", flush=True)
    print(json.dumps(result["coverage"], sort_keys=True), flush=True)
    print("=== FIXED SELECTORS ON COMMON DAYS ===", flush=True)
    for row in fixed_selector_comparison:
        m = row["metrics"]
        print(
            f"SELECTOR={row['selector']} DAYS={m['days']} RACES={m['races']} "
            f"TOP2_HIT={m['top2_hit_rate_percent']:.3f} "
            f"HEAD_HIT={m['head_hit_rate_percent']:.3f} "
            f"ROI={m['roi_percent']:.3f} LOGLOSS={m['mean_log_loss']:.6f}",
            flush=True,
        )
    print("=== ADAPTIVE WALKFORWARD ===", flush=True)
    print(json.dumps(result["adaptive_walkforward"], sort_keys=True), flush=True)
    print(f"OUTPUT_JSON={OUTPUT_JSON}", flush=True)
    print("RESULT=PASS_READ_ONLY_SELECTOR_CHALLENGER", flush=True)


if __name__ == "__main__":
    main()
