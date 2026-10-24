# -*- coding: utf-8 -*-
"""Pure replay bridge from immutable V4 formal artifacts to 1..5 point economics.

The bridge never regenerates ticket ranks. It accepts only ranks already
preserved in the pre-result artifact, verifies that the preserved top two match
formal core tickets, joins an exact-six finalized outcome set, then delegates to
the frozen marginal-revenue evaluator.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from research.v4_point_count_marginal_revenue import (
    CONTRACT,
    evaluate_point_counts,
)

ARTIFACT_CONTRACT = "candidate_discovery_v4_main_feed_v1"
OUTCOMES_CONTRACT = "v4_point_count_formal_outcomes_v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_CORE_RACES = 6
EXPECTED_RESEARCH_RANKS = 5
EXPECTED_FORMAL_TICKETS = 2
STAKE_PER_TICKET_YEN = 100


class V4PointCountFormalReplayError(ValueError):
    pass


def _aware(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise V4PointCountFormalReplayError(
            f"{field} must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise V4PointCountFormalReplayError(
            f"{field} is not valid ISO datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V4PointCountFormalReplayError(
            f"{field} must be timezone-aware"
        )
    return parsed


def _ticket(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise V4PointCountFormalReplayError(f"{field} must be a string")
    parts = value.split("-")
    if (
        len(parts) != 3
        or any(not part.isdigit() for part in parts)
        or len(set(parts)) != 3
        or any(not (1 <= int(part) <= 6) for part in parts)
    ):
        raise V4PointCountFormalReplayError(
            f"{field} must be a valid trifecta ticket"
        )
    return value


def build_day_input(
    artifact: Any,
    *,
    artifact_sha256: str,
    outcomes: Any,
) -> dict[str, Any]:
    if not isinstance(artifact, dict) or artifact.get("contract") != ARTIFACT_CONTRACT:
        raise V4PointCountFormalReplayError("unexpected formal artifact contract")
    if artifact.get("prospective_evidence_eligible") is not True:
        raise V4PointCountFormalReplayError(
            "formal artifact is not prospective-evidence eligible"
        )
    if artifact.get("purchase_action") is not False:
        raise V4PointCountFormalReplayError(
            "formal artifact purchase_action must be false"
        )
    if (
        not isinstance(artifact_sha256, str)
        or SHA256_RE.fullmatch(artifact_sha256) is None
    ):
        raise V4PointCountFormalReplayError(
            "artifact_sha256 must be lowercase 64-hex"
        )

    provenance = artifact.get("freeze_provenance")
    if not isinstance(provenance, dict):
        raise V4PointCountFormalReplayError("freeze_provenance missing")
    if provenance.get("all_frozen_rows_pre_deadline") is not True:
        raise V4PointCountFormalReplayError(
            "formal artifact lacks pre-deadline freeze proof"
        )
    if provenance.get("outcome_read") is not False or provenance.get("payout_read") is not False:
        raise V4PointCountFormalReplayError(
            "formal artifact result/payout-read invariant violated"
        )

    target_date = provenance.get("target_date")
    if not isinstance(target_date, str):
        raise V4PointCountFormalReplayError("target_date missing")

    generated = _aware(
        artifact.get("generated_at_jst"),
        field="artifact generated_at_jst",
    )
    completed = _aware(
        provenance.get("completed_at_jst"),
        field="freeze_provenance completed_at_jst",
    )
    if generated != completed:
        raise V4PointCountFormalReplayError(
            "artifact generated_at_jst must equal freeze completion"
        )

    feed = artifact.get("feed")
    if not isinstance(feed, list):
        raise V4PointCountFormalReplayError("formal artifact feed missing")
    core = [
        row
        for row in feed
        if isinstance(row, dict)
        and not bool(row.get("legacy_carryover"))
        and row.get("daily_rank") is not None
    ]
    if len(core) != EXPECTED_CORE_RACES:
        raise V4PointCountFormalReplayError(
            "formal artifact must contain exactly six core races"
        )
    ranks = sorted(int(row.get("daily_rank") or 0) for row in core)
    if ranks != list(range(1, EXPECTED_CORE_RACES + 1)):
        raise V4PointCountFormalReplayError(
            "formal core daily_rank must be exactly 1..6"
        )

    if not isinstance(outcomes, dict) or outcomes.get("contract") != OUTCOMES_CONTRACT:
        raise V4PointCountFormalReplayError("unexpected outcomes contract")
    if outcomes.get("target_date") != target_date:
        raise V4PointCountFormalReplayError("outcomes target_date mismatch")
    outcome_rows = outcomes.get("races")
    if not isinstance(outcome_rows, list):
        raise V4PointCountFormalReplayError("outcome races missing")

    by_race: dict[str, dict[str, Any]] = {}
    for outcome in outcome_rows:
        if not isinstance(outcome, dict):
            raise V4PointCountFormalReplayError("outcome row must be an object")
        race_id = outcome.get("race_id")
        if not isinstance(race_id, str) or race_id in by_race:
            raise V4PointCountFormalReplayError(
                "outcome race_id missing or duplicated"
            )
        if outcome.get("status") != "final":
            raise V4PointCountFormalReplayError(
                f"outcome must be final: {race_id}"
            )
        by_race[race_id] = outcome

    core_ids = {str(row.get("race_id") or "") for row in core}
    if set(by_race) != core_ids:
        raise V4PointCountFormalReplayError(
            "outcomes must equal the exact six formal core race IDs"
        )

    races: list[dict[str, Any]] = []
    for row in sorted(core, key=lambda item: int(item["daily_rank"])):
        race_id = str(row.get("race_id") or "")
        if not race_id.startswith(target_date.replace("-", "") + "_"):
            raise V4PointCountFormalReplayError(
                f"formal core target_date mismatch: {race_id}"
            )

        deadline = _aware(
            row.get("deadline_at"),
            field=f"{race_id} deadline_at",
        )
        if generated >= deadline:
            raise V4PointCountFormalReplayError(
                f"formal ranking evidence is not pre-deadline: {race_id}"
            )

        formal_tickets = [
            ticket
            for ticket in (row.get("tickets") or [])
            if isinstance(ticket, dict) and ticket.get("core_order") in (1, 2)
        ]
        formal_tickets.sort(key=lambda ticket: int(ticket["core_order"]))
        if [ticket.get("core_order") for ticket in formal_tickets] != [1, 2]:
            raise V4PointCountFormalReplayError(
                f"formal TOP2 ticket contract mismatch: {race_id}"
            )
        formal_top2 = [
            _ticket(ticket.get("ticket"), field=f"{race_id} formal ticket")
            for ticket in formal_tickets
        ]

        research = row.get("research_ranked_tickets")
        if not isinstance(research, list) or len(research) != EXPECTED_RESEARCH_RANKS:
            raise V4PointCountFormalReplayError(
                f"{race_id} must preserve exactly five pre-result ticket ranks"
            )
        ranked = [
            _ticket(ticket, field=f"{race_id} research ranked ticket")
            for ticket in research
        ]
        if len(set(ranked)) != EXPECTED_RESEARCH_RANKS:
            raise V4PointCountFormalReplayError(
                f"{race_id} research ranked tickets must be unique"
            )
        if ranked[:EXPECTED_FORMAL_TICKETS] != formal_top2:
            raise V4PointCountFormalReplayError(
                f"{race_id} research top two do not match formal core tickets"
            )

        outcome = by_race[race_id]
        actual = _ticket(
            outcome.get("actual_trifecta"),
            field=f"{race_id} actual_trifecta",
        )
        payout = outcome.get("trifecta_payout_yen")
        if (
            not isinstance(payout, int)
            or isinstance(payout, bool)
            or payout < 0
        ):
            raise V4PointCountFormalReplayError(
                f"{race_id} trifecta_payout_yen must be nonnegative integer"
            )

        races.append(
            {
                "race_id": race_id,
                "deadline_at": row["deadline_at"],
                "daily_rank": int(row["daily_rank"]),
                "ranked_tickets": ranked,
                "actual_trifecta": actual,
                "trifecta_payout_yen": payout,
            }
        )

    return {
        "target_date": target_date,
        "ranking_evidence_generated_at": artifact["generated_at_jst"],
        "ranking_evidence_sha256": artifact_sha256,
        "ranking_count": EXPECTED_RESEARCH_RANKS,
        "races": races,
    }


def outcomes_from_post_result_eval(data: Any) -> dict[str, Any]:
    if (
        not isinstance(data, dict)
        or data.get("contract") != "candidate_discovery_v4_post_result_eval_v1"
    ):
        raise V4PointCountFormalReplayError(
            "unexpected post-result evaluation contract"
        )
    if data.get("formal_core_only") is not True:
        raise V4PointCountFormalReplayError(
            "post-result evaluation must be formal-core only"
        )
    if data.get("legacy_excluded_from_formal_metrics") is not True:
        raise V4PointCountFormalReplayError(
            "post-result evaluation must exclude legacy metrics"
        )
    if data.get("stake_per_ticket_yen") != STAKE_PER_TICKET_YEN:
        raise V4PointCountFormalReplayError(
            "post-result evaluation stake must remain fixed at 100"
        )

    target_date = data.get("target_date")
    if not isinstance(target_date, str):
        raise V4PointCountFormalReplayError(
            "post-result evaluation target_date missing"
        )
    races = data.get("races")
    if not isinstance(races, list) or len(races) != EXPECTED_CORE_RACES:
        raise V4PointCountFormalReplayError(
            "post-result evaluation must contain exactly six races"
        )

    converted = []
    seen: set[str] = set()
    exact_hits = 0
    gross_return = 0
    for row in races:
        if not isinstance(row, dict):
            raise V4PointCountFormalReplayError(
                "post-result evaluation race must be an object"
            )
        race_id = row.get("race_id")
        if not isinstance(race_id, str) or race_id in seen:
            raise V4PointCountFormalReplayError(
                "post-result evaluation race_id missing or duplicated"
            )
        seen.add(race_id)

        predicted = row.get("predicted_tickets")
        if (
            not isinstance(predicted, list)
            or len(predicted) != EXPECTED_FORMAL_TICKETS
        ):
            raise V4PointCountFormalReplayError(
                f"post-result predicted_tickets must contain exact formal top two: {race_id}"
            )
        normalized_predicted = [
            _ticket(
                ticket,
                field=f"{race_id} post-result predicted ticket",
            )
            for ticket in predicted
        ]
        if len(set(normalized_predicted)) != EXPECTED_FORMAL_TICKETS:
            raise V4PointCountFormalReplayError(
                f"post-result predicted_tickets must be unique: {race_id}"
            )

        actual = _ticket(
            row.get("actual_trifecta"),
            field=f"{race_id} post-result actual_trifecta",
        )
        payout = row.get("trifecta_payout_yen")
        if (
            not isinstance(payout, int)
            or isinstance(payout, bool)
            or payout < 0
        ):
            raise V4PointCountFormalReplayError(
                f"{race_id} post-result payout must be nonnegative integer"
            )

        exact = actual in normalized_predicted
        if row.get("exact_hit") is not exact:
            raise V4PointCountFormalReplayError(
                f"post-result exact_hit disagrees with tickets/outcome: {race_id}"
            )
        exact_hits += int(exact)
        if exact:
            gross_return += payout

        converted.append(
            {
                "race_id": race_id,
                "status": "final",
                "actual_trifecta": actual,
                "trifecta_payout_yen": payout,
            }
        )

    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise V4PointCountFormalReplayError(
            "post-result evaluation summary missing"
        )
    expected_investment = (
        EXPECTED_CORE_RACES
        * EXPECTED_FORMAL_TICKETS
        * STAKE_PER_TICKET_YEN
    )
    checks = {
        "core_races": EXPECTED_CORE_RACES,
        "core_tickets": EXPECTED_CORE_RACES * EXPECTED_FORMAL_TICKETS,
        "exact_hit_races": exact_hits,
        "investment_yen": expected_investment,
        "gross_return_yen": gross_return,
        "profit_yen": gross_return - expected_investment,
    }
    mismatches = [
        key for key, expected in checks.items()
        if summary.get(key) != expected
    ]
    if mismatches:
        raise V4PointCountFormalReplayError(
            "post-result summary mismatch: " + ",".join(mismatches)
        )

    return {
        "contract": OUTCOMES_CONTRACT,
        "target_date": target_date,
        "races": converted,
    }


def evaluate_formal_replays(days: Any) -> dict[str, Any]:
    if not isinstance(days, list) or not days:
        raise V4PointCountFormalReplayError(
            "days must be a non-empty list"
        )

    built_days = []
    for record in days:
        if not isinstance(record, dict):
            raise V4PointCountFormalReplayError(
                "day replay record must be an object"
            )
        built_days.append(
            build_day_input(
                record.get("artifact"),
                artifact_sha256=record.get("artifact_sha256"),
                outcomes=record.get("outcomes"),
            )
        )

    return evaluate_point_counts(
        {
            "contract": CONTRACT,
            "stake_per_ticket_yen": STAKE_PER_TICKET_YEN,
            "max_requested_points": EXPECTED_RESEARCH_RANKS,
            "days": built_days,
        }
    )
