# -*- coding: utf-8 -*-
"""Candidate Discovery V1 research audit (READ ONLY).

Goal
----
Build a candidate system that is not gated by expected value or odds bands.
Selection uses only race-card/model structure:

- top-ticket model probability
- separation from the second-ranked ticket
- probability-distribution concentration

The three signals are converted to within-day percentile ranks and averaged with
fixed equal weight. One ticket is chosen per race, then the best N races of the
day are retained. Fixed candidate-count views (6/9/12/18 per day) are reported;
12/day is the predeclared provisional primary view.

Two frozen probability variants are compared:
- BASE: current v24-style race-card model, Motor2 neutral (33.0)
- MOTOR2: same model with fixed Motor2 weight 0.06

Odds are never read by this script and therefore cannot affect candidate
eligibility or ordering. Official trifecta results/payouts are read only after
selection to evaluate realized hit rate / ROI. Existing S01-S05 shadow tickets
are read only as a legacy reference and optional carryover comparison.

No DB write, LINE send, BUY action, Production selector change, or Railway
configuration change is performed.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

JST = ZoneInfo("Asia/Tokyo")
START_DATE = os.getenv("CANDIDATE_DISCOVERY_START", "2025-07-01").strip()
END_DATE = os.getenv(
    "CANDIDATE_DISCOVERY_END",
    (datetime.now(JST).date() - timedelta(days=1)).isoformat(),
).strip()
OUTPUT = Path(os.getenv("CANDIDATE_DISCOVERY_OUTPUT", "candidate-discovery-v1.json"))
UNIT_YEN = max(1, int(os.getenv("CANDIDATE_DISCOVERY_UNIT_YEN", "100")))
DEFAULT_DAILY_CAP = 12
DAILY_CAPS = tuple(
    sorted(
        {
            int(x.strip())
            for x in os.getenv("CANDIDATE_DISCOVERY_DAILY_CAPS", "6,9,12,18").split(",")
            if x.strip()
        }
    )
)
if DEFAULT_DAILY_CAP not in DAILY_CAPS:
    raise RuntimeError("CANDIDATE_DISCOVERY_DAILY_CAPS must include 12")

PROB_TEMP = 2.20
MOTOR2_WEIGHT = 0.06
VARIANTS = {"BASE": 0.0, "MOTOR2": MOTOR2_WEIGHT}
CLASS_WEIGHT = {1: 0.15, 2: 0.55, 3: 1.15, 4: 1.55}
VENUE_COURSE_BIAS = {
    "01": {1: 2.762, 2: 2.747, 3: 3.385, 4: 4.070, 5: 3.537, 6: 2.343},
    "06": {1: 2.932, 2: 3.401, 3: 3.571, 4: 3.195, 5: 2.694, 6: 2.403},
    "12": {1: 3.249, 2: 3.344, 3: 2.957, 4: 2.824, 5: 2.313, 6: 1.553},
    "18": {1: 3.509, 2: 3.116, 3: 2.908, 4: 2.648, 5: 1.380, 6: 1.355},
    "24": {1: 3.561, 2: 2.880, 3: 2.659, 4: 2.267, 5: 2.049, 6: 1.314},
}
DEFAULT_COURSE_BIAS = {1: 3.20, 2: 3.10, 3: 3.10, 4: 3.00, 5: 2.40, 6: 1.80}
ALL_LANES = {1, 2, 3, 4, 5, 6}
LEGACY_RULES = {"S01", "S02", "S03", "S04", "S05"}


def sf(value: Any, default: float | None = 0.0) -> float | None:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def si(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def norm_ticket(value: Any) -> str:
    parts = re.findall(r"[1-6]", str(value or ""))
    if len(parts) < 3:
        return ""
    lanes = [int(x) for x in parts[:3]]
    if len(set(lanes)) != 3:
        return ""
    return f"{lanes[0]}-{lanes[1]}-{lanes[2]}"


def valid_motor2(value: Any) -> float | None:
    x = sf(value, None)
    if x is None or not (0.0 <= x <= 100.0):
        return None
    return float(x)


def lane_raw_strength(entry: dict[str, Any], lane: int, venue: str, motor_weight: float) -> float:
    racer_class = si(entry.get("racer_class"), 2)
    class_weight = CLASS_WEIGHT.get(racer_class, 0.55)
    win_rate = sf(entry.get("national_win_rate"), 0.0) or 0.0
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    avg_st = sf(entry.get("avg_st"), 0.18)
    nat2 = 32.0 if nat2 is None else nat2
    loc2 = 30.0 if loc2 is None else loc2
    avg_st = 0.18 if avg_st is None else avg_st
    motor2 = valid_motor2(entry.get("motor_place2_rate"))
    motor2 = 33.0 if motor2 is None else motor2
    course_bias = VENUE_COURSE_BIAS.get(venue, DEFAULT_COURSE_BIAS).get(
        lane, DEFAULT_COURSE_BIAS[lane]
    )
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))
    return (
        class_weight
        + win_rate * 0.16
        + (nat2 / 100.0) * 0.90
        + (loc2 / 100.0) * 0.55
        + (motor2 / 100.0) * motor_weight
        + (34.0 / 100.0) * 0.25
        + st_score * 0.35
        + course_bias * 0.22
    )


def ticket_probabilities(entries: list[dict[str, Any]], venue: str, motor_weight: float) -> dict[str, float]:
    by_lane = {si(row.get("lane"), 0): row for row in entries}
    if set(by_lane) != ALL_LANES:
        raise ValueError("complete six-lane entries required")
    raw = {
        lane: lane_raw_strength(by_lane[lane], lane, venue, motor_weight)
        for lane in range(1, 7)
    }
    weights = {lane: math.exp(raw[lane] / PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    out: dict[str, float] = {}
    for first in range(1, 7):
        p_first = weights[first] / total
        remain_second = total - weights[first]
        for second in range(1, 7):
            if second == first:
                continue
            p_second = weights[second] / remain_second
            remain_third = remain_second - weights[second]
            for third in range(1, 7):
                if third in (first, second):
                    continue
                out[f"{first}-{second}-{third}"] = (
                    p_first * p_second * (weights[third] / remain_third)
                )
    return out


def race_candidate_metrics(
    race: dict[str, Any],
    entries: list[dict[str, Any]],
    motor_weight: float,
) -> dict[str, Any]:
    venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
    probs = ticket_probabilities(entries, venue, motor_weight)
    ranked = sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))
    ticket, p1 = ranked[0]
    p2 = ranked[1][1]
    entropy = -sum(p * math.log(p) for p in probs.values()) / math.log(len(probs))
    concentration = 1.0 - entropy
    return {
        "race_id": str(race.get("race_id") or ""),
        "race_date": str(race.get("race_date") or "")[:10],
        "venue_id": venue,
        "race_no": si(race.get("race_no"), 0),
        "ticket": ticket,
        "p1": float(p1),
        "margin": float(p1 - p2),
        "ratio": float(p1 / p2) if p2 > 0 else None,
        "concentration": float(concentration),
    }


def _percentile_rank(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    ordered = sorted(
        rows,
        key=lambda row: (-float(row[key]), str(row["race_id"])),
    )
    n = len(ordered)
    if n <= 1:
        return {str(row["race_id"]): 1.0 for row in ordered}
    return {
        str(row["race_id"]): 1.0 - (idx / (n - 1))
        for idx, row in enumerate(ordered)
    }


def rank_day(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank races without odds/EV. Equal-weight percentile consensus only."""
    if not rows:
        return []
    p1_rank = _percentile_rank(rows, "p1")
    margin_rank = _percentile_rank(rows, "margin")
    concentration_rank = _percentile_rank(rows, "concentration")
    ranked: list[dict[str, Any]] = []
    for row in rows:
        race_id = str(row["race_id"])
        item = dict(row)
        item["confidence_score"] = (
            p1_rank[race_id] + margin_rank[race_id] + concentration_rank[race_id]
        ) / 3.0
        ranked.append(item)
    ranked.sort(
        key=lambda row: (
            -float(row["confidence_score"]),
            -float(row["p1"]),
            -float(row["margin"]),
            str(row["race_id"]),
        )
    )
    for idx, row in enumerate(ranked, start=1):
        row["daily_rank"] = idx
    return ranked


def _new_stat() -> dict[str, Any]:
    return {
        "selected": 0,
        "evaluated": 0,
        "pending": 0,
        "hits": 0,
        "investment_yen": 0,
        "return_yen": 0,
        "profit_yen": 0,
        "roi_pct": None,
        "hit_rate_pct": None,
        "max_losing_streak": 0,
    }


def evaluate_rows(
    rows: list[dict[str, Any]],
    results: dict[str, tuple[str, int]],
) -> dict[str, Any]:
    stat = _new_stat()
    stat["selected"] = len(rows)
    losing = 0
    max_losing = 0
    for row in sorted(
        rows,
        key=lambda x: (
            str(x.get("race_date") or ""),
            str(x.get("venue_id") or ""),
            si(x.get("race_no"), 0),
            str(x.get("ticket") or ""),
        ),
    ):
        race_id = str(row.get("race_id") or "")
        result = results.get(race_id)
        if result is None:
            stat["pending"] += 1
            continue
        win_ticket, payout = result
        stat["evaluated"] += 1
        stat["investment_yen"] += UNIT_YEN
        hit = norm_ticket(row.get("ticket")) == win_ticket
        if hit:
            stat["hits"] += 1
            stat["return_yen"] += payout
            losing = 0
        else:
            losing += 1
            max_losing = max(max_losing, losing)
    stat["profit_yen"] = stat["return_yen"] - stat["investment_yen"]
    if stat["investment_yen"]:
        stat["roi_pct"] = round(stat["return_yen"] / stat["investment_yen"] * 100.0, 3)
    if stat["evaluated"]:
        stat["hit_rate_pct"] = round(stat["hits"] / stat["evaluated"] * 100.0, 3)
    stat["max_losing_streak"] = max_losing
    return stat


def monthly_stats(rows: list[dict[str, Any]], results: dict[str, tuple[str, int]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ds = str(row.get("race_date") or "")
        grouped[ds[:7]].append(row)
    return {month: evaluate_rows(items, results) for month, items in sorted(grouped.items())}


def _table_exists(cur: psycopg.Cursor[Any], name: str) -> bool:
    cur.execute("select to_regclass(%s) is not null as ok", (name,))
    row = cur.fetchone()
    return bool(row and row["ok"])


def load_data(conn: psycopg.Connection[Any]) -> tuple[
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, tuple[str, int]],
    list[dict[str, Any]],
]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no
              from v2_races
             where race_date >= %s and race_date <= %s
             order by race_date,venue_id,race_no,race_id
            """,
            (START_DATE, END_DATE),
        )
        races = [dict(row) for row in cur.fetchall()]

        cur.execute(
            """
            select e.race_id,e.lane,e.racer_class,e.national_win_rate,
                   e.national_place2_rate,e.local_place2_rate,e.avg_st,
                   e.motor_place2_rate
              from v2_race_entries e
              join v2_races r on r.race_id=e.race_id
             where r.race_date >= %s and r.race_date <= %s
             order by e.race_id,e.lane
            """,
            (START_DATE, END_DATE),
        )
        entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries_by[str(row["race_id"])].append(dict(row))

        cur.execute(
            """
            select r.race_id,r.trifecta_ticket,r.trifecta_payout_yen
              from v2_results r
              join v2_races rr on rr.race_id=r.race_id
             where rr.race_date >= %s and rr.race_date <= %s
               and r.result_status='official'
               and r.race_status='official'
               and r.trifecta_ticket is not null
               and r.trifecta_payout_yen > 0
             order by r.race_id
            """,
            (START_DATE, END_DATE),
        )
        results: dict[str, tuple[str, int]] = {}
        for row in cur.fetchall():
            ticket = norm_ticket(row["trifecta_ticket"])
            payout = si(row["trifecta_payout_yen"], 0)
            if ticket and payout > 0:
                results[str(row["race_id"])] = (ticket, payout)

        legacy_rows: list[dict[str, Any]] = []
        if _table_exists(cur, "v2_candidate_filter_shadow"):
            cur.execute(
                """
                select race_id,race_date,venue_id,race_no,rule_id,ticket
                  from v2_candidate_filter_shadow
                 where race_date >= %s and race_date <= %s
                   and rule_id = any(%s)
                 order by race_date,venue_id,race_no,rule_id
                """,
                (START_DATE, END_DATE, sorted(LEGACY_RULES)),
            )
            for row in cur.fetchall():
                ticket = norm_ticket(row["ticket"])
                if ticket:
                    item = dict(row)
                    item["ticket"] = ticket
                    legacy_rows.append(item)

    return races, entries_by, results, legacy_rows


def _dedupe_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("race_id") or ""), norm_ticket(row.get("ticket")))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _legacy_summary(
    selected: list[dict[str, Any]],
    legacy_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    legacy = _dedupe_pairs(legacy_rows)
    selected_pairs = {
        (str(row["race_id"]), norm_ticket(row["ticket"])) for row in selected
    }
    legacy_pairs = {(str(row["race_id"]), norm_ticket(row["ticket"])) for row in legacy}
    covered = legacy_pairs & selected_pairs
    legacy_races = {race_id for race_id, _ in legacy_pairs}
    selected_races = {race_id for race_id, _ in selected_pairs}
    race_covered = legacy_races & selected_races
    return {
        "legacy_unique_ticket_rows": len(legacy_pairs),
        "legacy_unique_races": len(legacy_races),
        "exact_ticket_covered": len(covered),
        "exact_ticket_coverage_pct": round(len(covered) / len(legacy_pairs) * 100.0, 3)
        if legacy_pairs
        else None,
        "race_covered": len(race_covered),
        "race_coverage_pct": round(len(race_covered) / len(legacy_races) * 100.0, 3)
        if legacy_races
        else None,
    }


def _combined_legacy_window(
    selected: list[dict[str, Any]],
    legacy_rows: list[dict[str, Any]],
    results: dict[str, tuple[str, int]],
) -> dict[str, Any] | None:
    if not legacy_rows:
        return None
    legacy = _dedupe_pairs(legacy_rows)
    dates = sorted(str(row.get("race_date") or "")[:10] for row in legacy if row.get("race_date"))
    if not dates:
        return None
    first, last = dates[0], dates[-1]
    main_window = [
        row for row in selected if first <= str(row.get("race_date") or "")[:10] <= last
    ]
    union = _dedupe_pairs(main_window + legacy)
    return {
        "period": f"{first}..{last}",
        "discovery_rows": len(_dedupe_pairs(main_window)),
        "legacy_rows": len(legacy),
        "union_rows": len(union),
        "evaluation": evaluate_rows(union, results),
        "monthly": monthly_stats(union, results),
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    if START_DATE > END_DATE:
        raise RuntimeError("invalid date range")

    print("CANDIDATE_DISCOVERY_V1_MODE=read_only_odds_independent_selection", flush=True)
    print(f"CANDIDATE_DISCOVERY_V1_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "CANDIDATE_DISCOVERY_V1_SELECTION_SIGNALS=p1,margin,concentration equal_weight_percentile_consensus",
        flush=True,
    )
    print(
        f"CANDIDATE_DISCOVERY_V1_DAILY_CAPS={','.join(str(x) for x in DAILY_CAPS)} primary:{DEFAULT_DAILY_CAP}",
        flush=True,
    )
    print(f"CANDIDATE_DISCOVERY_V1_MOTOR2_WEIGHT={MOTOR2_WEIGHT:.2f}", flush=True)
    print("CANDIDATE_DISCOVERY_V1_ODDS_READ=0 EV_FILTER=0 ODDS_FILTER=0", flush=True)
    print("CANDIDATE_DISCOVERY_V1_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        races, entries_by, results, legacy_rows = load_data(conn)
        conn.rollback()

    audit = {
        "races_total": len(races),
        "results_official": len(results),
        "legacy_rows_raw": len(legacy_rows),
        "skipped_incomplete_entries": 0,
        "evaluable_races": 0,
    }
    by_variant_day: dict[str, dict[str, list[dict[str, Any]]]] = {
        name: defaultdict(list) for name in VARIANTS
    }

    for race in races:
        race_id = str(race.get("race_id") or "")
        entries = entries_by.get(race_id, [])
        if len(entries) != 6 or {si(row.get("lane"), 0) for row in entries} != ALL_LANES:
            audit["skipped_incomplete_entries"] += 1
            continue
        race_date = str(race.get("race_date") or "")[:10]
        for name, motor_weight in VARIANTS.items():
            row = race_candidate_metrics(race, entries, motor_weight)
            row["variant"] = name
            by_variant_day[name][race_date].append(row)
        audit["evaluable_races"] += 1

    all_reports: dict[str, Any] = {}
    primary_rows_by_variant: dict[str, list[dict[str, Any]]] = {}
    for variant in VARIANTS:
        ranked_days = {
            ds: rank_day(rows) for ds, rows in sorted(by_variant_day[variant].items())
        }
        cap_reports: dict[str, Any] = {}
        for cap in DAILY_CAPS:
            selected: list[dict[str, Any]] = []
            daily_counts: list[int] = []
            for ds, rows in ranked_days.items():
                take = rows[: min(cap, len(rows))]
                selected.extend(take)
                daily_counts.append(len(take))
            evaluation = evaluate_rows(selected, results)
            cap_reports[str(cap)] = {
                "days": len(daily_counts),
                "mean_candidates_per_day": round(mean(daily_counts), 3) if daily_counts else 0.0,
                "median_candidates_per_day": float(median(daily_counts)) if daily_counts else 0.0,
                "min_candidates_per_day": min(daily_counts) if daily_counts else 0,
                "max_candidates_per_day": max(daily_counts) if daily_counts else 0,
                "evaluation": evaluation,
                "monthly": monthly_stats(selected, results),
                "legacy_overlap": _legacy_summary(selected, legacy_rows),
            }
            if cap == DEFAULT_DAILY_CAP:
                primary_rows_by_variant[variant] = selected
            print(
                f"CANDIDATE_DISCOVERY_V1_VIEW={variant}/TOP{cap} "
                f"selected:{evaluation['selected']} evaluated:{evaluation['evaluated']} "
                f"hits:{evaluation['hits']} roi:{evaluation['roi_pct']} "
                f"avg_day:{cap_reports[str(cap)]['mean_candidates_per_day']} "
                f"max_lose:{evaluation['max_losing_streak']}",
                flush=True,
            )
        all_reports[variant] = {"motor_weight": VARIANTS[variant], "caps": cap_reports}

    combined: dict[str, Any] = {}
    for variant, selected in primary_rows_by_variant.items():
        combined[variant] = _combined_legacy_window(selected, legacy_rows, results)
        if combined[variant]:
            ev = combined[variant]["evaluation"]
            print(
                f"CANDIDATE_DISCOVERY_V1_COMBINED={variant}/TOP{DEFAULT_DAILY_CAP}+LEGACY "
                f"period:{combined[variant]['period']} rows:{combined[variant]['union_rows']} "
                f"hits:{ev['hits']} roi:{ev['roi_pct']}",
                flush=True,
            )

    output = {
        "contract": "candidate_discovery_v1_odds_independent_daily_consensus",
        "period": {"start": START_DATE, "end": END_DATE},
        "selection": {
            "uses_odds": False,
            "uses_expected_value": False,
            "signals": ["top_ticket_probability", "top1_minus_top2_margin", "probability_concentration"],
            "signal_weighting": "equal_weight_within_day_percentile_consensus",
            "one_ticket_per_race": True,
            "daily_caps": list(DAILY_CAPS),
            "provisional_primary_cap": DEFAULT_DAILY_CAP,
            "legacy_behavior": "reference_and_optional_carryover_only",
        },
        "variants": {
            "BASE": {"motor_weight": 0.0},
            "MOTOR2": {"motor_weight": MOTOR2_WEIGHT, "invalid_motor2_fallback": 33.0},
        },
        "audit": audit,
        "reports": all_reports,
        "combined_legacy_window": combined,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    print("CANDIDATE_DISCOVERY_V1_AUDIT=" + json.dumps(audit, sort_keys=True), flush=True)
    print("CANDIDATE_DISCOVERY_V1_PURCHASE_ACTION=false", flush=True)
    print("CANDIDATE_DISCOVERY_V1_PROMOTION_ALLOWED=0", flush=True)
    print("CANDIDATE_DISCOVERY_V1_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
