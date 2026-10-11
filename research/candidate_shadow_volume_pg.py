# -*- coding: utf-8 -*-
"""Read-only pre-result shadow candidate volume report.

This report intentionally reads ONLY pre-result identifiers from
v2_candidate_filter_shadow. It does not select hit/payout/result fields and is
not an economics or promotion report.

Goal:
- measure unique race volume available in existing shadow rules;
- compare observed volume with the practical 1-3 races/day notification context;
- avoid confusing rule rows with unique races;
- provide volume evidence without changing Production or looking at outcomes.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Sequence


DEFAULT_RULES = ("S01", "S02", "S03", "S04", "S05", "N02")


def _force_read_only_pgoptions() -> None:
    current = os.environ.get("PGOPTIONS", "").strip()
    guard = "-c default_transaction_read_only=on"
    if guard not in current:
        os.environ["PGOPTIONS"] = f"{current} {guard}".strip()


def normalize_rules(raw: str | None) -> List[str]:
    if not raw:
        return list(DEFAULT_RULES)
    out: List[str] = []
    seen = set()
    for token in raw.replace(";", ",").split(","):
        rule = token.strip().upper()
        if not rule or rule in seen:
            continue
        seen.add(rule)
        out.append(rule)
    return out


def aggregate_shadow_volume(
    rows: Iterable[Mapping[str, Any]],
    rules: Sequence[str],
) -> Dict[str, Any]:
    rules_set = {str(x).upper() for x in rules}
    by_date_rows: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)

    for row in rows:
        rule = str(row.get("rule_id") or "").upper()
        if rule not in rules_set:
            continue
        race_date = str(row.get("race_date") or "")
        race_id = str(row.get("race_id") or "")
        if not race_date or not race_id:
            continue
        by_date_rows[race_date].append(row)

    daily: Dict[str, Any] = {}
    totals = Counter()
    all_unique_races = set()

    for race_date in sorted(by_date_rows):
        day_rows = by_date_rows[race_date]
        unique_races = {str(r.get("race_id")) for r in day_rows}
        all_unique_races.update((race_date, rid) for rid in unique_races)

        per_rule: Dict[str, Any] = {}
        for rule in rules:
            rule_rows = [
                r for r in day_rows
                if str(r.get("rule_id") or "").upper() == rule
            ]
            rule_races = {str(r.get("race_id")) for r in rule_rows}
            per_rule[rule] = {
                "rows": len(rule_rows),
                "unique_races": len(rule_races),
            }
            totals[f"{rule}_rows"] += len(rule_rows)
            totals[f"{rule}_unique_race_days"] += len(rule_races)

        windows = Counter(str(r.get("window_name") or "unknown") for r in day_rows)
        daily[race_date] = {
            "rows": len(day_rows),
            "unique_races": len(unique_races),
            "within_1_to_3_race_context": 1 <= len(unique_races) <= 3,
            "above_3_race_context": len(unique_races) > 3,
            "below_1_race_context": len(unique_races) < 1,
            "windows": dict(sorted(windows.items())),
            "per_rule": per_rule,
        }
        totals["rows"] += len(day_rows)
        totals["unique_race_days"] += len(unique_races)
        totals["days"] += 1
        if 1 <= len(unique_races) <= 3:
            totals["days_within_1_to_3"] += 1
        elif len(unique_races) > 3:
            totals["days_above_3"] += 1
        else:
            totals["days_below_1"] += 1

    return {
        "daily": daily,
        "totals": dict(sorted(totals.items())),
        "unique_races_across_dates": len(all_unique_races),
    }


def fetch_shadow_rows(
    start_date: str,
    end_date: str,
    rules: Sequence[str],
) -> List[Dict[str, Any]]:
    _force_read_only_pgoptions()
    from db_pg import fetch_all

    if not rules:
        return []

    placeholders = ",".join(["%s"] * len(rules))
    sql = f"""
        select
            race_date,
            race_id,
            window_name,
            rule_id,
            snapshot_at
        from v2_candidate_filter_shadow
        where race_date between %s and %s
          and upper(rule_id) in ({placeholders})
        order by race_date asc, race_id asc, rule_id asc
    """
    params = [start_date, end_date, *rules]
    return fetch_all(sql, tuple(params))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=os.environ.get("START_DATE"))
    parser.add_argument("--end-date", default=os.environ.get("END_DATE"))
    parser.add_argument("--rules", default=os.environ.get("RULE_IDS"))
    args = parser.parse_args()

    if not args.start_date or not args.end_date:
        raise SystemExit("START_DATE and END_DATE are required")

    rules = normalize_rules(args.rules)
    rows = fetch_shadow_rows(args.start_date, args.end_date, rules)
    summary = aggregate_shadow_volume(rows, rules)

    output = {
        "contract": "CANDIDATE_SHADOW_VOLUME_PRE_RESULT_V1",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "rules": rules,
        "selected_columns": [
            "race_date",
            "race_id",
            "window_name",
            "rule_id",
            "snapshot_at",
        ],
        "result_fields_read": False,
        "economics_claim": False,
        "promotion_claim": False,
        "operational_observation_target_races_per_day": {"min": 1, "max": 3},
        "target_is_not_a_selector_gate": True,
        "no_threshold_relaxation": True,
        "diagnostic_only": True,
        "purchase_action": False,
        "line_send": False,
        "db_write": False,
        **summary,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
