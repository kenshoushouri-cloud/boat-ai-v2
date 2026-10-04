# -*- coding: utf-8 -*-
"""Pure/offline prospective shadow for the preregistered V4 alpha=0.25 blend.

This module has two deliberately separate phases:

1. freeze:
   - accepts only pre-result current-V4 distributions and race-card lane inputs;
   - computes the frozen alpha=0.25 shadow Top2;
   - rejects result/payout-like fields;
   - requires exactly the current formal six races.

2. settle:
   - consumes an already frozen shadow artifact plus exact official outcomes;
   - evaluates control vs shadow without reranking or changing tickets.

No database, network, Railway, LINE, purchase, or Production mutation exists here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from research import candidate_discovery_v4_contract as v4

CONTRACT_VERSION = "v4_posblend_forward_shadow_v1"
TRAINING_CUTOFF = date(2026, 9, 22)
FORWARD_START_DATE = date(2026, 9, 24)
ALPHA = 0.25
UNIT_YEN = 100
FORMAL_RACES = 6
FORMAL_TICKETS = 2

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

SECOND_DIM = 14
THIRD_DIM = 16

FORBIDDEN_PRE_RESULT_KEYS = {
    "actual",
    "actual_ticket",
    "finish",
    "finishing_order",
    "outcome",
    "payout",
    "payout_yen",
    "result",
    "result_status",
    "race_status",
    "trifecta_ticket",
    "trifecta_payout_yen",
}


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def finite_number(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def reject_result_fields(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in FORBIDDEN_PRE_RESULT_KEYS:
                raise ValueError(f"pre-result input contains forbidden field: {path}.{key}")
            reject_result_fields(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            reject_result_fields(child, path=f"{path}[{idx}]")


def zscore6(values: Mapping[int, float]) -> dict[int, float]:
    if set(values) != set(v4.LANES):
        raise ValueError("six lanes required")
    xs = [float(values[lane]) for lane in v4.LANES]
    mean = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs))
    if sd < 1e-12:
        return {lane: 0.0 for lane in v4.LANES}
    return {lane: (float(values[lane]) - mean) / sd for lane in v4.LANES}


def lane_one_hot(lane: int) -> tuple[float, ...]:
    return tuple(1.0 if lane == idx else 0.0 for idx in v4.LANES)


def lane_feature_map(lanes: Mapping[str, Any]) -> dict[int, tuple[float, ...]]:
    if set(lanes) != {str(lane) for lane in v4.LANES}:
        raise ValueError("lane inputs must contain string keys 1..6 exactly")

    required = (
        "base_raw",
        "national_win_rate",
        "national_place2_rate",
        "local_place2_rate",
        "avg_st",
        "motor_place2_rate",
    )
    raw_maps: list[dict[int, float]] = []
    for key in required:
        values: dict[int, float] = {}
        for lane in v4.LANES:
            row = lanes[str(lane)]
            if not isinstance(row, Mapping):
                raise ValueError(f"lane {lane} must be an object")
            values[lane] = finite_number(row.get(key), name=f"lane{lane}.{key}")
        if key == "avg_st":
            values = {lane: -value for lane, value in values.items()}
        raw_maps.append(values)

    zs = [zscore6(values) for values in raw_maps]
    return {
        lane: tuple(z[lane] for z in zs)
        for lane in v4.LANES
    }


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


def softmax(
    alternatives: Sequence[int],
    *,
    weights: Sequence[float],
    feature_fn,
) -> dict[int, float]:
    scored = []
    for lane in alternatives:
        features = feature_fn(lane)
        if len(features) != len(weights):
            raise ValueError("weight/feature dimension mismatch")
        score = sum(float(w) * float(x) for w, x in zip(weights, features))
        scored.append((lane, score))
    top = max(score for _, score in scored)
    exp_rows = [(lane, math.exp(score - top)) for lane, score in scored]
    total = sum(value for _, value in exp_rows)
    return {lane: value / total for lane, value in exp_rows}


def first_marginals(probs: Mapping[str, float]) -> dict[int, float]:
    out = {lane: 0.0 for lane in v4.LANES}
    for ticket, prob in probs.items():
        a, _, _ = (int(x) for x in str(ticket).split("-"))
        out[a] += float(prob)
    return out


def learned_distribution(
    control_probs: Mapping[str, float],
    base: Mapping[int, Sequence[float]],
) -> dict[str, float]:
    control = v4._normalize_tickets(control_probs)
    heads = first_marginals(control)
    out: dict[str, float] = {}
    for first in v4.LANES:
        second_alts = [lane for lane in v4.LANES if lane != first]
        p2 = softmax(
            second_alts,
            weights=SECOND_WEIGHTS,
            feature_fn=lambda lane, first=first: second_features(
                base, candidate=lane, first=first
            ),
        )
        for second in second_alts:
            third_alts = [
                lane for lane in v4.LANES if lane not in (first, second)
            ]
            p3 = softmax(
                third_alts,
                weights=THIRD_WEIGHTS,
                feature_fn=lambda lane, first=first, second=second: third_features(
                    base, candidate=lane, first=first, second=second
                ),
            )
            for third in third_alts:
                out[f"{first}-{second}-{third}"] = (
                    heads[first] * p2[second] * p3[third]
                )

    out = v4._normalize_tickets(out)
    after = first_marginals(out)
    for lane in v4.LANES:
        if abs(after[lane] - heads[lane]) > 1e-12:
            raise RuntimeError("learned first-place marginal drift")
    return out


def blend_distribution(
    control_probs: Mapping[str, float],
    learned_probs: Mapping[str, float],
) -> dict[str, float]:
    control = v4._normalize_tickets(control_probs)
    learned = v4._normalize_tickets(learned_probs)
    if set(control) != set(learned):
        raise ValueError("ticket support mismatch")
    out = v4._normalize_tickets(
        {
            ticket: (1.0 - ALPHA) * control[ticket] + ALPHA * learned[ticket]
            for ticket in control
        }
    )
    before = first_marginals(control)
    after = first_marginals(out)
    for lane in v4.LANES:
        if abs(after[lane] - before[lane]) > 1e-12:
            raise RuntimeError("blend first-place marginal drift")
    return out


def parse_aware_timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must include timezone")
    return parsed.isoformat()


def validate_control_probs(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError("control_probs must be an object")
    probs = {str(k): finite_number(v, name=f"control_probs.{k}") for k, v in value.items()}
    return v4._normalize_tickets(probs)


def freeze_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    reject_result_fields(payload)
    if payload.get("contract") != "v4_posblend_forward_input_v1":
        raise ValueError("unsupported pre-result input contract")

    race_day = date.fromisoformat(str(payload.get("race_date") or ""))
    if race_day < FORWARD_START_DATE:
        raise ValueError("race_date precedes preregistered Forward start")
    observed_at = parse_aware_timestamp(payload.get("observed_at"))
    races = payload.get("races")
    if not isinstance(races, list) or len(races) != FORMAL_RACES:
        raise ValueError("exactly six formal races required")

    race_ids: set[str] = set()
    frozen_races = []
    for row in races:
        if not isinstance(row, Mapping):
            raise ValueError("race row must be an object")
        race_id = str(row.get("race_id") or "")
        if not race_id or race_id in race_ids:
            raise ValueError("race_id must be nonempty and unique")
        race_ids.add(race_id)

        control = validate_control_probs(row.get("control_probs"))
        base = lane_feature_map(row.get("lanes"))
        learned = learned_distribution(control, base)
        shadow = blend_distribution(control, learned)
        frozen_races.append(
            {
                "race_id": race_id,
                "control_top2": list(v4.top_tickets(control, FORMAL_TICKETS)),
                "shadow_top2": list(v4.top_tickets(shadow, FORMAL_TICKETS)),
                "control_first_marginal": {
                    str(lane): round(value, 12)
                    for lane, value in first_marginals(control).items()
                },
                "shadow_first_marginal": {
                    str(lane): round(value, 12)
                    for lane, value in first_marginals(shadow).items()
                },
            }
        )

    source_sha = sha256_json(payload)
    out = {
        "contract": CONTRACT_VERSION,
        "phase": "PRE_RESULT_FROZEN",
        "race_date": race_day.isoformat(),
        "observed_at": observed_at,
        "training_cutoff": TRAINING_CUTOFF.isoformat(),
        "forward_start_date": FORWARD_START_DATE.isoformat(),
        "alpha": ALPHA,
        "formal_races": FORMAL_RACES,
        "formal_tickets": FORMAL_TICKETS,
        "source_input_sha256": source_sha,
        "model_source": {
            "tail_run": 35850876016,
            "tail_artifact_id": 10745542496,
            "tail_json_sha256": "7efaeff5b835494e0b8e4a76610b53a79734bf07a7e44a30541677969031078e",
            "blend_run": 35850876154,
            "blend_artifact_id": 10745995595,
            "blend_json_sha256": "817903cf704593171d4b93874d286fe0b110336c81775af642afa698d0720f5c",
        },
        "policy": {
            "current_six_required": True,
            "first_place_marginal_preserved": True,
            "result_fields_accepted_at_freeze": False,
            "rerank_after_result": False,
            "replacement_race": False,
            "five_race_shrink": False,
            "db_write": False,
            "network": False,
            "production_change_allowed": False,
            "promotion_allowed": False,
            "purchase_action": False,
        },
        "races": frozen_races,
    }
    out["freeze_sha256"] = sha256_json(out)
    return out


def normalize_ticket(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "")
    parts = text.split("-")
    if len(parts) != 3:
        raise ValueError("official ticket must be A-B-C")
    try:
        lanes = tuple(int(x) for x in parts)
    except ValueError as exc:
        raise ValueError("official ticket contains noninteger lane") from exc
    if len(set(lanes)) != 3 or any(lane not in v4.LANES for lane in lanes):
        raise ValueError("official ticket must contain three distinct lanes 1..6")
    return "-".join(str(x) for x in lanes)


def settle_payload(frozen: Mapping[str, Any], results_payload: Mapping[str, Any]) -> dict[str, Any]:
    if frozen.get("contract") != CONTRACT_VERSION or frozen.get("phase") != "PRE_RESULT_FROZEN":
        raise ValueError("unsupported frozen shadow artifact")
    expected_sha = frozen.get("freeze_sha256")
    without_sha = dict(frozen)
    without_sha.pop("freeze_sha256", None)
    if expected_sha != sha256_json(without_sha):
        raise ValueError("frozen artifact SHA mismatch")

    results = results_payload.get("results")
    if not isinstance(results, list) or len(results) != FORMAL_RACES:
        raise ValueError("exactly six official results required")
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in results:
        if not isinstance(row, Mapping):
            raise ValueError("result row must be an object")
        race_id = str(row.get("race_id") or "")
        if not race_id or race_id in by_id:
            raise ValueError("result race_id must be nonempty and unique")
        if row.get("result_status") != "official" or row.get("race_status") != "official":
            raise ValueError("official/official result status required")
        by_id[race_id] = row

    frozen_ids = [str(row["race_id"]) for row in frozen["races"]]
    if set(by_id) != set(frozen_ids):
        raise ValueError("result set must exactly match frozen six races")

    rows = []
    control_gross = shadow_gross = 0
    control_hits = shadow_hits = 0
    for row in frozen["races"]:
        race_id = str(row["race_id"])
        result = by_id[race_id]
        actual = normalize_ticket(result.get("trifecta_ticket"))
        payout = int(finite_number(result.get("trifecta_payout_yen"), name="trifecta_payout_yen"))
        if payout <= 0:
            raise ValueError("official payout must be positive")
        control_hit = actual in row["control_top2"]
        shadow_hit = actual in row["shadow_top2"]
        control_hits += int(control_hit)
        shadow_hits += int(shadow_hit)
        control_gross += payout if control_hit else 0
        shadow_gross += payout if shadow_hit else 0
        rows.append(
            {
                "race_id": race_id,
                "actual": actual,
                "payout_yen": payout,
                "control_top2": row["control_top2"],
                "shadow_top2": row["shadow_top2"],
                "control_hit": control_hit,
                "shadow_hit": shadow_hit,
            }
        )

    investment = FORMAL_RACES * FORMAL_TICKETS * UNIT_YEN
    out = {
        "contract": "v4_posblend_forward_settlement_v1",
        "phase": "POST_RESULT_SETTLED",
        "race_date": frozen["race_date"],
        "freeze_sha256": expected_sha,
        "alpha": ALPHA,
        "races": FORMAL_RACES,
        "investment_yen_each": investment,
        "control": {
            "top2_hits": control_hits,
            "top2_hit_rate_percent": round(control_hits / FORMAL_RACES * 100.0, 3),
            "gross_return_yen": control_gross,
            "profit_yen": control_gross - investment,
            "roi_percent": round(control_gross / investment * 100.0, 3),
        },
        "shadow": {
            "top2_hits": shadow_hits,
            "top2_hit_rate_percent": round(shadow_hits / FORMAL_RACES * 100.0, 3),
            "gross_return_yen": shadow_gross,
            "profit_yen": shadow_gross - investment,
            "roi_percent": round(shadow_gross / investment * 100.0, 3),
        },
        "policy": {
            "tickets_recomputed_after_result": False,
            "five_race_shrink": False,
            "replacement_race": False,
            "production_change_allowed": False,
            "promotion_allowed": False,
            "purchase_action": False,
        },
        "rows": rows,
    }
    out["settlement_sha256"] = sha256_json(out)
    return out


def read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str, value: Any) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze")
    freeze.add_argument("input_json")
    freeze.add_argument("output_json")

    settle = sub.add_parser("settle")
    settle.add_argument("frozen_json")
    settle.add_argument("results_json")
    settle.add_argument("output_json")

    args = parser.parse_args()
    if args.command == "freeze":
        out = freeze_payload(read_json(args.input_json))
        write_json(args.output_json, out)
        print("RESULT=PASS_PRE_RESULT_FREEZE")
    else:
        out = settle_payload(read_json(args.frozen_json), read_json(args.results_json))
        write_json(args.output_json, out)
        print("RESULT=PASS_POST_RESULT_SETTLEMENT")


if __name__ == "__main__":
    main()
