# -*- coding: utf-8 -*-
"""Timing-safe profit audit for current V4 and the frozen alpha=0.25 tail blend.

Research only. The position-conditional models are trained strictly on historical
blocks ending 2026-08-09. They are then frozen for the entire profit test period
2026-08-25..2026-09-22.

For each test date:
- reconstruct current V4 using only timing-safe pre-result inputs;
- keep the current exact six races;
- create current and alpha=0.25 ticket distributions;
- choose the latest coherent complete 120-ticket odds label fully observable at
  least 15 minutes before deadline;
- freeze all 2-point/3-point EV policies before any result read;
- only then read official result/payout rows for settlement.

No threshold is fit from the profit-test outcomes. The policy grid is fixed in
source and all variants are reported. Positive historical variants are only
Forward hypotheses, never Production promotion evidence.
"""
from __future__ import annotations

import json
import math
import os
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist
from research import v4_position_conditional_tail_walkforward_pg as pos

VERSION = "2026-09-23 v4-timing-safe-profit-gate-v1"
TRAIN_START = date(2025, 7, 1)
TRAIN_END = date(2026, 8, 9)
TEST_START = date.fromisoformat(os.getenv("V4_VALUE_TEST_START", "2026-08-25"))
TEST_END = date.fromisoformat(os.getenv("V4_VALUE_TEST_END", "2026-09-22"))
ODDS_CUTOFF_MINUTES = int(os.getenv("V4_VALUE_ODDS_CUTOFF_MINUTES", "15"))
MAX_LABEL_SPREAD_SECONDS = float(
    os.getenv("V4_VALUE_MAX_LABEL_SPREAD_SECONDS", "60")
)
BOOTSTRAP_SAMPLES = int(os.getenv("V4_VALUE_BOOTSTRAP_SAMPLES", "20000"))
BOOTSTRAP_SEED = int(os.getenv("V4_VALUE_BOOTSTRAP_SEED", "20260923"))
UNIT_YEN = 100
OUTPUT_JSON = Path(
    os.getenv("V4_VALUE_OUTPUT_JSON", "v4-timing-safe-profit-gate.json")
)

POINT_COUNTS = (2, 3)
EV_THRESHOLDS: tuple[float | None, ...] = (
    None,
    1.00,
    1.05,
    1.10,
    1.15,
    1.20,
    1.25,
)
SOURCES = ("current", "alpha025")
ALPHA = 0.25

if TEST_END < TEST_START:
    raise RuntimeError("invalid value-test period")
if TEST_START <= TRAIN_END:
    raise RuntimeError("profit test must start after training end")
if ODDS_CUTOFF_MINUTES < 5:
    raise RuntimeError("odds cutoff must preserve operational decision time")
if BOOTSTRAP_SAMPLES < 100:
    raise RuntimeError("bootstrap samples too small")


def threshold_label(value: float | None) -> str:
    return "all" if value is None else f"ev{value:.2f}"


def policy_id(source: str, points: int, threshold: float | None) -> str:
    return f"{source}_p{points}_{threshold_label(threshold)}"


def first_marginals(probs: Mapping[str, float]) -> dict[int, float]:
    normalized = v4._normalize_tickets(probs)
    out = {lane: 0.0 for lane in v4.LANES}
    for ticket, prob in normalized.items():
        out[int(ticket.split("-", 1)[0])] += prob
    return out


def alpha025_distribution(
    current: Mapping[str, float],
    learned: Mapping[str, float],
) -> dict[str, float]:
    c = v4._normalize_tickets(current)
    l = v4._normalize_tickets(learned)
    if set(c) != set(l):
        raise RuntimeError("ticket support drift")
    before = first_marginals(c)
    learned_heads = first_marginals(l)
    for lane in v4.LANES:
        if abs(before[lane] - learned_heads[lane]) > 1e-12:
            raise RuntimeError("learned first-place marginal drift")
    out = v4._normalize_tickets(
        {
            ticket: (1.0 - ALPHA) * c[ticket] + ALPHA * l[ticket]
            for ticket in c
        }
    )
    after = first_marginals(out)
    for lane in v4.LANES:
        if abs(before[lane] - after[lane]) > 1e-12:
            raise RuntimeError("alpha025 first-place marginal drift")
    return out


def train_position_models_to_cutoff(
    cur: psycopg.Cursor[Any],
) -> tuple[pos.PairwiseLogit, pos.PairwiseLogit, dict[str, Any]]:
    all_days = [
        day.isoformat()
        for day in hist.daterange(date(2025, 7, 1), date(2026, 9, 22))
    ]
    blocks = hist.split_blocks(all_days, 10)
    second_model = pos.PairwiseLogit(pos.SECOND_DIM)
    third_model = pos.PairwiseLogit(pos.THIRD_DIM)
    trained_days = 0
    trained_races = 0
    used_blocks = 0

    for block_index, block_day_set in enumerate(blocks, 1):
        block_days = sorted(block_day_set)
        if date.fromisoformat(block_days[0]) > TRAIN_END:
            break
        if date.fromisoformat(block_days[-1]) > TRAIN_END:
            block_days = [
                d for d in block_days if date.fromisoformat(d) <= TRAIN_END
            ]
        if not block_days:
            break

        block_training_rows: list[dict[str, Any]] = []
        for day_text in block_days:
            day = date.fromisoformat(day_text)
            frozen = pos.current_day_snapshot(
                cur,
                day,
                second_model=second_model,
                third_model=third_model,
            )
            selected_ids = [str(row["race_id"]) for row in frozen]
            # Historical outcomes are read only after the day's pre-result
            # candidates have been frozen.
            results = hist.fetch_selected_results(cur, day, selected_ids)
            evaluated = pos.evaluate_frozen_day(
                day=day,
                frozen=frozen,
                results=results,
            )
            if evaluated is None:
                continue
            _, rows_for_training = evaluated
            block_training_rows.extend(rows_for_training)
            trained_days += 1
            trained_races += len(rows_for_training)

        pos.train_block(
            second_model=second_model,
            third_model=third_model,
            training_rows=block_training_rows,
        )
        used_blocks += 1

        if date.fromisoformat(block_days[-1]) >= TRAIN_END:
            break

    return second_model, third_model, {
        "train_start": TRAIN_START.isoformat(),
        "train_end": TRAIN_END.isoformat(),
        "blocks_used": used_blocks,
        "evaluated_days": trained_days,
        "training_races": trained_races,
        "second_updates": second_model.updates,
        "third_updates": third_model.updates,
    }


def build_test_day(
    cur: psycopg.Cursor[Any],
    day: date,
    *,
    second_model: pos.PairwiseLogit,
    third_model: pos.PairwiseLogit,
) -> list[dict[str, Any]]:
    races, entries_by, course_by, opponent_by = hist.fetch_day_inputs(cur, day)
    cutoff = hist.cutoff_for(day)
    distributions: dict[str, dict[str, float]] = {}
    features: dict[str, dict[int, tuple[float, ...]]] = {}
    meta: dict[str, dict[str, Any]] = {}

    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        deadline = hist.aware_jst(race.get("deadline_at"))
        if len(entries) != 6 or deadline is None:
            continue
        venue = str(race.get("venue_id") or "").zfill(2)
        try:
            base = hist.base_raw(entries, venue)
            base_features = pos.lane_base_feature_map(entries, venue)
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
        distributions[rid] = v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        features[rid] = base_features
        meta[rid] = {
            "race_id": rid,
            "race_date": day.isoformat(),
            "venue_id": venue,
            "race_no": int(race.get("race_no") or 0),
            "deadline_at": deadline,
        }

    selected = v4.select_daily(
        distributions,
        race_cap=v4.CORE_RACES,
        ticket_count=v4.CORE_TICKETS,
    )
    if len(selected) != v4.CORE_RACES:
        return []

    frozen: list[dict[str, Any]] = []
    for row in selected:
        rid = str(row["race_id"])
        current = distributions[rid]
        learned, _ = pos.challenger_distribution(
            control_probs=current,
            base_features=features[rid],
            second_model=second_model,
            third_model=third_model,
        )
        alpha025 = alpha025_distribution(current, learned)
        frozen.append(
            {
                **meta[rid],
                "daily_rank": int(row["daily_race_rank"]),
                "probabilities": {
                    "current": current,
                    "alpha025": alpha025,
                },
            }
        )
    return frozen


def latest_coherent_odds(
    cur: psycopg.Cursor[Any],
    selected: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    race_ids = [str(row["race_id"]) for row in selected]
    if not race_ids:
        return {}
    cur.execute(
        """
        select o.race_id,o.snapshot_label,o.ticket,o.odds,o.snapshot_at,
               r.deadline_at
          from v2_realtime_odds_snapshots o
          join v2_races r on r.race_id=o.race_id
         where o.race_id=any(%s)
           and o.snapshot_label is not null
           and o.snapshot_at is not null
           and o.odds is not null
           and o.odds > 1.0
           and r.deadline_at is not null
           and o.snapshot_at <= r.deadline_at - (%s * interval '1 minute')
         order by o.race_id,o.snapshot_label,o.snapshot_at,o.ticket
        """,
        (race_ids, ODDS_CUTOFF_MINUTES),
    )
    rows = [dict(row) for row in cur.fetchall()]

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["race_id"]), str(row["snapshot_label"]))].append(row)

    valid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (rid, label), group in grouped.items():
        tickets: dict[str, float] = {}
        timestamps: list[datetime] = []
        deadline: datetime | None = None
        for row in group:
            ticket = hist.norm_ticket(row.get("ticket"))
            try:
                odd = float(row.get("odds"))
            except Exception:
                continue
            snap = hist.aware_jst(row.get("snapshot_at"))
            deadline = hist.aware_jst(row.get("deadline_at"))
            if ticket is None or snap is None or deadline is None:
                continue
            if not math.isfinite(odd) or odd <= 1.0:
                continue
            tickets[ticket] = odd
            timestamps.append(snap)
        if (
            len(group) != 120
            or len(tickets) != 120
            or len(timestamps) != 120
            or deadline is None
        ):
            continue
        first_at = min(timestamps)
        last_at = max(timestamps)
        spread = (last_at - first_at).total_seconds()
        if spread > MAX_LABEL_SPREAD_SECONDS:
            continue
        if last_at > deadline - timedelta(minutes=ODDS_CUTOFF_MINUTES):
            continue
        valid[rid].append(
            {
                "race_id": rid,
                "snapshot_label": label,
                "odds": tickets,
                "first_snapshot_at": first_at,
                "last_snapshot_at": last_at,
                "deadline_at": deadline,
                "spread_seconds": spread,
                "minutes_before_deadline": (
                    deadline - last_at
                ).total_seconds() / 60.0,
            }
        )

    chosen: dict[str, dict[str, Any]] = {}
    for rid, labels in valid.items():
        labels.sort(
            key=lambda row: (
                row["last_snapshot_at"],
                row["snapshot_label"],
            ),
            reverse=True,
        )
        chosen[rid] = labels[0]
    return chosen


def market_probs(odds: Mapping[str, float]) -> dict[str, float]:
    inverse = {
        ticket: 1.0 / float(value)
        for ticket, value in odds.items()
        if float(value) > 1.0
    }
    if len(inverse) != 120:
        raise ValueError("complete 120 odds required")
    total = sum(inverse.values())
    return {ticket: value / total for ticket, value in inverse.items()}


def brier_score(probs: Mapping[str, float], actual: str) -> float:
    return sum(
        (float(prob) - (1.0 if ticket == actual else 0.0)) ** 2
        for ticket, prob in probs.items()
    )


def freeze_policies_for_race(
    row: Mapping[str, Any],
    odds_row: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    odds = odds_row["odds"]
    frozen: dict[str, list[dict[str, Any]]] = {}
    for source in SOURCES:
        probs = row["probabilities"][source]
        top3 = list(v4.top_tickets(probs, 3))
        for points in POINT_COUNTS:
            tickets = top3[:points]
            for threshold in EV_THRESHOLDS:
                pid = policy_id(source, points, threshold)
                bets: list[dict[str, Any]] = []
                for rank, ticket in enumerate(tickets, 1):
                    odd = float(odds[ticket])
                    prob = float(probs[ticket])
                    ev = prob * odd
                    if threshold is not None and ev < threshold:
                        continue
                    bets.append(
                        {
                            "ticket": ticket,
                            "rank": rank,
                            "prob": prob,
                            "odds": odd,
                            "raw_ev": ev,
                        }
                    )
                frozen[pid] = bets
    return frozen


def summarize_bets(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        rows,
        key=lambda row: (
            row["race_date"],
            row["race_id"],
            int(row["rank"]),
        ),
    )
    bets = len(ordered)
    investment = bets * UNIT_YEN
    gross = sum(int(row["return_yen"]) for row in ordered)
    hits = sum(int(bool(row["hit"])) for row in ordered)
    hit_returns = sorted(
        (int(row["return_yen"]) for row in ordered if row["hit"]),
        reverse=True,
    )

    equity = 0
    peak = 0
    max_drawdown = 0
    losing = 0
    max_losing = 0
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        equity += int(row["return_yen"]) - UNIT_YEN
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        if row["hit"]:
            losing = 0
        else:
            losing += 1
            max_losing = max(max_losing, losing)
        by_date[row["race_date"]].append(row)

    daily = []
    for day, rr in sorted(by_date.items()):
        inv = len(rr) * UNIT_YEN
        ret = sum(int(r["return_yen"]) for r in rr)
        daily.append(
            {
                "date": day,
                "bets": len(rr),
                "investment_yen": inv,
                "return_yen": ret,
            }
        )

    return {
        "bets": bets,
        "races_bet": len({row["race_id"] for row in ordered}),
        "hits": hits,
        "hit_rate_percent": round(hits / bets * 100.0, 3) if bets else None,
        "investment_yen": investment,
        "return_yen": gross,
        "profit_yen": gross - investment,
        "roi_percent": round(gross / investment * 100.0, 3)
        if investment else None,
        "max_hit_yen": hit_returns[0] if hit_returns else 0,
        "largest_hit_share_percent": round(
            hit_returns[0] / gross * 100.0, 3
        ) if hit_returns and gross else 0.0,
        "max_losing_streak_bets": max_losing,
        "max_drawdown_yen": max_drawdown,
        "daily": daily,
    }


def bootstrap_roi(
    daily: Sequence[Mapping[str, Any]],
    *,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    if not daily:
        return {
            "samples": samples,
            "seed": seed,
            "p025": None,
            "median": None,
            "p975": None,
            "positive_share_percent": None,
        }
    rng = random.Random(seed)
    n = len(daily)
    rois: list[float] = []
    for _ in range(samples):
        inv = ret = 0
        for _ in range(n):
            row = daily[rng.randrange(n)]
            inv += int(row["investment_yen"])
            ret += int(row["return_yen"])
        if inv:
            rois.append(ret / inv * 100.0)
    rois.sort()

    def q(p: float) -> float | None:
        if not rois:
            return None
        idx = int(round((len(rois) - 1) * p))
        return round(rois[max(0, min(idx, len(rois) - 1))], 3)

    positive = sum(1 for value in rois if value > 100.0)
    return {
        "samples": samples,
        "seed": seed,
        "p025": q(0.025),
        "median": q(0.5),
        "p975": q(0.975),
        "positive_share_percent": round(
            positive / len(rois) * 100.0,
            3,
        ) if rois else None,
    }


def half_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    midpoint = TEST_START + timedelta(
        days=((TEST_END - TEST_START).days + 1) // 2
    )
    early = [
        row for row in rows
        if date.fromisoformat(row["race_date"]) < midpoint
    ]
    late = [
        row for row in rows
        if date.fromisoformat(row["race_date"]) >= midpoint
    ]
    return {
        "split_date": midpoint.isoformat(),
        "early": summarize_bets(early),
        "late": summarize_bets(late),
    }


def research_candidate_gate(summary: Mapping[str, Any], halves: Mapping[str, Any], bootstrap: Mapping[str, Any]) -> dict[str, Any]:
    early_roi = halves["early"]["roi_percent"]
    late_roi = halves["late"]["roi_percent"]
    passed = bool(
        int(summary["bets"]) >= 30
        and summary["roi_percent"] is not None
        and float(summary["roi_percent"]) > 100.0
        and early_roi is not None
        and float(early_roi) > 100.0
        and late_roi is not None
        and float(late_roi) > 100.0
        and float(summary["largest_hit_share_percent"]) < 50.0
        and bootstrap["positive_share_percent"] is not None
        and float(bootstrap["positive_share_percent"]) >= 90.0
    )
    return {
        "passed": passed,
        "minimum_bets": 30,
        "overall_roi_gt_100": (
            summary["roi_percent"] is not None
            and float(summary["roi_percent"]) > 100.0
        ),
        "both_halves_roi_gt_100": (
            early_roi is not None
            and late_roi is not None
            and float(early_roi) > 100.0
            and float(late_roi) > 100.0
        ),
        "largest_hit_share_lt_50": float(
            summary["largest_hit_share_percent"]
        ) < 50.0,
        "bootstrap_positive_share_ge_90": (
            bootstrap["positive_share_percent"] is not None
            and float(bootstrap["positive_share_percent"]) >= 90.0
        ),
        "promotion_allowed": False,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_VALUE_VERSION={VERSION}", flush=True)
    print(
        f"TRAIN={TRAIN_START}..{TRAIN_END} TEST={TEST_START}..{TEST_END}",
        flush=True,
    )
    print(
        f"ODDS=latest_complete_120_before_deadline_minus_{ODDS_CUTOFF_MINUTES}m "
        f"MAX_LABEL_SPREAD={MAX_LABEL_SPREAD_SECONDS:g}s",
        flush=True,
    )
    print(
        "POLICY_GRID=points:2,3 thresholds:all,1.00,1.05,1.10,1.15,1.20,1.25 "
        "SOURCES=current,alpha025",
        flush=True,
    )
    print(
        "SAFETY=READ_ONLY PRE_RESULT_FREEZE RESULT_AFTER_POLICY_FREEZE "
        "NO_THRESHOLD_FIT_ON_TEST NO_DB_WRITE NO_LINE NO_BUY NO_PROMOTION",
        flush=True,
    )

    policy_rows: dict[str, list[dict[str, Any]]] = {
        policy_id(source, points, threshold): []
        for source in SOURCES
        for points in POINT_COUNTS
        for threshold in EV_THRESHOLDS
    }
    residual_rows: list[dict[str, Any]] = []
    coverage_by_date: dict[str, dict[str, int]] = {}

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='16MB'")

            second_model, third_model, training = train_position_models_to_cutoff(cur)
            print("TRAINING=" + json.dumps(training, sort_keys=True), flush=True)

            for day in hist.daterange(TEST_START, TEST_END):
                selected = build_test_day(
                    cur,
                    day,
                    second_model=second_model,
                    third_model=third_model,
                )
                if len(selected) != v4.CORE_RACES:
                    coverage_by_date[day.isoformat()] = {
                        "selected": len(selected),
                        "odds_ready": 0,
                        "settled": 0,
                    }
                    continue

                odds_by = latest_coherent_odds(cur, selected)
                # Freeze every candidate policy before results are accessed.
                frozen: dict[str, dict[str, list[dict[str, Any]]]] = {}
                for row in selected:
                    rid = str(row["race_id"])
                    if rid not in odds_by:
                        continue
                    frozen[rid] = freeze_policies_for_race(row, odds_by[rid])

                result_ids = sorted(frozen)
                results = hist.fetch_selected_results(cur, day, result_ids)
                settled = 0
                selected_by_id = {
                    str(row["race_id"]): row for row in selected
                }

                for rid in result_ids:
                    result = results.get(rid)
                    if not result:
                        continue
                    actual = hist.norm_ticket(result.get("trifecta_ticket"))
                    payout = int(result.get("trifecta_payout_yen") or 0)
                    if actual is None or payout <= 0:
                        continue
                    settled += 1
                    row = selected_by_id[rid]
                    odds_row = odds_by[rid]
                    market = market_probs(odds_row["odds"])

                    residual = {
                        "race_id": rid,
                        "race_date": day.isoformat(),
                        "daily_rank": int(row["daily_rank"]),
                        "actual": actual,
                        "minutes_before_deadline": round(
                            float(odds_row["minutes_before_deadline"]),
                            4,
                        ),
                        "market_log_loss": -math.log(max(market[actual], 1e-15)),
                        "market_brier": brier_score(market, actual),
                    }
                    for source in SOURCES:
                        probs = row["probabilities"][source]
                        residual[f"{source}_log_loss"] = -math.log(
                            max(float(probs[actual]), 1e-15)
                        )
                        residual[f"{source}_brier"] = brier_score(probs, actual)
                    residual_rows.append(residual)

                    for pid, bets in frozen[rid].items():
                        for bet in bets:
                            hit = bet["ticket"] == actual
                            policy_rows[pid].append(
                                {
                                    "race_id": rid,
                                    "race_date": day.isoformat(),
                                    "daily_rank": int(row["daily_rank"]),
                                    "ticket": bet["ticket"],
                                    "rank": int(bet["rank"]),
                                    "prob": round(float(bet["prob"]), 12),
                                    "odds": round(float(bet["odds"]), 4),
                                    "raw_ev": round(float(bet["raw_ev"]), 8),
                                    "snapshot_label": str(
                                        odds_row["snapshot_label"]
                                    ),
                                    "minutes_before_deadline": round(
                                        float(
                                            odds_row["minutes_before_deadline"]
                                        ),
                                        4,
                                    ),
                                    "hit": hit,
                                    "return_yen": payout if hit else 0,
                                }
                            )

                coverage_by_date[day.isoformat()] = {
                    "selected": len(selected),
                    "odds_ready": len(frozen),
                    "settled": settled,
                }

            conn.rollback()

    residual_summary: dict[str, Any] = {
        "races": len(residual_rows),
    }
    if residual_rows:
        for key in (
            "market_log_loss",
            "current_log_loss",
            "alpha025_log_loss",
            "market_brier",
            "current_brier",
            "alpha025_brier",
        ):
            residual_summary[key] = round(
                sum(float(row[key]) for row in residual_rows)
                / len(residual_rows),
                8,
            )
        residual_summary["current_minus_market_log_loss"] = round(
            residual_summary["current_log_loss"]
            - residual_summary["market_log_loss"],
            8,
        )
        residual_summary["alpha025_minus_market_log_loss"] = round(
            residual_summary["alpha025_log_loss"]
            - residual_summary["market_log_loss"],
            8,
        )

    policies: dict[str, Any] = {}
    passed_candidates: list[str] = []
    for pid, rows in sorted(policy_rows.items()):
        summary = summarize_bets(rows)
        halves = half_summaries(rows)
        bootstrap = bootstrap_roi(
            summary["daily"],
            samples=BOOTSTRAP_SAMPLES,
            seed=BOOTSTRAP_SEED,
        )
        gate = research_candidate_gate(summary, halves, bootstrap)
        if gate["passed"]:
            passed_candidates.append(pid)
        policies[pid] = {
            "summary": summary,
            "halves": halves,
            "bootstrap_roi_percent": bootstrap,
            "research_candidate_gate": gate,
        }

    selected_total = sum(
        row["selected"] for row in coverage_by_date.values()
    )
    odds_total = sum(
        row["odds_ready"] for row in coverage_by_date.values()
    )
    settled_total = sum(
        row["settled"] for row in coverage_by_date.values()
    )
    coverage = {
        "calendar_days": (TEST_END - TEST_START).days + 1,
        "selected_races": selected_total,
        "timing_safe_odds_races": odds_total,
        "settled_timing_safe_races": settled_total,
        "timing_safe_odds_coverage_percent": round(
            odds_total / selected_total * 100.0,
            3,
        ) if selected_total else 0.0,
        "by_date": coverage_by_date,
    }

    out = {
        "contract": "v4_timing_safe_profit_gate_v1",
        "version": VERSION,
        "training": training,
        "test_period": {
            "start": TEST_START.isoformat(),
            "end": TEST_END.isoformat(),
        },
        "odds_contract": {
            "source": "v2_realtime_odds_snapshots",
            "latest_complete_120": True,
            "cutoff_minutes_before_deadline": ODDS_CUTOFF_MINUTES,
            "max_label_spread_seconds": MAX_LABEL_SPREAD_SECONDS,
        },
        "policy_grid": {
            "sources": list(SOURCES),
            "point_counts": list(POINT_COUNTS),
            "ev_thresholds": [
                threshold_label(value) for value in EV_THRESHOLDS
            ],
            "unit_yen": UNIT_YEN,
            "threshold_fit_on_test": False,
        },
        "coverage": coverage,
        "market_residual": residual_summary,
        "policies": policies,
        "research_candidate_gate": {
            "passed_policy_ids": passed_candidates,
            "multiple_comparison_warning": True,
            "historical_positive_is_forward_hypothesis_only": True,
        },
        "policy": {
            "production_change_allowed": False,
            "threshold_change_allowed": False,
            "ticket_count_change_allowed": False,
            "forward_shadow_only_if_preregistered_separately": True,
            "purchase_action": False,
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== COVERAGE ===", flush=True)
    print(json.dumps(coverage, sort_keys=True), flush=True)
    print("=== MARKET RESIDUAL ===", flush=True)
    print(json.dumps(residual_summary, sort_keys=True), flush=True)
    print("=== POLICY RESULTS ===", flush=True)
    for pid, report in sorted(policies.items()):
        s = report["summary"]
        b = report["bootstrap_roi_percent"]
        g = report["research_candidate_gate"]
        print(
            f"POLICY={pid} BETS={s['bets']} RACES={s['races_bet']} "
            f"HITS={s['hits']} ROI={s['roi_percent']} PROFIT={s['profit_yen']} "
            f"EARLY_ROI={report['halves']['early']['roi_percent']} "
            f"LATE_ROI={report['halves']['late']['roi_percent']} "
            f"MAX_HIT_SHARE={s['largest_hit_share_percent']} "
            f"BOOT_POS={b['positive_share_percent']} "
            f"BOOT95=[{b['p025']},{b['p975']}] "
            f"GATE={int(g['passed'])}",
            flush=True,
        )
    print(
        "PASSED_POLICIES=" + json.dumps(passed_candidates),
        flush=True,
    )
    print("PURCHASE_ACTION=false", flush=True)
    print("RESULT=PASS_READ_ONLY_TIMING_SAFE_PROFIT_GATE", flush=True)


if __name__ == "__main__":
    main()
