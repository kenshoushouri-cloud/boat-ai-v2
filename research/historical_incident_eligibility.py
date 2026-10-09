# -*- coding: utf-8 -*-
"""Pure historical V5 primary-fit incident eligibility guard.

Only consumes retrospective result-side evidence. Never infers incident
knowledge at the prediction cutoff, reconstructs a historic bet, or mutates
raw official results. Unknown/non-standard cases fail closed. This research
component does not activate V4/V5 Production decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Literal, Mapping, Sequence

from research.historical_void_registry import (
    EVIDENCE_REF as K_VOID_EVIDENCE_REF,
    VERIFIED_VOID_RACE_IDS,
)

State = Literal[
    "VERIFIED_K_VOID",
    "DB_CANCELLATION_INDICATED",
    "ABNORMAL_RESULT",
    "INSUFFICIENT_RESULT_EVIDENCE",
    "NO_INCIDENT_EVIDENCE",
]

_VALID_RACE_ID = re.compile(r"^\d{8}_\d{2}_(?:0[1-9]|1[0-2])$")
_NORMAL_FINISH = frozenset(f"{n:02d}" for n in range(1, 7))
_KNOWN_ABNORMAL = {
    "K0": "withdrawal",
    "K1": "withdrawal",
    "L0": "late",
    "L1": "late",
    "F": "flying",
    "S0": "incident_or_disqualification",
    "S1": "incident_or_disqualification",
    "S2": "incident_or_disqualification",
}
_TEXT_INCIDENT = ("失格", "妨", "転", "落", "沈", "事故")
_TEXT_WITHDRAWAL = ("欠", "取消")
_DB_CANCELLED = frozenset(("cancelled", "canceled"))
_BOOL_FIELDS = ("is_flying", "is_late")


def _status(raw: object) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str):
        return ""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", raw)).upper()


@dataclass(frozen=True)
class IncidentEligibility:
    race_id: str
    state: State
    categories: tuple[str, ...]
    primary_training_eligible: bool | None
    historical_incident_timing_proven: bool
    hypothetical_investment: int | None
    economics_policy: Literal[
        "VOID_ZERO_HYPOTHETICAL",
        "KEEP_ACTUAL_SETTLEMENT_SEPARATE",
        "DO_NOT_INFER_SETTLEMENT",
        "CHECK_ALL_OTHER_GATES",
    ]
    evidence_ref: str | None


def _decision(
    race_id: str,
    state: State,
    categories: set[str],
    evidence_ref: str | None,
) -> IncidentEligibility:
    if state == "VERIFIED_K_VOID":
        policy = "VOID_ZERO_HYPOTHETICAL"
        stake = 0
    elif state in ("DB_CANCELLATION_INDICATED", "ABNORMAL_RESULT"):
        policy = "KEEP_ACTUAL_SETTLEMENT_SEPARATE"
        stake = None
    elif state == "INSUFFICIENT_RESULT_EVIDENCE":
        policy = "DO_NOT_INFER_SETTLEMENT"
        stake = None
    else:
        policy = "CHECK_ALL_OTHER_GATES"
        stake = None
    return IncidentEligibility(
        race_id=race_id,
        state=state,
        categories=tuple(sorted(categories)),
        # Not even a normal result alone proves feature/timing/snapshot eligibility.
        primary_training_eligible=None if state == "NO_INCIDENT_EVIDENCE" else False,
        historical_incident_timing_proven=False,
        hypothetical_investment=stake,
        economics_policy=policy,
        evidence_ref=evidence_ref,
    )


def classify_historical_incident(
    race_id: str,
    result_entries: Sequence[Mapping[str, object]] | None,
    *,
    result_status: str | None = None,
    race_status: str | None = None,
) -> IncidentEligibility:
    """Return a retrospective research exclusion/abstention decision.

    result_entries are result-side participant rows, including lane,
    finish_status, is_flying, is_late. A normal six-row return never grants
    training eligibility by itself. Missing columns/flags fail closed.
    """
    if not isinstance(race_id, str) or not _VALID_RACE_ID.fullmatch(race_id):
        raise ValueError("Expected canonical YYYYMMDD_VV_RR race_id")

    # Priority: independent, race-specific official K cancellation evidence.
    if race_id in VERIFIED_VOID_RACE_IDS:
        return _decision(race_id, "VERIFIED_K_VOID", {"whole_race_void"}, K_VOID_EVIDENCE_REF)

    statuses = tuple(_status(x).lower() for x in (result_status, race_status))
    if any(x in _DB_CANCELLED for x in statuses):
        # The DB flag is retrospective indication, not separately K-verified
        # cancellation, and not authority to rewrite official settlements.
        return _decision(race_id, "DB_CANCELLATION_INDICATED", {"db_cancellation"}, "v2_results_postrace_status")

    if result_entries is None or not isinstance(result_entries, (list, tuple)):
        return _decision(race_id, "INSUFFICIENT_RESULT_EVIDENCE", {"missing_result_entries"}, None)

    categories: set[str] = set()
    lanes: list[int] = []
    for entry in result_entries:
        if not isinstance(entry, Mapping):
            categories.add("malformed_result_row")
            continue
        lane = entry.get("lane")
        if isinstance(lane, bool) or not isinstance(lane, int) or lane not in range(1, 7):
            categories.add("invalid_lane")
        else:
            lanes.append(lane)
        status = _status(entry.get("finish_status"))
        if status in _KNOWN_ABNORMAL:
            categories.add(_KNOWN_ABNORMAL[status])
        elif status in _NORMAL_FINISH:
            pass
        elif any(s in status for s in _TEXT_WITHDRAWAL):
            categories.add("withdrawal")
        elif any(s in status for s in _TEXT_INCIDENT):
            categories.add("incident_or_disqualification")
        elif status:
            categories.add("unknown_finish_status")
        else:
            categories.add("missing_finish_status")
        for name in _BOOL_FIELDS:
            flag = entry.get(name)
            if not isinstance(flag, bool):
                categories.add("unknown_incident_flag")
            elif flag:
                categories.add("flying" if name == "is_flying" else "late")

    if len(result_entries) != 6 or sorted(lanes) != [1, 2, 3, 4, 5, 6]:
        categories.add("incomplete_or_duplicate_lanes")

    incident = categories & {
        "withdrawal", "flying", "late", "incident_or_disqualification",
    }
    if incident:
        return _decision(race_id, "ABNORMAL_RESULT", categories, "v2_result_entries_postrace")
    if categories:
        return _decision(race_id, "INSUFFICIENT_RESULT_EVIDENCE", categories, "v2_result_entries_postrace")
    return _decision(race_id, "NO_INCIDENT_EVIDENCE", set(), "v2_result_entries_postrace")
