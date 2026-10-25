# -*- coding: utf-8 -*-
"""Pure/offline diagnostics for the long-history V4 replay JSON.

Consumes only sanitized rows already frozen by the read-only historical replay.
No database, network, Railway, LINE, model mutation, or purchase surface.
"""
from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

INPUT_JSON = Path(os.getenv("V4_LONG_INPUT_JSON", "v4-long-history-walkforward.json"))
OUTPUT_JSON = Path(os.getenv("V4_LONG_DIAG_JSON", "v4-long-history-selector-diagnostic.json"))
UNIT_YEN = 100
BOOTSTRAP_SAMPLES = int(os.getenv("V4_LONG_BOOTSTRAP_SAMPLES", "20000"))
BOOTSTRAP_SEED = int(os.getenv("V4_LONG_BOOTSTRAP_SEED", "20260923"))


def cumulative_metric(rows: list[dict[str, Any]], points: int) -> dict[str, Any]:
    invest = len(rows) * points * UNIT_YEN
    gross = 0
    hits = 0
    for row in rows:
        actual = row["actual_trifecta"]
        hit = actual in row["ranked_top5"][:points]
        if hit:
            gross += int(row["payout_yen"])
            hits += 1
    return {
        "races": len(rows),
        "points": points,
        "investment_yen": invest,
        "gross_return_yen": gross,
        "profit_yen": gross - invest,
        "roi_percent": round(gross / invest * 100.0, 3) if invest else 0.0,
        "hits": hits,
    }


def marginal_metric(rows: list[dict[str, Any]], rank: int) -> dict[str, Any]:
    invest = len(rows) * UNIT_YEN
    gross = 0
    hits = 0
    hit_payouts: list[int] = []
    for row in rows:
        if row["actual_trifecta"] == row["ranked_top5"][rank - 1]:
            payout = int(row["payout_yen"])
            gross += payout
            hits += 1
            hit_payouts.append(payout)
    largest = max(hit_payouts, default=0)
    return {
        "races": len(rows),
        "rank": rank,
        "investment_yen": invest,
        "gross_return_yen": gross,
        "profit_yen": gross - invest,
        "roi_percent": round(gross / invest * 100.0, 3) if invest else 0.0,
        "hits": hits,
        "largest_hit_yen": largest,
        "largest_hit_share_percent": round(largest / gross * 100.0, 3) if gross else 0.0,
    }


def _rank_half_day_stats(rows: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = {}
    for row in rows:
        day = row["date"]
        if day not in out:
            out[day] = [0, 0, 0, 0]
        bucket = out[day]
        target = 0 if int(row["daily_rank"]) <= 3 else 2
        bucket[target] += 2 * UNIT_YEN
        if row["actual_trifecta"] in row["ranked_top5"][:2]:
            bucket[target + 1] += int(row["payout_yen"])
    return {d: ((v[0], v[1]), (v[2], v[3])) for d, v in out.items()}


def bootstrap_rank_half(rows: list[dict[str, Any]]) -> dict[str, Any]:
    day_stats = _rank_half_day_stats(rows)
    days = sorted(day_stats)
    if not days:
        return {"samples": 0, "ci95_pp": [0.0, 0.0], "positive_share_percent": 0.0}
    rnd = random.Random(BOOTSTRAP_SEED)
    diffs: list[float] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        hi_i = hi_g = lo_i = lo_g = 0
        for _j in days:
            d = days[rnd.randrange(len(days))]
            (a, b), (c, e) = day_stats[d]
            hi_i += a
            hi_g += b
            lo_i += c
            lo_g += e
        hi_roi = hi_g / hi_i * 100.0 if hi_i else 0.0
        lo_roi = lo_g / lo_i * 100.0 if lo_i else 0.0
        diffs.append(hi_roi - lo_roi)
    diffs.sort()
    n = len(diffs)
    lo = diffs[int(0.025 * (n - 1))]
    hi = diffs[int(0.975 * (n - 1))]
    positive = sum(x > 0 for x in diffs) / n * 100.0
    return {
        "samples": n,
        "seed": BOOTSTRAP_SEED,
        "ci95_pp": [round(lo, 3), round(hi, 3)],
        "positive_share_percent": round(positive, 3),
    }


def main() -> None:
    payload = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    rows = list(payload.get("evaluated_race_records") or [])
    rows.sort(key=lambda r: (r["date"], int(r["daily_rank"]), r["race_id"]))

    per_daily_rank = []
    for daily_rank in range(1, 7):
        subset = [r for r in rows if int(r["daily_rank"]) == daily_rank]
        per_daily_rank.append({
            "daily_rank": daily_rank,
            "formal_2pt": cumulative_metric(subset, 2),
            "third_ticket_marginal": marginal_metric(subset, 3),
        })

    top_half = [r for r in rows if int(r["daily_rank"]) <= 3]
    bottom_half = [r for r in rows if int(r["daily_rank"]) >= 4]

    months: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        months[row["date"][:7]].append(row)
    monthly = []
    for month, mrows in sorted(months.items()):
        monthly.append({
            "month": month,
            "races": len(mrows),
            "formal_2pt": cumulative_metric(mrows, 2),
            "third_ticket_marginal": marginal_metric(mrows, 3),
        })

    result = {
        "contract": "v4_long_history_selector_diagnostic_v1",
        "source_contract": payload.get("contract"),
        "source_period": payload.get("period"),
        "coverage": payload.get("coverage"),
        "selected_feature_coverage": payload.get("selected_feature_coverage"),
        "overall": {
            "formal_2pt": cumulative_metric(rows, 2),
            "shadow_3pt": cumulative_metric(rows, 3),
            "third_ticket_marginal": marginal_metric(rows, 3),
        },
        "per_daily_rank": per_daily_rank,
        "rank_half": {
            "rank_1_3_formal_2pt": cumulative_metric(top_half, 2),
            "rank_4_6_formal_2pt": cumulative_metric(bottom_half, 2),
            "bootstrap_difference_pp": bootstrap_rank_half(rows),
        },
        "monthly": monthly,
        "safety": {
            "historical_hypothesis_only": True,
            "production_change_allowed": False,
            "candidate_count_change_allowed": False,
            "race_score_gate_allowed": False,
            "threshold_change_allowed": False,
            "rerank_allowed": False,
            "purchase_action": False,
        },
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("=== LONG HISTORY SELECTOR DIAGNOSTIC ===")
    print(json.dumps(result["overall"], ensure_ascii=False, sort_keys=True))
    print(json.dumps(result["rank_half"], ensure_ascii=False, sort_keys=True))
    print(f"OUTPUT_JSON={OUTPUT_JSON}")
    print("RESULT=PASS_OFFLINE_DIAGNOSTIC")


if __name__ == "__main__":
    main()
