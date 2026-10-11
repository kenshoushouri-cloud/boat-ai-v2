# -*- coding: utf-8 -*-
"""Generic market-residual gate for value-candidate research.

Research-only. The input is the same compact ticket CSV accepted by
``research_value_candidate_shadow.py`` but formal use requires complete 120-ticket
races. For each complete race:

- q = de-vigged market probability from the supplied odds
- p = normalized research-model probability from ``prob``
- r_alpha ∝ q * (p/q)^alpha

Alpha is selected on a strictly earlier train period using multiclass log loss and
then frozen on the future test period. This is a probability-quality gate before
any ``p * odds`` profitability claim. It never writes PostgreSQL, sends LINE, or
performs a purchase.

Historical/final odds are permitted only as a clearly labelled diagnostic. Formal
value evidence requires odds that were actually observable before the decision
deadline.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from research_value_candidate_shadow import Row, load_rows

EPS = 1e-15
ALPHAS = (0.00, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00)
TICKETS = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7)
    if b != a
    for c in range(1, 7)
    if c not in (a, b)
)
TICKET_INDEX = {t: i for i, t in enumerate(TICKETS)}


@dataclass(frozen=True)
class Race:
    race_date: date
    race_id: str
    q: tuple[float, ...]
    p: tuple[float, ...]
    actual_index: int


def _normalize(values: Iterable[float]) -> tuple[float, ...]:
    xs = tuple(max(EPS, float(x)) for x in values)
    total = sum(xs)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("invalid probability normalization total")
    return tuple(x / total for x in xs)


def complete_races(rows: Sequence[Row]) -> tuple[list[Race], dict[str, int]]:
    grouped: dict[tuple[str, str], list[Row]] = {}
    for row in rows:
        grouped.setdefault((row.race_date, row.race_id), []).append(row)

    races: list[Race] = []
    skipped_incomplete = skipped_invalid_hit = skipped_invalid_prob = 0
    expected = set(TICKETS)

    for (race_date_raw, race_id), group in sorted(grouped.items()):
        by_ticket = {r.ticket: r for r in group}
        if len(group) != 120 or len(by_ticket) != 120 or set(by_ticket) != expected:
            skipped_incomplete += 1
            continue
        hits = [r for r in group if r.hit == 1]
        if len(hits) != 1 or hits[0].ticket not in TICKET_INDEX:
            skipped_invalid_hit += 1
            continue
        try:
            ordered = [by_ticket[t] for t in TICKETS]
            p = _normalize(r.prob for r in ordered)
            q = _normalize(1.0 / r.odds for r in ordered)
            rd = date.fromisoformat(race_date_raw[:10])
        except Exception:
            skipped_invalid_prob += 1
            continue
        races.append(Race(rd, race_id, q, p, TICKET_INDEX[hits[0].ticket]))

    coverage = {
        "input_race_groups": len(grouped),
        "complete_races": len(races),
        "skipped_incomplete": skipped_incomplete,
        "skipped_invalid_hit": skipped_invalid_hit,
        "skipped_invalid_probability": skipped_invalid_prob,
    }
    return races, coverage


def blend(race: Race, alpha: float) -> tuple[float, ...]:
    logs = []
    mx = -1e100
    for q, p in zip(race.q, race.p):
        z = (1.0 - alpha) * math.log(max(q, EPS)) + alpha * math.log(max(p, EPS))
        logs.append(z)
        mx = max(mx, z)
    values = [math.exp(z - mx) for z in logs]
    return _normalize(values)


def metrics(races: Sequence[Race], alpha: float) -> dict[str, float | int | None]:
    if not races:
        return {"n": 0, "logloss": None, "brier": None, "mean_rank": None}
    ll = br = rk = 0.0
    for race in races:
        probs = blend(race, alpha)
        idx = race.actual_index
        actual_p = max(probs[idx], EPS)
        ll += -math.log(actual_p)
        br += 1.0 - 2.0 * probs[idx] + sum(x * x for x in probs)
        target = probs[idx]
        rk += 1 + sum(1 for i, x in enumerate(probs) if x > target or (x == target and i < idx))
    n = len(races)
    return {"n": n, "logloss": ll / n, "brier": br / n, "mean_rank": rk / n}


def residual_gate(
    rows: Sequence[Row],
    train_end: date,
    test_start: date,
    test_end: date,
    alphas: Sequence[float] = ALPHAS,
) -> dict[str, object]:
    if test_start <= train_end:
        raise ValueError("test_start must be after train_end")
    if test_end < test_start:
        raise ValueError("test_end must be on/after test_start")
    if not alphas or 0.0 not in alphas or 1.0 not in alphas:
        raise ValueError("alphas must include 0.0 market-only and 1.0 model-only")

    races, coverage = complete_races(rows)
    train = [r for r in races if r.race_date <= train_end]
    test = [r for r in races if test_start <= r.race_date <= test_end]

    if not train or not test:
        return {
            "coverage": coverage,
            "period": {
                "train_end": train_end.isoformat(),
                "test_start": test_start.isoformat(),
                "test_end": test_end.isoformat(),
                "train_races": len(train),
                "test_races": len(test),
            },
            "selected_alpha": None,
            "market": metrics(test, 0.0),
            "selected": metrics(test, 0.0) if test else metrics([], 0.0),
            "model": metrics(test, 1.0),
            "oos_residual_support": False,
            "status": "INSUFFICIENT_COMPLETE_TRAIN_OR_TEST_RACES",
            "promotion_allowed": False,
        }

    train_metrics = {float(a): metrics(train, float(a)) for a in alphas}
    selected_alpha = min(
        (float(a) for a in alphas),
        key=lambda a: float(train_metrics[a]["logloss"]),
    )
    market = metrics(test, 0.0)
    selected = metrics(test, selected_alpha)
    model = metrics(test, 1.0)
    ll_delta = float(selected["logloss"]) - float(market["logloss"])
    br_delta = float(selected["brier"]) - float(market["brier"])
    rank_delta = float(selected["mean_rank"]) - float(market["mean_rank"])
    support = selected_alpha > 0.0 and ll_delta < 0.0 and br_delta <= 0.0

    return {
        "coverage": coverage,
        "period": {
            "train_end": train_end.isoformat(),
            "test_start": test_start.isoformat(),
            "test_end": test_end.isoformat(),
            "train_races": len(train),
            "test_races": len(test),
        },
        "alpha_grid": [float(a) for a in alphas],
        "selected_alpha": selected_alpha,
        "train_selected": train_metrics[selected_alpha],
        "market": market,
        "selected": selected,
        "model": model,
        "selected_minus_market": {
            "logloss": ll_delta,
            "brier": br_delta,
            "mean_rank": rank_delta,
        },
        "oos_residual_support": support,
        "status": "SUPPORTS_MARKET_RESIDUAL_RESEARCH" if support else "MARKET_RESIDUAL_NOT_ESTABLISHED",
        "promotion_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research-only train/test market residual gate")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--train-end", required=True, type=date.fromisoformat)
    parser.add_argument("--test-start", required=True, type=date.fromisoformat)
    parser.add_argument("--test-end", required=True, type=date.fromisoformat)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_rows(args.input)
    out = residual_gate(rows, args.train_end, args.test_start, args.test_end)
    out["meta"] = {
        "research_only": True,
        "production_write": False,
        "line_send": False,
        "purchase_action": False,
        "formal_profit_requires_timing_safe_odds": True,
        "historical_or_final_odds_diagnostic_only": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": out["status"], "selected_alpha": out["selected_alpha"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
