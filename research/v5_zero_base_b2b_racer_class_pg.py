# -*- coding: utf-8 -*-
"""
V5 zero-base B2B backtest: racer class only.

Feature
-------
Only v2_race_entries.racer_class is used.

Walk-forward estimator (no tuning):
- For each target day, estimate each class's historical win rate from PREVIOUS
  DAYS ONLY: (wins + alpha) / (starts + 2*alpha), alpha=1.
- Convert the six class scores within each race to probabilities by simple
  normalization.
- Score the whole day before adding that day's starts/wins to history.

No lane, national/local rates, ST, motor, exhibition, venue, weather, odds,
selector, or V4 prediction logic is used.

Defaults:
    START_DATE=2025-07-01
    END_DATE=2026-10-05

Safety:
- DB read-only.
- No Production/LINE/purchase/stake/model/settings changes.
"""

from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any

from db_pg import fetch_all

VERSION = "2026-10-08-v1"
START_DATE = os.getenv("START_DATE", "2025-07-01")
END_DATE = os.getenv("END_DATE", "2026-10-05")
ALPHA = 1.0
EPS = 1e-15

B0_LOGLOSS = -math.log(1.0 / 6.0)
B0_BRIER_SUM = (1.0 - 1.0 / 6.0) ** 2 + 5.0 * ((1.0 / 6.0) ** 2)


def _iso_date(v: Any) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _table_columns(table: str) -> set[str]:
    rows = fetch_all(
        """
        select column_name
        from information_schema.columns
        where table_schema='public' and table_name=%s
        """,
        (table,),
    )
    return {str(r["column_name"]) for r in rows}


def _winner_expr(result_cols: set[str]) -> str:
    if "first_lane" in result_cols:
        return "rs.first_lane::int"
    if "trifecta_ticket" in result_cols:
        return (
            "nullif(substring(regexp_replace(rs.trifecta_ticket::text,"
            " '[^0-9]', '', 'g') from 1 for 1), '')::int"
        )
    raise RuntimeError("v2_results has neither first_lane nor trifecta_ticket")


def load_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result_cols = _table_columns("v2_results")
    entry_cols = _table_columns("v2_race_entries")
    if "racer_class" not in entry_cols:
        raise RuntimeError("v2_race_entries.racer_class is unavailable")

    winner = _winner_expr(result_cols)
    filters = [
        "r.race_date >= %s",
        "r.race_date <= %s",
        f"({winner}) between 1 and 6",
    ]
    if "result_status" in result_cols:
        filters.append("coalesce(rs.result_status,'official') = 'official'")
    if "race_status" in result_cols:
        filters.append("coalesce(rs.race_status,'official') = 'official'")

    results = fetch_all(
        f"""
        select r.race_id, r.race_date, {winner} as winner_lane
        from v2_races r
        join v2_results rs on rs.race_id=r.race_id
        where {' and '.join(filters)}
        order by r.race_date, r.race_id
        """,
        (START_DATE, END_DATE),
    )

    entries = fetch_all(
        """
        select e.race_id, r.race_date, e.lane, e.racer_class
        from v2_race_entries e
        join v2_races r on r.race_id=e.race_id
        where r.race_date >= %s
          and r.race_date <= %s
        order by r.race_date, e.race_id, e.lane
        """,
        (START_DATE, END_DATE),
    )
    return results, entries


def clean_class(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip().upper()
    return s or None


def main() -> None:
    results, entries = load_data()
    if not results:
        raise RuntimeError("B2B: no completed races")

    winner_by_race = {str(r["race_id"]): int(r["winner_lane"]) for r in results}
    date_by_race = {str(r["race_id"]): _iso_date(r["race_date"]) for r in results}

    entries_by_race: defaultdict[str, dict[int, str]] = defaultdict(dict)
    invalid_entry_rows = 0
    observed_classes: Counter[str] = Counter()

    for e in entries:
        rid = str(e["race_id"])
        if rid not in winner_by_race:
            continue
        try:
            lane = int(e["lane"])
        except (TypeError, ValueError):
            invalid_entry_rows += 1
            continue
        cls = clean_class(e.get("racer_class"))
        if not (1 <= lane <= 6) or cls is None:
            invalid_entry_rows += 1
            continue
        entries_by_race[rid][lane] = cls
        observed_classes[cls] += 1

    races_by_day: defaultdict[str, list[str]] = defaultdict(list)
    skipped_incomplete6 = 0
    for rid in winner_by_race:
        lane_classes = entries_by_race.get(rid, {})
        if len(lane_classes) == 6 and all(lane in lane_classes for lane in range(1, 7)):
            races_by_day[date_by_race[rid]].append(rid)
        else:
            skipped_incomplete6 += 1

    class_starts: Counter[str] = Counter()
    class_wins: Counter[str] = Counter()

    logloss_total = 0.0
    brier_total = 0.0
    top1_hits = 0
    unique_top_count = 0
    scored = 0

    first_day_scores = None
    last_day_scores = None

    for ds in sorted(races_by_day):
        # Freeze history for the whole day.
        classes_today = {
            entries_by_race[rid][lane]
            for rid in races_by_day[ds]
            for lane in range(1, 7)
        }
        scores = {}
        for cls in classes_today:
            scores[cls] = (class_wins[cls] + ALPHA) / (
                class_starts[cls] + 2.0 * ALPHA
            )

        if first_day_scores is None:
            first_day_scores = dict(sorted(scores.items()))
        last_day_scores = dict(sorted(scores.items()))

        day_starts: Counter[str] = Counter()
        day_wins: Counter[str] = Counter()

        for rid in races_by_day[ds]:
            winner = winner_by_race[rid]
            lane_classes = entries_by_race[rid]
            raw = [scores[lane_classes[lane]] for lane in range(1, 7)]
            total = sum(raw)
            if total <= 0:
                raise RuntimeError("B2B: nonpositive class-score total")
            probs = [x / total for x in raw]

            logloss_total += -math.log(max(probs[winner - 1], EPS))
            y = [0.0] * 6
            y[winner - 1] = 1.0
            brier_total += sum((probs[i] - y[i]) ** 2 for i in range(6))

            max_p = max(probs)
            top_lanes = [i + 1 for i, p in enumerate(probs) if abs(p - max_p) < 1e-15]
            if len(top_lanes) == 1:
                unique_top_count += 1
                if top_lanes[0] == winner:
                    top1_hits += 1

            for lane in range(1, 7):
                day_starts[lane_classes[lane]] += 1
            day_wins[lane_classes[winner]] += 1
            scored += 1

        class_starts.update(day_starts)
        class_wins.update(day_wins)

    if scored == 0:
        raise RuntimeError("B2B: zero scoreable races")

    logloss = logloss_total / scored
    brier_sum = brier_total / scored

    report = {
        "contract": "V5_ZERO_BASE_B2B_RACER_CLASS_ONLY_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "feature_family": {
            "name": "racer_class_only",
            "inputs": ["v2_race_entries.racer_class"],
            "lane_number_as_predictor": False,
            "national_win_rate_used": False,
            "national_place_rate_used": False,
            "v4_prediction_logic_used": False,
            "odds_used": False,
            "selector_used": False,
        },
        "estimator": {
            "method": "previous-days class empirical win rate then within-race normalization",
            "laplace_alpha": ALPHA,
            "same_day_results_used_for_same_day_prediction": False,
            "parameter_search": False,
            "learned_coefficients": False,
        },
        "coverage": {
            "completed_result_races": len(results),
            "scored_complete6_races": scored,
            "coverage_pct": 100.0 * scored / len(results),
            "skipped_incomplete6": skipped_incomplete6,
            "invalid_entry_rows": invalid_entry_rows,
            "observed_class_entry_counts": dict(sorted(observed_classes.items())),
        },
        "metrics": {
            "logloss": logloss,
            "brier_multiclass_sum": brier_sum,
            "brier_per_class": brier_sum / 6.0,
            "top1_accuracy_unique_only": (
                top1_hits / unique_top_count if unique_top_count else None
            ),
            "unique_top_races": unique_top_count,
            "b0_logloss_same_subset": B0_LOGLOSS,
            "b0_brier_multiclass_sum_same_subset": B0_BRIER_SUM,
            "delta_logloss_vs_b0": logloss - B0_LOGLOSS,
            "delta_brier_sum_vs_b0": brier_sum - B0_BRIER_SUM,
            "improved_logloss_vs_b0": logloss < B0_LOGLOSS,
            "improved_brier_vs_b0": brier_sum < B0_BRIER_SUM,
        },
        "class_history_audit": {
            "final_starts": dict(sorted(class_starts.items())),
            "final_wins": dict(sorted(class_wins.items())),
            "first_target_day_scores": first_day_scores,
            "last_target_day_scores": last_day_scores,
        },
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }

    print("V5_B2B_RACER_CLASS_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
