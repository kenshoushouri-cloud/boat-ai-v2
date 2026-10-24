# -*- coding: utf-8 -*-
"""Offline evaluator for the preregistered V4 economic rank-pair reranker.

Consumes one immutable long-history JSON artifact only. No DB, network, odds,
market rank, LINE, persistence, or purchase surface exists here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from research.v4_economic_reranker_contract import (
    BLOCK_COUNT,
    CONTROL_PAIR,
    POINTS_PER_RACE,
    UNIT_YEN,
    choose_pair_for_block,
    freeze_pair,
)

EXPECTED_SOURCE_JSON_SHA256 = (
    "4f814a4c5a89e7f014ca32a91ef9e477ce076ebd1527eeab306c96be5759b286"
)
EXPECTED_SOURCE_CONTRACT = "v4_long_history_walkforward_v1"
EXPECTED_EVALUATED_DAYS = 432
EXPECTED_EVALUATED_RACES = 2592
EXPECTED_RACES_PER_DAY = 6
BOOTSTRAP_SAMPLES = 20000
BOOTSTRAP_SEED = 20260924


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _block_for_date(day: date, blocks: Sequence[Mapping[str, Any]]) -> int:
    matches = []
    for block in blocks:
        start = date.fromisoformat(str(block["start_date"]))
        end = date.fromisoformat(str(block["end_date"]))
        if start <= day <= end:
            matches.append(int(block["block"]))
    if len(matches) != 1:
        raise ValueError(f"date {day} does not map to exactly one block")
    return matches[0]


def load_immutable_source(path: Path) -> dict[str, Any]:
    digest = sha256_file(path)
    if digest != EXPECTED_SOURCE_JSON_SHA256:
        raise ValueError(
            f"source JSON SHA mismatch: expected={EXPECTED_SOURCE_JSON_SHA256} got={digest}"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_source(data)
    return data


def validate_source(data: Mapping[str, Any]) -> None:
    if data.get("contract") != EXPECTED_SOURCE_CONTRACT:
        raise ValueError("unexpected source contract")

    coverage = data.get("coverage")
    if not isinstance(coverage, Mapping):
        raise ValueError("missing coverage")
    if int(coverage.get("evaluated_days") or -1) != EXPECTED_EVALUATED_DAYS:
        raise ValueError("evaluated day count drift")
    if int(coverage.get("evaluated_races") or -1) != EXPECTED_EVALUATED_RACES:
        raise ValueError("evaluated race count drift")

    blocks = data.get("walkforward_blocks")
    if not isinstance(blocks, list) or len(blocks) != BLOCK_COUNT:
        raise ValueError("walkforward block count drift")
    expected_ids = list(range(1, BLOCK_COUNT + 1))
    actual_ids = [int(block.get("block") or 0) for block in blocks]
    if actual_ids != expected_ids:
        raise ValueError("walkforward block identity drift")

    records = data.get("evaluated_race_records")
    if not isinstance(records, list) or len(records) != EXPECTED_EVALUATED_RACES:
        raise ValueError("evaluated race records drift")

    by_day: dict[str, int] = {}
    by_block_days: dict[int, set[str]] = {i: set() for i in expected_ids}
    by_block_races: dict[int, int] = {i: 0 for i in expected_ids}
    seen_race_ids: set[str] = set()

    for row in records:
        rid = str(row.get("race_id") or "")
        day_text = str(row.get("date") or "")
        ranked = row.get("ranked_top5")
        actual = str(row.get("actual_trifecta") or "")
        payout = int(row.get("payout_yen") or 0)

        if not rid or rid in seen_race_ids:
            raise ValueError("missing/duplicate race_id")
        seen_race_ids.add(rid)
        day = date.fromisoformat(day_text)
        if not isinstance(ranked, list) or len(ranked) != 5 or len(set(ranked)) != 5:
            raise ValueError(f"invalid frozen Top5 for {rid}")
        if actual not in {
            f"{a}-{b}-{c}"
            for a in range(1, 7)
            for b in range(1, 7)
            for c in range(1, 7)
            if len({a, b, c}) == 3
        }:
            raise ValueError(f"invalid actual trifecta for {rid}")
        if payout <= 0:
            raise ValueError(f"invalid payout for {rid}")

        block = _block_for_date(day, blocks)
        by_day[day_text] = by_day.get(day_text, 0) + 1
        by_block_days[block].add(day_text)
        by_block_races[block] += 1

    if len(by_day) != EXPECTED_EVALUATED_DAYS:
        raise ValueError("unique evaluated day count drift")
    if any(count != EXPECTED_RACES_PER_DAY for count in by_day.values()):
        raise ValueError("source no longer has exact six races on every evaluated day")

    for block in blocks:
        block_id = int(block["block"])
        expected_days = int(block["days"])
        if len(by_block_days[block_id]) != expected_days:
            raise ValueError(f"block {block_id} evaluated day count drift")
        if by_block_races[block_id] != expected_days * EXPECTED_RACES_PER_DAY:
            raise ValueError(f"block {block_id} race count drift")


def rows_with_blocks(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    blocks = data["walkforward_blocks"]
    rows = []
    for source in data["evaluated_race_records"]:
        row = dict(source)
        row["block"] = _block_for_date(date.fromisoformat(str(row["date"])), blocks)
        rows.append(row)
    return sorted(rows, key=lambda r: (str(r["date"]), str(r["race_id"])))


def settle_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    pair_by_block: Mapping[int, tuple[int, int]],
) -> dict[str, Any]:
    investment = 0
    gross = 0
    hits = 0
    equity = 0
    peak = 0
    max_drawdown = 0
    hit_returns: list[int] = []
    by_block: dict[int, dict[str, Any]] = {}

    for row in rows:
        block = int(row["block"])
        pair = pair_by_block[block]
        tickets = freeze_pair(row["ranked_top5"], pair)
        actual = str(row["actual_trifecta"])
        payout = int(row["payout_yen"])
        hit = actual in tickets
        returned = payout if hit else 0

        investment += POINTS_PER_RACE * UNIT_YEN
        gross += returned
        hits += int(hit)
        if hit:
            hit_returns.append(returned)

        equity += returned - POINTS_PER_RACE * UNIT_YEN
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

        b = by_block.setdefault(
            block,
            {
                "block": block,
                "pair": list(pair),
                "races": 0,
                "investment_yen": 0,
                "gross_return_yen": 0,
                "hits": 0,
            },
        )
        b["races"] += 1
        b["investment_yen"] += POINTS_PER_RACE * UNIT_YEN
        b["gross_return_yen"] += returned
        b["hits"] += int(hit)

    for block in sorted(by_block):
        b = by_block[block]
        b["profit_yen"] = b["gross_return_yen"] - b["investment_yen"]
        b["roi_percent"] = round(
            b["gross_return_yen"] / b["investment_yen"] * 100.0, 3
        )
        b["hit_rate_percent"] = round(b["hits"] / b["races"] * 100.0, 3)

    return {
        "races": len(rows),
        "bets": len(rows) * POINTS_PER_RACE,
        "investment_yen": investment,
        "gross_return_yen": gross,
        "profit_yen": gross - investment,
        "roi_percent": round(gross / investment * 100.0, 3),
        "hits": hits,
        "hit_rate_percent": round(hits / len(rows) * 100.0, 3),
        "max_drawdown_yen": max_drawdown,
        "largest_hit_share_percent": round(
            max(hit_returns) / gross * 100.0, 3
        ) if hit_returns and gross else 0.0,
        "blocks": [by_block[b] for b in sorted(by_block)],
    }


def select_walkforward_pairs(rows: Sequence[Mapping[str, Any]]) -> dict[int, tuple[int, int]]:
    selected: dict[int, tuple[int, int]] = {}
    for block in range(1, BLOCK_COUNT + 1):
        selected[block] = choose_pair_for_block(rows, current_block=block)
    return selected


def paired_block_bootstrap(
    selected: Mapping[str, Any],
    control: Mapping[str, Any],
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    s_by = {int(row["block"]): row for row in selected["blocks"]}
    c_by = {int(row["block"]): row for row in control["blocks"]}
    eval_blocks = list(range(3, BLOCK_COUNT + 1))
    if set(eval_blocks) - set(s_by) or set(eval_blocks) - set(c_by):
        raise ValueError("missing evaluation block for bootstrap")

    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(samples):
        gross_delta = 0
        investment = 0
        for _ in eval_blocks:
            block = eval_blocks[rng.randrange(len(eval_blocks))]
            gross_delta += int(s_by[block]["gross_return_yen"]) - int(
                c_by[block]["gross_return_yen"]
            )
            investment += int(c_by[block]["investment_yen"])
        deltas.append(gross_delta / investment * 100.0)

    deltas.sort()

    def quantile(p: float) -> float:
        idx = int(round((len(deltas) - 1) * p))
        return round(deltas[max(0, min(idx, len(deltas) - 1))], 3)

    return {
        "blocks": eval_blocks,
        "samples": samples,
        "seed": seed,
        "roi_delta_pp_p025": quantile(0.025),
        "roi_delta_pp_median": quantile(0.5),
        "roi_delta_pp_p975": quantile(0.975),
        "positive_share_percent": round(
            sum(value > 0.0 for value in deltas) / len(deltas) * 100.0, 3
        ),
    }


def evaluate(data: Mapping[str, Any]) -> dict[str, Any]:
    validate_source(data)
    rows = rows_with_blocks(data)

    selected_pairs = select_walkforward_pairs(rows)
    control_pairs = {block: CONTROL_PAIR for block in range(1, BLOCK_COUNT + 1)}

    selected = settle_rows(rows, pair_by_block=selected_pairs)
    control = settle_rows(rows, pair_by_block=control_pairs)

    s_by = {int(row["block"]): row for row in selected["blocks"]}
    c_by = {int(row["block"]): row for row in control["blocks"]}
    block_comparison = []
    wins = ties = losses = 0
    for block in range(1, BLOCK_COUNT + 1):
        delta = round(
            float(s_by[block]["roi_percent"]) - float(c_by[block]["roi_percent"]),
            3,
        )
        if delta > 0:
            wins += 1
        elif delta < 0:
            losses += 1
        else:
            ties += 1
        block_comparison.append(
            {
                "block": block,
                "selected_pair": list(selected_pairs[block]),
                "selected_roi_percent": s_by[block]["roi_percent"],
                "control_roi_percent": c_by[block]["roi_percent"],
                "delta_pp": delta,
            }
        )

    return {
        "contract": "v4_economic_reranker_walkforward_v1",
        "source": {
            "expected_json_sha256": EXPECTED_SOURCE_JSON_SHA256,
            "evaluated_days": EXPECTED_EVALUATED_DAYS,
            "evaluated_races": EXPECTED_EVALUATED_RACES,
        },
        "volume_invariants": {
            "selected_races_per_day": EXPECTED_RACES_PER_DAY,
            "points_per_race": POINTS_PER_RACE,
            "selected_races_equal_control": selected["races"] == control["races"],
            "bets_equal_control": selected["bets"] == control["bets"],
            "candidate_skip": False,
        },
        "control": control,
        "walkforward": selected,
        "overall_delta": {
            "profit_yen": selected["profit_yen"] - control["profit_yen"],
            "roi_pp": round(
                selected["roi_percent"] - control["roi_percent"], 3
            ),
            "hits": selected["hits"] - control["hits"],
        },
        "block_comparison": block_comparison,
        "block_record": {
            "wins": wins,
            "ties": ties,
            "losses": losses,
        },
        "paired_block_bootstrap": paired_block_bootstrap(selected, control),
        "policy": {
            "market_input_used": False,
            "odds_gate_used": False,
            "venue_filter_used": False,
            "race_number_filter_used": False,
            "result_after_current_block_freeze": True,
            "production_change_allowed": False,
            "purchase_action": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_json", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("v4-economic-reranker-walkforward.json"),
    )
    args = parser.parse_args()

    data = load_immutable_source(args.source_json)
    result = evaluate(data)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("V4_ECONOMIC_RERANKER_SOURCE_SHA=" + EXPECTED_SOURCE_JSON_SHA256)
    print(
        "V4_ECONOMIC_RERANKER_VOLUME="
        f"races:{result['walkforward']['races']} bets:{result['walkforward']['bets']}"
    )
    for row in result["block_comparison"]:
        print(
            "BLOCK={block} PAIR={selected_pair} SELECTED_ROI={selected_roi_percent} "
            "CONTROL_ROI={control_roi_percent} DELTA_PP={delta_pp}".format(**row)
        )
    print(
        "OVERALL="
        + json.dumps(result["overall_delta"], sort_keys=True)
    )
    print(
        "BLOCK_RECORD="
        + json.dumps(result["block_record"], sort_keys=True)
    )
    print(
        "BOOTSTRAP="
        + json.dumps(result["paired_block_bootstrap"], sort_keys=True)
    )
    print("PURCHASE_ACTION=false")
    print("RESULT=PASS_OFFLINE_ECONOMIC_RERANKER")


if __name__ == "__main__":
    main()
