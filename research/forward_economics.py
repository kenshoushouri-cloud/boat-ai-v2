# -*- coding: utf-8 -*-
"""Pure common economics for prospective Forward evidence.

This module has no DB/network/file I/O and no Production side effects.

Settlement semantics:
- evaluation_status == "evaluated": economically settled; investment counts.
- evaluation_status == "invalid_result": void/cancelled/invalid; investment does NOT count.
- any other status: pending/unknown; investment does NOT count.

The module is intentionally policy-neutral. It reports metrics and uncertainty;
it never authorizes promotion, stake, selector, purchase, or Production changes.
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_UNIT_YEN = 100
VALID_ECONOMIC_STATUS = "evaluated"
INVALID_ECONOMIC_STATUS = "invalid_result"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def economic_status(row: Mapping[str, Any]) -> str:
    status = str(row.get("evaluation_status") or "").strip()
    if status == VALID_ECONOMIC_STATUS:
        return VALID_ECONOMIC_STATUS
    if status == INVALID_ECONOMIC_STATUS:
        return INVALID_ECONOMIC_STATUS
    return "pending"


def is_economically_settled(row: Mapping[str, Any]) -> bool:
    return economic_status(row) == VALID_ECONOMIC_STATUS


def investment_yen(row: Mapping[str, Any], *, unit_yen: int = DEFAULT_UNIT_YEN) -> int:
    if not is_economically_settled(row):
        return 0
    inv = _safe_int(row.get("investment_yen"), unit_yen)
    return inv if inv > 0 else unit_yen


def return_yen(row: Mapping[str, Any]) -> int:
    if not is_economically_settled(row):
        return 0
    return max(0, _safe_int(row.get("return_yen"), 0))


def hit_return_yen(row: Mapping[str, Any]) -> int:
    if not is_economically_settled(row) or not bool(row.get("hit")):
        return 0
    payout = _safe_int(row.get("payout_yen"), return_yen(row))
    return max(payout, return_yen(row), 0)


def coverage(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    total = evaluated = invalid = pending = 0
    for row in rows:
        total += 1
        status = economic_status(row)
        if status == VALID_ECONOMIC_STATUS:
            evaluated += 1
        elif status == INVALID_ECONOMIC_STATUS:
            invalid += 1
        else:
            pending += 1
    return {
        "rows": total,
        "evaluated": evaluated,
        "invalid_result": invalid,
        "pending": pending,
    }


def metrics(
    rows: Iterable[Mapping[str, Any]],
    *,
    unit_yen: int = DEFAULT_UNIT_YEN,
) -> dict[str, Any]:
    rr = [row for row in rows if is_economically_settled(row)]
    investment = sum(investment_yen(row, unit_yen=unit_yen) for row in rr)
    returned = sum(return_yen(row) for row in rr)
    hits = sum(int(bool(row.get("hit"))) for row in rr)
    hit_returns = sorted(
        (hit_return_yen(row) for row in rr if bool(row.get("hit"))),
        reverse=True,
    )
    largest = hit_returns[0] if hit_returns else 0
    return {
        "evaluated": len(rr),
        "hits": hits,
        "hit_rate_pct": round(hits / len(rr) * 100.0, 4) if rr else None,
        "investment_yen": investment,
        "return_yen": returned,
        "profit_yen": returned - investment,
        "roi_pct": round(returned / investment * 100.0, 4) if investment else None,
        "largest_hit_yen": largest,
        "largest_hit_share_pct": (
            round(largest / returned * 100.0, 4) if returned else 0.0
        ),
    }


def risk(
    rows: Sequence[Mapping[str, Any]],
    *,
    unit_yen: int = DEFAULT_UNIT_YEN,
) -> dict[str, int]:
    rr = [row for row in rows if is_economically_settled(row)]
    equity = 0
    peak = 0
    peak_index = 0
    max_drawdown = 0
    max_drawdown_bets = 0
    losing = 0
    max_losing = 0

    for index, row in enumerate(rr, 1):
        ret = return_yen(row)
        inv = investment_yen(row, unit_yen=unit_yen)
        equity += ret - inv

        if ret > 0:
            losing = 0
        else:
            losing += 1
            max_losing = max(max_losing, losing)

        if equity > peak:
            peak = equity
            peak_index = index

        dd = peak - equity
        if dd > max_drawdown:
            max_drawdown = dd
            max_drawdown_bets = index - peak_index

    return {
        "max_drawdown_yen": max_drawdown,
        "max_drawdown_bets": max_drawdown_bets,
        "max_losing_streak": max_losing,
    }


def chronological_halves(
    rows: Sequence[Mapping[str, Any]],
    *,
    unit_yen: int = DEFAULT_UNIT_YEN,
) -> dict[str, dict[str, Any]]:
    rr = [row for row in rows if is_economically_settled(row)]
    mid = len(rr) // 2
    return {
        "first": metrics(rr[:mid], unit_yen=unit_yen),
        "second": metrics(rr[mid:], unit_yen=unit_yen),
    }


def by_calendar_key(
    rows: Iterable[Mapping[str, Any]],
    *,
    key_len: int,
    date_field: str = "race_date",
    unit_yen: int = DEFAULT_UNIT_YEN,
) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        raw = str(row.get(date_field) or "")
        key = raw[:key_len]
        if key:
            groups[key].append(row)
    return [
        {"period": key, **coverage(groups[key]), **metrics(groups[key], unit_yen=unit_yen)}
        for key in sorted(groups)
    ]


def day_bootstrap(
    rows: Iterable[Mapping[str, Any]],
    *,
    samples: int = 20_000,
    seed: int = 20260927,
    date_field: str = "race_date",
    unit_yen: int = DEFAULT_UNIT_YEN,
) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if not is_economically_settled(row):
            continue
        day = str(row.get(date_field) or "")[:10]
        if day:
            groups[day].append(row)

    days = sorted(groups)
    if not days or samples <= 0:
        return {
            "samples": 0,
            "seed": seed,
            "median_roi_pct": None,
            "ci95_roi_pct": [None, None],
            "p_roi_gt_100_pct": None,
        }

    rnd = random.Random(seed)
    rois: list[float] = []
    for _ in range(samples):
        investment = 0
        returned = 0
        for _slot in days:
            day = days[rnd.randrange(len(days))]
            for row in groups[day]:
                investment += investment_yen(row, unit_yen=unit_yen)
                returned += return_yen(row)
        rois.append(returned / investment * 100.0 if investment else 0.0)

    rois.sort()
    n = len(rois)
    return {
        "samples": n,
        "seed": seed,
        "median_roi_pct": round(rois[n // 2], 4),
        "ci95_roi_pct": [
            round(rois[int(0.025 * (n - 1))], 4),
            round(rois[int(0.975 * (n - 1))], 4),
        ],
        "p_roi_gt_100_pct": round(
            sum(x > 100.0 for x in rois) / n * 100.0,
            4,
        ),
    }


def normalize_formal_settlement_row(
    row: Mapping[str, Any],
    *,
    investment_yen_per_bet: int = DEFAULT_UNIT_YEN,
    ticket_count: int = 1,
) -> dict[str, Any]:
    """Map immutable-artifact settlement shape into the common economics shape.

    Expected input fields:
    - official: bool
    - hit or hits: exact hit indicator/count for the evaluated ticket set
    - return_yen: realized gross return for the ticket set
    - race_date or date

    A non-official race becomes invalid_result and therefore carries zero
    economic investment under the common contract.
    """
    if ticket_count <= 0:
        raise ValueError("ticket_count must be positive")
    official = bool(row.get("official"))
    raw_hits = row.get("hits", row.get("hit", 0))
    try:
        hit_count = int(raw_hits)
    except Exception:
        hit_count = int(bool(raw_hits))
    hit = hit_count > 0
    returned = max(0, _safe_int(row.get("return_yen"), 0))
    payout = max(0, _safe_int(row.get("payout_yen"), returned))
    race_date = str(row.get("race_date") or row.get("date") or "")
    return {
        **dict(row),
        "race_date": race_date,
        "evaluation_status": VALID_ECONOMIC_STATUS if official else INVALID_ECONOMIC_STATUS,
        "investment_yen": investment_yen_per_bet * ticket_count if official else 0,
        "hit": hit if official else False,
        "return_yen": returned if official else 0,
        "payout_yen": payout if official and hit else 0,
    }


def normalize_formal_settlement_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    investment_yen_per_bet: int = DEFAULT_UNIT_YEN,
    ticket_count: int = 1,
) -> list[dict[str, Any]]:
    return [
        normalize_formal_settlement_row(
            row,
            investment_yen_per_bet=investment_yen_per_bet,
            ticket_count=ticket_count,
        )
        for row in rows
    ]


def forward_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    unit_yen: int = DEFAULT_UNIT_YEN,
    bootstrap_samples: int = 20_000,
    bootstrap_seed: int = 20260927,
) -> dict[str, Any]:
    return {
        "coverage": coverage(rows),
        "overall": metrics(rows, unit_yen=unit_yen),
        "risk": risk(rows, unit_yen=unit_yen),
        "chronological_halves": chronological_halves(rows, unit_yen=unit_yen),
        "by_day": by_calendar_key(rows, key_len=10, unit_yen=unit_yen),
        "by_month": by_calendar_key(rows, key_len=7, unit_yen=unit_yen),
        "day_bootstrap": day_bootstrap(
            rows,
            samples=bootstrap_samples,
            seed=bootstrap_seed,
            unit_yen=unit_yen,
        ),
        "promotion_allowed": False,
        "production_change": False,
        "purchase_action": False,
    }
