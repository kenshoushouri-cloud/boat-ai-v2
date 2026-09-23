# -*- coding: utf-8 -*-
"""Strict past-only V4 position-conditional tail model walk-forward.

Current V4 race selection and predicted first-place head are fixed.  Two small
pairwise-logit models are learned only from prior chronological blocks:
- second place, conditional on first;
- third place, conditional on first and second.

All lane features are race-card / entry information available pre-result.  For
each test day the current six races, current control Top2, and challenger Top2
are frozen before official result/payout access.  Model weights are fixed for
the whole test block and updated only after that block has ended.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist

VERSION = "2026-09-23 v4-position-conditional-tail-v1"
START_DATE = date.fromisoformat(os.getenv("V4_POSCOND_START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("V4_POSCOND_END_DATE", "2026-09-22"))
BLOCKS = int(os.getenv("V4_POSCOND_BLOCKS", "10"))
EPOCHS_PER_BLOCK = int(os.getenv("V4_POSCOND_EPOCHS_PER_BLOCK", "12"))
BASE_LR = float(os.getenv("V4_POSCOND_BASE_LR", "0.035"))
L2 = float(os.getenv("V4_POSCOND_L2", "0.0005"))
UNIT_YEN = 100
OUTPUT_JSON = Path(
    os.getenv("V4_POSCOND_OUTPUT_JSON", "v4-position-conditional-tail-walkforward.json")
)

if BLOCKS < 2:
    raise RuntimeError("V4_POSCOND_BLOCKS must be >= 2")
if EPOCHS_PER_BLOCK < 1:
    raise RuntimeError("V4_POSCOND_EPOCHS_PER_BLOCK must be >= 1")
if END_DATE < START_DATE:
    raise RuntimeError("invalid position-conditional period")


def zscore6(values: Mapping[int, float]) -> dict[int, float]:
    xs = [float(values[lane]) for lane in v4.LANES]
    mean = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs))
    if sd < 1e-12:
        return {lane: 0.0 for lane in v4.LANES}
    return {lane: (float(values[lane]) - mean) / sd for lane in v4.LANES}


def entry_value(row: Mapping[str, Any], key: str, default: float) -> float:
    value = hist.finite(row.get(key))
    return default if value is None else float(value)


def lane_base_feature_map(
    entries: list[dict[str, Any]],
    venue_id: str,
) -> dict[int, tuple[float, ...]]:
    by_lane = {int(row.get("lane") or 0): row for row in entries}
    if set(by_lane) != set(v4.LANES):
        raise ValueError("complete six-lane entries required")

    raw = hist.base_raw(entries, venue_id)
    win = {
        lane: entry_value(by_lane[lane], "national_win_rate", 0.0)
        for lane in v4.LANES
    }
    nat2 = {
        lane: entry_value(by_lane[lane], "national_place2_rate", 32.0)
        for lane in v4.LANES
    }
    loc2 = {
        lane: entry_value(by_lane[lane], "local_place2_rate", 30.0)
        for lane in v4.LANES
    }
    fast_st = {
        lane: -entry_value(by_lane[lane], "avg_st", 0.18)
        for lane in v4.LANES
    }
    motor2 = {
        lane: entry_value(by_lane[lane], "motor_place2_rate", 33.0)
        for lane in v4.LANES
    }
    zs = [zscore6(values) for values in (raw, win, nat2, loc2, fast_st, motor2)]
    return {
        lane: tuple(z[lane] for z in zs)
        for lane in v4.LANES
    }


def lane_one_hot(lane: int) -> tuple[float, ...]:
    return tuple(1.0 if lane == idx else 0.0 for idx in v4.LANES)


def second_features(
    base: Mapping[int, Sequence[float]],
    *,
    candidate: int,
    first: int,
) -> tuple[float, ...]:
    return (
        *tuple(float(x) for x in base[candidate]),
        *lane_one_hot(candidate),
        1.0 if candidate < first else 0.0,
        abs(candidate - first) / 5.0,
    )


def third_features(
    base: Mapping[int, Sequence[float]],
    *,
    candidate: int,
    first: int,
    second: int,
) -> tuple[float, ...]:
    return (
        *tuple(float(x) for x in base[candidate]),
        *lane_one_hot(candidate),
        1.0 if candidate < first else 0.0,
        abs(candidate - first) / 5.0,
        1.0 if candidate < second else 0.0,
        abs(candidate - second) / 5.0,
    )


SECOND_DIM = len(second_features(
    {lane: (0.0,) * 6 for lane in v4.LANES},
    candidate=2,
    first=1,
))
THIRD_DIM = len(third_features(
    {lane: (0.0,) * 6 for lane in v4.LANES},
    candidate=3,
    first=1,
    second=2,
))


class PairwiseLogit:
    def __init__(self, dim: int) -> None:
        self.weights = [0.0] * dim
        self.updates = 0

    def score(self, x: Sequence[float]) -> float:
        return sum(w * float(v) for w, v in zip(self.weights, x))

    def fit_choice(
        self,
        *,
        target: int,
        alternatives: Sequence[int],
        feature_fn,
    ) -> None:
        xt = feature_fn(target)
        for other in alternatives:
            if other == target:
                continue
            xo = feature_fn(other)
            diff = [float(a) - float(b) for a, b in zip(xt, xo)]
            margin = sum(w * d for w, d in zip(self.weights, diff))
            if margin >= 0:
                exp_neg = math.exp(-min(margin, 60.0))
                p = 1.0 / (1.0 + exp_neg)
            else:
                exp_pos = math.exp(max(margin, -60.0))
                p = exp_pos / (1.0 + exp_pos)
            lr = BASE_LR / math.sqrt(1.0 + self.updates / 5000.0)
            for idx, d in enumerate(diff):
                grad = (1.0 - p) * d - L2 * self.weights[idx]
                self.weights[idx] += lr * grad
                self.weights[idx] = max(-6.0, min(6.0, self.weights[idx]))
            self.updates += 1

    def softmax(
        self,
        alternatives: Sequence[int],
        feature_fn,
    ) -> dict[int, float]:
        scored = [(lane, self.score(feature_fn(lane))) for lane in alternatives]
        max_score = max(score for _, score in scored)
        weights = [(lane, math.exp(score - max_score)) for lane, score in scored]
        total = sum(value for _, value in weights)
        return {lane: value / total for lane, value in weights}


def control_second_choice(
    probs: Mapping[str, float],
    *,
    first: int,
) -> int:
    masses = {lane: 0.0 for lane in v4.LANES if lane != first}
    for ticket, prob in probs.items():
        a, b, _ = (int(x) for x in ticket.split("-"))
        if a == first:
            masses[b] += float(prob)
    return sorted(masses.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def challenger_top2(
    *,
    first: int,
    base_features: Mapping[int, Sequence[float]],
    second_model: PairwiseLogit,
    third_model: PairwiseLogit,
) -> tuple[list[str], dict[int, float]]:
    second_alts = [lane for lane in v4.LANES if lane != first]
    p2 = second_model.softmax(
        second_alts,
        lambda lane: second_features(base_features, candidate=lane, first=first),
    )
    tickets: list[tuple[str, float]] = []
    for second in second_alts:
        third_alts = [
            lane for lane in v4.LANES if lane not in (first, second)
        ]
        p3 = third_model.softmax(
            third_alts,
            lambda lane: third_features(
                base_features,
                candidate=lane,
                first=first,
                second=second,
            ),
        )
        for third in third_alts:
            tickets.append((f"{first}-{second}-{third}", p2[second] * p3[third]))
    tickets.sort(key=lambda kv: (-kv[1], kv[0]))
    return [ticket for ticket, _ in tickets[:2]], p2


def current_day_snapshot(
    cur: psycopg.Cursor[Any],
    day: date,
    *,
    second_model: PairwiseLogit,
    third_model: PairwiseLogit,
) -> list[dict[str, Any]]:
    races, entries_by, course_by, opponent_by = hist.fetch_day_inputs(cur, day)
    cutoff = hist.cutoff_for(day)
    distributions: dict[str, dict[str, float]] = {}
    features: dict[str, dict[int, tuple[float, ...]]] = {}

    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        deadline = hist.aware_jst(race.get("deadline_at"))
        if len(entries) != 6 or deadline is None:
            continue
        venue = str(race.get("venue_id") or "").zfill(2)
        try:
            base_raw = hist.base_raw(entries, venue)
            base_features = lane_base_feature_map(entries, venue)
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
            base_raw=base_raw,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        features[rid] = base_features

    selected = v4.select_daily(
        distributions,
        race_cap=v4.CORE_RACES,
        ticket_count=v4.CORE_TICKETS,
    )

    frozen: list[dict[str, Any]] = []
    for row in selected:
        rid = str(row["race_id"])
        control_top2 = list(row["tickets"])
        head = int(row["head_lane"])
        if any(int(ticket.split("-", 1)[0]) != head for ticket in control_top2):
            raise RuntimeError(f"current Top2 head drift: {rid}")
        challenger, p2 = challenger_top2(
            first=head,
            base_features=features[rid],
            second_model=second_model,
            third_model=third_model,
        )
        frozen.append(
            {
                "race_id": rid,
                "head_lane": head,
                "control_top2": control_top2,
                "challenger_top2": challenger,
                "challenger_second_choice": sorted(
                    p2.items(), key=lambda kv: (-kv[1], kv[0])
                )[0][0],
                "control_second_choice": control_second_choice(
                    distributions[rid], first=head
                ),
                "base_features": {
                    str(lane): list(features[rid][lane]) for lane in v4.LANES
                },
            }
        )
    return frozen


def evaluate_frozen_day(
    *,
    day: date,
    frozen: list[dict[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    if len(frozen) != v4.CORE_RACES:
        return None

    control_hits = challenger_hits = head_hits = 0
    control_prefix_hits = challenger_prefix_hits = 0
    control_second_hits = challenger_second_hits = 0
    control_gross = challenger_gross = 0
    training_rows: list[dict[str, Any]] = []

    for row in frozen:
        rid = str(row["race_id"])
        result = results.get(rid)
        if not result:
            return None
        actual = hist.norm_ticket(result.get("trifecta_ticket"))
        payout = int(result.get("trifecta_payout_yen") or 0)
        if actual is None or payout <= 0:
            return None
        a, b, c = (int(x) for x in actual.split("-"))
        control_top2 = list(row["control_top2"])
        challenger_top2 = list(row["challenger_top2"])
        control_hit = actual in control_top2
        challenger_hit = actual in challenger_top2
        control_hits += int(control_hit)
        challenger_hits += int(challenger_hit)
        control_gross += payout if control_hit else 0
        challenger_gross += payout if challenger_hit else 0

        head_correct = int(row["head_lane"]) == a
        head_hits += int(head_correct)
        if head_correct:
            control_prefix_hits += int(
                any(
                    tuple(int(x) for x in ticket.split("-"))[:2] == (a, b)
                    for ticket in control_top2
                )
            )
            challenger_prefix_hits += int(
                any(
                    tuple(int(x) for x in ticket.split("-"))[:2] == (a, b)
                    for ticket in challenger_top2
                )
            )
            control_second_hits += int(int(row["control_second_choice"]) == b)
            challenger_second_hits += int(int(row["challenger_second_choice"]) == b)

        training_rows.append(
            {
                "race_id": rid,
                "actual": [a, b, c],
                "base_features": row["base_features"],
            }
        )

    investment = v4.CORE_RACES * v4.CORE_TICKETS * UNIT_YEN
    return (
        {
            "date": day.isoformat(),
            "races": v4.CORE_RACES,
            "investment_yen": investment,
            "control_gross_yen": control_gross,
            "challenger_gross_yen": challenger_gross,
            "control_profit_yen": control_gross - investment,
            "challenger_profit_yen": challenger_gross - investment,
            "control_top2_hits": control_hits,
            "challenger_top2_hits": challenger_hits,
            "head_hits": head_hits,
            "control_prefix_hits_given_head": control_prefix_hits,
            "challenger_prefix_hits_given_head": challenger_prefix_hits,
            "control_second_hits_given_head": control_second_hits,
            "challenger_second_hits_given_head": challenger_second_hits,
        },
        training_rows,
    )


def train_block(
    *,
    second_model: PairwiseLogit,
    third_model: PairwiseLogit,
    training_rows: list[dict[str, Any]],
) -> None:
    for _ in range(EPOCHS_PER_BLOCK):
        for row in training_rows:
            a, b, c = (int(x) for x in row["actual"])
            base = {
                int(lane): tuple(float(v) for v in values)
                for lane, values in row["base_features"].items()
            }
            second_alts = [lane for lane in v4.LANES if lane != a]
            second_model.fit_choice(
                target=b,
                alternatives=second_alts,
                feature_fn=lambda lane, base=base, a=a: second_features(
                    base, candidate=lane, first=a
                ),
            )
            third_alts = [lane for lane in v4.LANES if lane not in (a, b)]
            third_model.fit_choice(
                target=c,
                alternatives=third_alts,
                feature_fn=lambda lane, base=base, a=a, b=b: third_features(
                    base, candidate=lane, first=a, second=b
                ),
            )


def aggregate(days: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(days)
    races = sum(int(row["races"]) for row in rows)
    investment = sum(int(row["investment_yen"]) for row in rows)
    control_gross = sum(int(row["control_gross_yen"]) for row in rows)
    challenger_gross = sum(int(row["challenger_gross_yen"]) for row in rows)
    control_hits = sum(int(row["control_top2_hits"]) for row in rows)
    challenger_hits = sum(int(row["challenger_top2_hits"]) for row in rows)
    head_hits = sum(int(row["head_hits"]) for row in rows)
    control_prefix = sum(int(row["control_prefix_hits_given_head"]) for row in rows)
    challenger_prefix = sum(
        int(row["challenger_prefix_hits_given_head"]) for row in rows
    )
    control_second = sum(int(row["control_second_hits_given_head"]) for row in rows)
    challenger_second = sum(
        int(row["challenger_second_hits_given_head"]) for row in rows
    )
    return {
        "days": len(rows),
        "races": races,
        "investment_yen": investment,
        "head_hits": head_hits,
        "head_hit_rate_percent": round(head_hits / races * 100.0, 3) if races else 0.0,
        "control": {
            "top2_hits": control_hits,
            "top2_hit_rate_percent": round(control_hits / races * 100.0, 3)
            if races else 0.0,
            "gross_return_yen": control_gross,
            "profit_yen": control_gross - investment,
            "roi_percent": round(control_gross / investment * 100.0, 3)
            if investment else 0.0,
            "prefix_hits_given_head": control_prefix,
            "prefix_hit_rate_given_head_percent": round(
                control_prefix / head_hits * 100.0, 3
            ) if head_hits else 0.0,
            "second_hits_given_head": control_second,
            "second_hit_rate_given_head_percent": round(
                control_second / head_hits * 100.0, 3
            ) if head_hits else 0.0,
        },
        "challenger": {
            "top2_hits": challenger_hits,
            "top2_hit_rate_percent": round(challenger_hits / races * 100.0, 3)
            if races else 0.0,
            "gross_return_yen": challenger_gross,
            "profit_yen": challenger_gross - investment,
            "roi_percent": round(challenger_gross / investment * 100.0, 3)
            if investment else 0.0,
            "prefix_hits_given_head": challenger_prefix,
            "prefix_hit_rate_given_head_percent": round(
                challenger_prefix / head_hits * 100.0, 3
            ) if head_hits else 0.0,
            "second_hits_given_head": challenger_second,
            "second_hit_rate_given_head_percent": round(
                challenger_second / head_hits * 100.0, 3
            ) if head_hits else 0.0,
        },
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    all_days = [d.isoformat() for d in hist.daterange(START_DATE, END_DATE)]
    calendar_blocks = hist.split_blocks(all_days, BLOCKS)
    second_model = PairwiseLogit(SECOND_DIM)
    third_model = PairwiseLogit(THIRD_DIM)

    print(f"V4_POSCOND_VERSION={VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "POLICY=READ_ONLY CURRENT_SIX_FIXED CURRENT_HEAD_FIXED "
        "BLOCK_WEIGHTS_FROZEN_BEFORE_TEST_RESULT PRIOR_BLOCK_TRAINING_ONLY "
        "NO_ODDS NO_RETUNE",
        flush=True,
    )
    print(
        f"MODEL=PAIRWISE_LOGIT second_dim:{SECOND_DIM} third_dim:{THIRD_DIM} "
        f"epochs_per_block:{EPOCHS_PER_BLOCK} base_lr:{BASE_LR} l2:{L2}",
        flush=True,
    )

    block_results: list[dict[str, Any]] = []
    test_day_metrics: list[dict[str, Any]] = []
    warmup_training_rows: list[dict[str, Any]] = []

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

            for block_index, block_days in enumerate(calendar_blocks, 1):
                block_training_rows: list[dict[str, Any]] = []
                block_metrics: list[dict[str, Any]] = []

                # Weights are fixed for the entire block.  Result rows are read
                # only after each day's control/challenger tickets are frozen.
                for day_text in block_days:
                    day = date.fromisoformat(day_text)
                    frozen = current_day_snapshot(
                        cur,
                        day,
                        second_model=second_model,
                        third_model=third_model,
                    )
                    selected_ids = [str(row["race_id"]) for row in frozen]
                    results = hist.fetch_selected_results(cur, day, selected_ids)
                    evaluated = evaluate_frozen_day(
                        day=day,
                        frozen=frozen,
                        results=results,
                    )
                    if evaluated is None:
                        continue
                    metrics, rows_for_training = evaluated
                    block_metrics.append(metrics)
                    block_training_rows.extend(rows_for_training)

                if block_index == 1:
                    warmup_training_rows = block_training_rows
                    evaluated_summary = aggregate(block_metrics)
                else:
                    evaluated_summary = aggregate(block_metrics)
                    test_day_metrics.extend(block_metrics)

                block_results.append(
                    {
                        "block": block_index,
                        "start_date": block_days[0],
                        "end_date": block_days[-1],
                        "calendar_days": len(block_days),
                        "evaluated": evaluated_summary,
                        "second_model_updates_before_train": second_model.updates,
                        "third_model_updates_before_train": third_model.updates,
                    }
                )

                # This block becomes training data only after every test day in
                # the block has been evaluated with pre-block frozen weights.
                train_block(
                    second_model=second_model,
                    third_model=third_model,
                    training_rows=block_training_rows,
                )
                block_results[-1]["training_races_added"] = len(block_training_rows)
                block_results[-1]["second_model_updates_after_train"] = second_model.updates
                block_results[-1]["third_model_updates_after_train"] = third_model.updates

                print(
                    f"BLOCK={block_index} {block_days[0]}..{block_days[-1]} "
                    f"EVAL_DAYS={evaluated_summary['days']} "
                    f"EVAL_RACES={evaluated_summary['races']} "
                    f"CONTROL_TOP2={evaluated_summary['control']['top2_hit_rate_percent']:.3f} "
                    f"CHALLENGER_TOP2={evaluated_summary['challenger']['top2_hit_rate_percent']:.3f} "
                    f"TRAIN_RACES={len(block_training_rows)}",
                    flush=True,
                )

            conn.rollback()

    unseen = aggregate(test_day_metrics)
    control = unseen["control"]
    challenger = unseen["challenger"]
    block_wins = sum(
        1
        for row in block_results[1:]
        if row["evaluated"]["challenger"]["top2_hit_rate_percent"]
        > row["evaluated"]["control"]["top2_hit_rate_percent"]
    )
    block_ties = sum(
        1
        for row in block_results[1:]
        if row["evaluated"]["challenger"]["top2_hit_rate_percent"]
        == row["evaluated"]["control"]["top2_hit_rate_percent"]
    )

    result = {
        "contract": "v4_position_conditional_tail_walkforward_v1",
        "version": VERSION,
        "period": {
            "start_date": START_DATE.isoformat(),
            "end_date": END_DATE.isoformat(),
        },
        "model": {
            "type": "pairwise_logit",
            "second_dim": SECOND_DIM,
            "third_dim": THIRD_DIM,
            "epochs_per_block": EPOCHS_PER_BLOCK,
            "base_lr": BASE_LR,
            "l2": L2,
            "second_weights_final": [round(x, 8) for x in second_model.weights],
            "third_weights_final": [round(x, 8) for x in third_model.weights],
        },
        "policy": {
            "current_daily_six_fixed": True,
            "current_predicted_head_fixed": True,
            "formal_ticket_count": 2,
            "test_block_weights_frozen": True,
            "training_uses_prior_blocks_only": True,
            "all_tickets_frozen_before_result": True,
            "odds_used_for_selection": False,
            "db_write": False,
            "production_change_allowed": False,
            "model_change_allowed": False,
            "ticket_count_change_allowed": False,
            "purchase_action": False,
        },
        "walkforward": {
            "warmup_block": 1,
            "unseen_test_blocks": max(0, len(calendar_blocks) - 1),
            "unseen": unseen,
            "delta": {
                "top2_hit_rate_pp": round(
                    challenger["top2_hit_rate_percent"]
                    - control["top2_hit_rate_percent"],
                    3,
                ),
                "prefix_hit_rate_given_head_pp": round(
                    challenger["prefix_hit_rate_given_head_percent"]
                    - control["prefix_hit_rate_given_head_percent"],
                    3,
                ),
                "second_hit_rate_given_head_pp": round(
                    challenger["second_hit_rate_given_head_percent"]
                    - control["second_hit_rate_given_head_percent"],
                    3,
                ),
                "roi_pp": round(
                    challenger["roi_percent"] - control["roi_percent"], 3
                ),
            },
            "challenger_top2_block_wins": block_wins,
            "challenger_top2_block_ties": block_ties,
            "block_results": block_results,
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== UNSEEN WALKFORWARD ===", flush=True)
    print(json.dumps(result["walkforward"], sort_keys=True), flush=True)
    print(f"OUTPUT_JSON={OUTPUT_JSON}", flush=True)
    print("RESULT=PASS_READ_ONLY_POSITION_CONDITIONAL", flush=True)


if __name__ == "__main__":
    main()
