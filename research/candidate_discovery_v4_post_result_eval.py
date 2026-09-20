from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TICKET_RE = re.compile(r"^[1-6]-[1-6]-[1-6]$")


class V4PostResultEvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class Outcome:
    race_id: str
    trifecta: str
    trifecta_payout_yen: int


def _ticket_lanes(ticket: str) -> tuple[int, int, int]:
    if not isinstance(ticket, str) or TICKET_RE.fullmatch(ticket) is None:
        raise V4PostResultEvaluationError(f"malformed trifecta ticket: {ticket!r}")
    a, b, c = (int(x) for x in ticket.split("-"))
    if len({a, b, c}) != 3:
        raise V4PostResultEvaluationError(f"duplicate lane in trifecta ticket: {ticket}")
    return a, b, c


def _load_outcomes(data: Any) -> dict[str, Outcome]:
    if not isinstance(data, dict) or not isinstance(data.get("races"), list):
        raise V4PostResultEvaluationError("outcomes must contain a races list")
    rows: dict[str, Outcome] = {}
    for raw in data["races"]:
        if not isinstance(raw, dict):
            raise V4PostResultEvaluationError("outcome row must be an object")
        race_id = raw.get("race_id")
        trifecta = raw.get("trifecta")
        payout = raw.get("trifecta_payout_yen")
        if not isinstance(race_id, str) or not re.fullmatch(r"\d{8}_\d{2}_\d{2}", race_id):
            raise V4PostResultEvaluationError(f"malformed race_id: {race_id!r}")
        _ticket_lanes(trifecta)
        if not isinstance(payout, int) or isinstance(payout, bool) or payout < 0:
            raise V4PostResultEvaluationError(f"invalid trifecta payout: {payout!r}")
        if race_id in rows:
            raise V4PostResultEvaluationError(f"duplicate outcome race_id: {race_id}")
        rows[race_id] = Outcome(race_id, trifecta, payout)
    return rows


def evaluate(artifact: Any, outcomes_data: Any, *, stake_per_ticket_yen: int = 100) -> dict[str, Any]:
    if not isinstance(stake_per_ticket_yen, int) or isinstance(stake_per_ticket_yen, bool) or stake_per_ticket_yen <= 0:
        raise V4PostResultEvaluationError("stake_per_ticket_yen must be a positive integer")
    if not isinstance(artifact, dict):
        raise V4PostResultEvaluationError("artifact must be an object")
    if artifact.get("contract") != "candidate_discovery_v4_main_feed_v1":
        raise V4PostResultEvaluationError("unexpected artifact contract")
    if artifact.get("prospective_evidence_eligible") is not True:
        raise V4PostResultEvaluationError("artifact is not eligible prospective evidence")
    if artifact.get("purchase_action") is not False:
        raise V4PostResultEvaluationError("artifact purchase_action must be false")
    provenance = artifact.get("freeze_provenance")
    if not isinstance(provenance, dict) or provenance.get("all_frozen_rows_pre_deadline") is not True:
        raise V4PostResultEvaluationError("artifact lacks pre-deadline provenance")

    feed = artifact.get("feed")
    if not isinstance(feed, list):
        raise V4PostResultEvaluationError("artifact feed must be a list")

    core_rows = []
    for row in feed:
        if not isinstance(row, dict):
            raise V4PostResultEvaluationError("feed row must be an object")
        core_tickets = [
            t for t in row.get("tickets", [])
            if isinstance(t, dict) and isinstance(t.get("core_order"), int)
        ]
        if core_tickets:
            core_rows.append((row, sorted(core_tickets, key=lambda t: t["core_order"])))

    if len(core_rows) != 6:
        raise V4PostResultEvaluationError(f"formal core must contain exactly 6 races: {len(core_rows)}")

    outcomes = _load_outcomes(outcomes_data)
    evaluated = []
    total_tickets = 0
    exact_hits = 0
    head_hits = 0
    first_second_hits = 0
    third_only_misses = 0
    gross_return = 0

    seen_races: set[str] = set()
    for row, tickets in sorted(core_rows, key=lambda pair: pair[0].get("daily_rank", 999)):
        race_id = row.get("race_id")
        if not isinstance(race_id, str) or race_id in seen_races:
            raise V4PostResultEvaluationError(f"invalid or duplicate core race_id: {race_id!r}")
        seen_races.add(race_id)
        if len(tickets) != 2 or [t["core_order"] for t in tickets] != [1, 2]:
            raise V4PostResultEvaluationError(f"core race must contain exact orders 1 and 2: {race_id}")
        predicted = [t.get("ticket") for t in tickets]
        predicted_lanes = [_ticket_lanes(t) for t in predicted]
        if len(set(predicted)) != 2:
            raise V4PostResultEvaluationError(f"duplicate core ticket: {race_id}")

        outcome = outcomes.get(race_id)
        if outcome is None:
            raise V4PostResultEvaluationError(f"missing outcome for core race: {race_id}")
        actual = _ticket_lanes(outcome.trifecta)

        exact = outcome.trifecta in predicted
        head_hit = actual[0] == row.get("head_lane")
        prefix_hit = any(actual[:2] == lanes[:2] for lanes in predicted_lanes)
        third_only = prefix_hit and not exact

        total_tickets += 2
        exact_hits += int(exact)
        head_hits += int(head_hit)
        first_second_hits += int(prefix_hit)
        third_only_misses += int(third_only)
        if exact:
            gross_return += outcome.trifecta_payout_yen

        evaluated.append({
            "race_id": race_id,
            "daily_rank": row.get("daily_rank"),
            "tier": row.get("tier"),
            "head_lane": row.get("head_lane"),
            "predicted_tickets": predicted,
            "actual_trifecta": outcome.trifecta,
            "trifecta_payout_yen": outcome.trifecta_payout_yen,
            "exact_hit": exact,
            "head_hit": head_hit,
            "first_second_prefix_hit": prefix_hit,
            "third_only_miss": third_only,
        })

    investment = total_tickets * stake_per_ticket_yen
    profit = gross_return - investment
    roi = (gross_return / investment * 100.0) if investment else 0.0

    return {
        "contract": "candidate_discovery_v4_post_result_eval_v1",
        "target_date": provenance.get("target_date"),
        "formal_core_only": True,
        "legacy_excluded_from_formal_metrics": True,
        "stake_per_ticket_yen": stake_per_ticket_yen,
        "races": evaluated,
        "summary": {
            "core_races": len(evaluated),
            "core_tickets": total_tickets,
            "exact_hit_races": exact_hits,
            "head_hit_races": head_hits,
            "first_second_prefix_hit_races": first_second_hits,
            "third_only_miss_races": third_only_misses,
            "investment_yen": investment,
            "gross_return_yen": gross_return,
            "profit_yen": profit,
            "roi_percent": round(roi, 3),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one immutable formal V4 prospective artifact after results are final.")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--outcomes", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    artifact = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    outcomes = json.loads(Path(args.outcomes).read_text(encoding="utf-8"))
    result = evaluate(artifact, outcomes)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
