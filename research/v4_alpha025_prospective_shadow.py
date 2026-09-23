# -*- coding: utf-8 -*-
"""Frozen V4 alpha=0.25 prospective shadow contract.

Research only. Historical tuning is closed. The weights and alpha below are
frozen from the completed 2025-07-01..2026-09-22 position-conditional research
and may only be evaluated prospectively after the #374 real-fixture gate.

This module never accesses a database, outcomes, payouts, odds, LINE, or purchase
surfaces. It transforms an already pre-result current V4 distribution plus the
same-day race-card lane features into a shadow distribution.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from research import candidate_discovery_v4_contract as v4

CONTRACT = "v4_alpha025_prospective_shadow_v1"
ALPHA = 0.25
TRAINING_END_DATE = "2026-09-22"
HISTORICAL_RUN_ID = 35850876154
HISTORICAL_ARTIFACT_ID = 10745995595
HISTORICAL_ARTIFACT_SHA256 = (
    "6aae27dbaa9ed7a13a937904765b61124d4507ec52880d007e9998e1286debbe"
)
HISTORICAL_JSON_SHA256 = (
    "817903cf704593171d4b93874d286fe0b110336c81775af642afa698d0720f5c"
)

SECOND_WEIGHTS = (
    0.06805213,
    0.31264238,
    0.39472861,
    0.21210849,
    -0.08490463,
    0.07383400,
    0.89165567,
    0.12075560,
    -0.07819782,
    -0.15097447,
    -0.12669964,
    -0.65653936,
    -0.22714968,
    -1.22039963,
)
THIRD_WEIGHTS = (
    0.12508998,
    1.11023737,
    -0.24091446,
    -0.04259659,
    0.01722289,
    0.10017386,
    0.55128526,
    0.39007010,
    0.00448591,
    0.10060103,
    -0.36255961,
    -0.68388267,
    -1.31321813,
    -0.44613288,
    -0.14108798,
    -0.29777646,
)

LANE_FEATURE_DIM = 6
SECOND_DIM = 14
THIRD_DIM = 16


def zscore6(values: Mapping[int, float]) -> dict[int, float]:
    xs = [float(values[lane]) for lane in v4.LANES]
    mean = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs))
    if sd < 1e-12:
        return {lane: 0.0 for lane in v4.LANES}
    return {lane: (float(values[lane]) - mean) / sd for lane in v4.LANES}


def lane_feature_map(
    entries: Sequence[Mapping[str, Any]],
    *,
    base_raw: Mapping[int, float],
) -> dict[int, tuple[float, ...]]:
    by_lane = {int(row.get("lane") or 0): row for row in entries}
    if set(by_lane) != set(v4.LANES):
        raise ValueError("complete six-lane entries required")
    if set(base_raw) != set(v4.LANES):
        raise ValueError("base_raw must contain lanes 1..6")

    def finite_or(row: Mapping[str, Any], key: str, default: float) -> float:
        try:
            value = float(row.get(key))
        except Exception:
            return default
        return value if math.isfinite(value) else default

    win = {
        lane: finite_or(by_lane[lane], "national_win_rate", 0.0)
        for lane in v4.LANES
    }
    nat2 = {
        lane: finite_or(by_lane[lane], "national_place2_rate", 32.0)
        for lane in v4.LANES
    }
    loc2 = {
        lane: finite_or(by_lane[lane], "local_place2_rate", 30.0)
        for lane in v4.LANES
    }
    fast_st = {
        lane: -finite_or(by_lane[lane], "avg_st", 0.18)
        for lane in v4.LANES
    }
    motor2 = {
        lane: finite_or(by_lane[lane], "motor_place2_rate", 33.0)
        for lane in v4.LANES
    }
    zs = [
        zscore6(values)
        for values in (base_raw, win, nat2, loc2, fast_st, motor2)
    ]
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
    out = (
        *tuple(float(x) for x in base[candidate]),
        *lane_one_hot(candidate),
        1.0 if candidate < first else 0.0,
        abs(candidate - first) / 5.0,
    )
    if len(out) != SECOND_DIM:
        raise RuntimeError("second feature dimension drift")
    return out


def third_features(
    base: Mapping[int, Sequence[float]],
    *,
    candidate: int,
    first: int,
    second: int,
) -> tuple[float, ...]:
    out = (
        *tuple(float(x) for x in base[candidate]),
        *lane_one_hot(candidate),
        1.0 if candidate < first else 0.0,
        abs(candidate - first) / 5.0,
        1.0 if candidate < second else 0.0,
        abs(candidate - second) / 5.0,
    )
    if len(out) != THIRD_DIM:
        raise RuntimeError("third feature dimension drift")
    return out


def _softmax(
    weights: Sequence[float],
    alternatives: Sequence[int],
    feature_fn,
) -> dict[int, float]:
    scored = []
    for lane in alternatives:
        features = feature_fn(lane)
        if len(features) != len(weights):
            raise RuntimeError("weight/feature dimension mismatch")
        score = sum(float(w) * float(x) for w, x in zip(weights, features))
        scored.append((lane, score))
    max_score = max(score for _, score in scored)
    exp_scores = [(lane, math.exp(score - max_score)) for lane, score in scored]
    total = sum(value for _, value in exp_scores)
    return {lane: value / total for lane, value in exp_scores}


def first_marginals(probs: Mapping[str, float]) -> dict[int, float]:
    normalized = v4._normalize_tickets(probs)
    out = {lane: 0.0 for lane in v4.LANES}
    for ticket, prob in normalized.items():
        out[int(ticket.split("-", 1)[0])] += prob
    return out


def learned_tail_distribution(
    current_probs: Mapping[str, float],
    base_features: Mapping[int, Sequence[float]],
) -> dict[str, float]:
    current = v4._normalize_tickets(current_probs)
    heads = first_marginals(current)
    out: dict[str, float] = {}

    for first in v4.LANES:
        second_alts = [lane for lane in v4.LANES if lane != first]
        p2 = _softmax(
            SECOND_WEIGHTS,
            second_alts,
            lambda lane, first=first: second_features(
                base_features,
                candidate=lane,
                first=first,
            ),
        )
        for second in second_alts:
            third_alts = [
                lane for lane in v4.LANES
                if lane not in (first, second)
            ]
            p3 = _softmax(
                THIRD_WEIGHTS,
                third_alts,
                lambda lane, first=first, second=second: third_features(
                    base_features,
                    candidate=lane,
                    first=first,
                    second=second,
                ),
            )
            for third in third_alts:
                out[f"{first}-{second}-{third}"] = (
                    heads[first] * p2[second] * p3[third]
                )

    out = v4._normalize_tickets(out)
    learned_heads = first_marginals(out)
    for lane in v4.LANES:
        if abs(learned_heads[lane] - heads[lane]) > 1e-12:
            raise RuntimeError("learned first-place marginal drift")
    return out


def shadow_distribution(
    current_probs: Mapping[str, float],
    base_features: Mapping[int, Sequence[float]],
) -> dict[str, float]:
    current = v4._normalize_tickets(current_probs)
    learned = learned_tail_distribution(current, base_features)
    out = {
        ticket: (1.0 - ALPHA) * current[ticket] + ALPHA * learned[ticket]
        for ticket in current
    }
    out = v4._normalize_tickets(out)
    before = first_marginals(current)
    after = first_marginals(out)
    for lane in v4.LANES:
        if abs(after[lane] - before[lane]) > 1e-12:
            raise RuntimeError("shadow first-place marginal drift")
    return out


def model_metadata() -> dict[str, Any]:
    frozen = {
        "contract": CONTRACT,
        "alpha": ALPHA,
        "training_end_date": TRAINING_END_DATE,
        "second_weights": list(SECOND_WEIGHTS),
        "third_weights": list(THIRD_WEIGHTS),
        "historical_run_id": HISTORICAL_RUN_ID,
        "historical_artifact_id": HISTORICAL_ARTIFACT_ID,
        "historical_artifact_sha256": HISTORICAL_ARTIFACT_SHA256,
        "historical_json_sha256": HISTORICAL_JSON_SHA256,
    }
    canonical = json.dumps(
        frozen,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        **frozen,
        "frozen_model_sha256": hashlib.sha256(canonical).hexdigest(),
    }
