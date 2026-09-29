# -*- coding: utf-8 -*-
from research.candidate_shadow_volume_pg import (
    aggregate_shadow_volume,
    normalize_rules,
)


def test_normalize_rules_dedupes_and_uppercases():
    assert normalize_rules("s03,S03; s05") == ["S03", "S05"]


def test_aggregate_counts_unique_races_not_rule_rows():
    rows = [
        {"race_date": "2026-09-29", "race_id": "A", "window_name": "day", "rule_id": "S03"},
        {"race_date": "2026-09-29", "race_id": "A", "window_name": "day", "rule_id": "S05"},
        {"race_date": "2026-09-29", "race_id": "B", "window_name": "night", "rule_id": "S03"},
    ]
    out = aggregate_shadow_volume(rows, ["S03", "S05"])
    day = out["daily"]["2026-09-29"]
    assert day["rows"] == 3
    assert day["unique_races"] == 2
    assert day["within_1_to_3_race_context"] is True
    assert day["per_rule"]["S03"]["unique_races"] == 2
    assert day["per_rule"]["S05"]["unique_races"] == 1


def test_aggregate_filters_unrequested_rules():
    rows = [
        {"race_date": "2026-09-29", "race_id": "A", "window_name": "day", "rule_id": "S03"},
        {"race_date": "2026-09-29", "race_id": "B", "window_name": "day", "rule_id": "S02"},
    ]
    out = aggregate_shadow_volume(rows, ["S03"])
    day = out["daily"]["2026-09-29"]
    assert day["rows"] == 1
    assert day["unique_races"] == 1
    assert out["totals"]["S03_rows"] == 1


def test_above_three_is_descriptive_only():
    rows = [
        {"race_date": "2026-09-29", "race_id": rid, "window_name": "day", "rule_id": "S03"}
        for rid in ["A", "B", "C", "D"]
    ]
    out = aggregate_shadow_volume(rows, ["S03"])
    day = out["daily"]["2026-09-29"]
    assert day["above_3_race_context"] is True
    assert day["within_1_to_3_race_context"] is False
