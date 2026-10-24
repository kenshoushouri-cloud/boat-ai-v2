# -*- coding: utf-8 -*-
"""Storage-light shadow analyzer for value-candidate research.

Research-only utility. It never writes to PostgreSQL and never sends notifications.
It consumes a compact CSV export with one row per historical ticket and produces
aggregated JSON summaries only.

Required CSV columns:
    race_date,race_id,venue_id,race_no,ticket,odds,prob,hit

Optional columns are carried only for grouping when present. `hit` must be 0/1.
`prob` must be a pre-result probability generated from timing-safe inputs.

Example:
    python research_value_candidate_shadow.py \
      --input /tmp/value_rows.csv \
      --output /tmp/value_summary.json

This script intentionally does not import db_pg. Extraction from Production must be
performed separately under read-only controls so no accidental schema/data writes
can occur through this research utility.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ODDS_BANDS: Tuple[Tuple[float, float | None, str], ...] = (
    (1.5, 2.0, "1.5-2.0"),
    (2.0, 3.0, "2.0-3.0"),
    (3.0, 5.5, "3.0-5.5"),
    (5.5, 10.0, "5.5-10.0"),
    (10.0, 20.0, "10.0-20.0"),
    (20.0, None, "20.0+"),
)
DEFAULT_VALUE_GATES = (1.02, 1.05, 1.10, 1.15, 1.20)


@dataclass(frozen=True)
class Row:
    race_date: str
    race_id: str
    venue_id: str
    race_no: int
    ticket: str
    odds: float
    prob: float
    hit: int

    @property
    def value_ratio(self) -> float:
        return self.prob * self.odds

    @property
    def edge(self) -> float:
        return self.prob - (1.0 / self.odds)

    @property
    def month(self) -> str:
        return self.race_date[:7]


def _band(odds: float) -> str | None:
    for low, high, label in ODDS_BANDS:
        if odds >= low and (high is None or odds < high):
            return label
    return None


def _finite_float(value: str, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def load_rows(path: Path) -> List[Row]:
    rows: List[Row] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"race_date", "race_id", "venue_id", "race_no", "ticket", "odds", "prob", "hit"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")
        for line_no, raw in enumerate(reader, start=2):
            try:
                datetime.strptime(raw["race_date"][:10], "%Y-%m-%d")
                odds = _finite_float(raw["odds"], "odds")
                prob = _finite_float(raw["prob"], "prob")
                hit = int(raw["hit"])
                race_no = int(raw["race_no"])
            except Exception as exc:
                raise ValueError(f"invalid row at line {line_no}: {exc}") from exc
            if odds <= 1.0:
                raise ValueError(f"invalid odds at line {line_no}: {odds}")
            if not 0.0 <= prob <= 1.0:
                raise ValueError(f"invalid prob at line {line_no}: {prob}")
            if hit not in (0, 1):
                raise ValueError(f"invalid hit at line {line_no}: {hit}")
            rows.append(
                Row(
                    race_date=raw["race_date"][:10],
                    race_id=raw["race_id"].strip(),
                    venue_id=raw["venue_id"].strip(),
                    race_no=race_no,
                    ticket=raw["ticket"].strip(),
                    odds=odds,
                    prob=prob,
                    hit=hit,
                )
            )
    return rows


def longest_losing_streak(rows: Iterable[Row]) -> int:
    ordered = sorted(rows, key=lambda r: (r.race_date, r.race_id, r.ticket))
    longest = current = 0
    for row in ordered:
        if row.hit:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def stats(rows: Iterable[Row], stake_yen: int = 100) -> Dict[str, float | int | None]:
    selected = list(rows)
    n = len(selected)
    if n == 0:
        return {
            "candidates": 0,
            "hits": 0,
            "hit_rate": None,
            "turnover_yen": 0,
            "payout_yen": 0.0,
            "profit_yen": 0.0,
            "roi": None,
            "avg_value_ratio": None,
            "avg_edge": None,
            "longest_losing_streak": 0,
        }
    turnover = n * stake_yen
    payout = sum(stake_yen * row.odds for row in selected if row.hit)
    profit = payout - turnover
    return {
        "candidates": n,
        "hits": sum(row.hit for row in selected),
        "hit_rate": sum(row.hit for row in selected) / n,
        "turnover_yen": turnover,
        "payout_yen": round(payout, 2),
        "profit_yen": round(profit, 2),
        "roi": payout / turnover if turnover else None,
        "avg_value_ratio": sum(row.value_ratio for row in selected) / n,
        "avg_edge": sum(row.edge for row in selected) / n,
        "longest_losing_streak": longest_losing_streak(selected),
    }


def build_summary(rows: List[Row], gates: Iterable[float], stake_yen: int) -> Dict[str, object]:
    summary: Dict[str, object] = {
        "meta": {
            "rows": len(rows),
            "stake_yen_per_ticket": stake_yen,
            "odds_bands": [label for _, _, label in ODDS_BANDS],
            "value_gates": list(gates),
            "production_write": False,
            "line_send": False,
            "purchase_action": False,
        },
        "all": stats(rows, stake_yen),
        "by_odds_band": {},
        "by_gate": {},
    }

    by_band = summary["by_odds_band"]
    assert isinstance(by_band, dict)
    for _, _, label in ODDS_BANDS:
        by_band[label] = stats([r for r in rows if _band(r.odds) == label], stake_yen)

    by_gate = summary["by_gate"]
    assert isinstance(by_gate, dict)
    for gate in gates:
        selected = [r for r in rows if r.value_ratio >= gate and _band(r.odds) is not None]
        monthly: Dict[str, object] = {}
        venues: Dict[str, object] = {}
        months = sorted({r.month for r in selected})
        venue_ids = sorted({r.venue_id for r in selected})
        for month in months:
            monthly[month] = stats([r for r in selected if r.month == month], stake_yen)
        for venue_id in venue_ids:
            venues[venue_id] = stats([r for r in selected if r.venue_id == venue_id], stake_yen)
        by_gate[f"{gate:.2f}"] = {
            "overall": stats(selected, stake_yen),
            "monthly": monthly,
            "venues": venues,
            "odds_bands": {
                label: stats([r for r in selected if _band(r.odds) == label], stake_yen)
                for _, _, label in ODDS_BANDS
            },
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research-only value candidate analyzer")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stake-yen", type=int, default=100)
    parser.add_argument("--gates", default=",".join(str(v) for v in DEFAULT_VALUE_GATES))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stake_yen <= 0:
        raise ValueError("--stake-yen must be positive")
    gates = tuple(float(v.strip()) for v in args.gates.split(",") if v.strip())
    if not gates or any((not math.isfinite(v) or v <= 0) for v in gates):
        raise ValueError("--gates must contain positive finite values")
    rows = load_rows(args.input)
    out = build_summary(rows, gates, args.stake_yen)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["meta"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
