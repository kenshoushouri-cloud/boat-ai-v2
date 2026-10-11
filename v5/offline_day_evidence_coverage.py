"""Read-only coverage / cutoff audit for offline V5 historical research.

Caller-provided inventory and timestamps are NOT independent official proof.
No source contract is allowlisted here: the audit cannot enable Forward/BUY.
The ledger covers frozen predictions, NO_BUY and PENDING alike; outcomes and
later captures must not retroactively turn a historical case into a real buy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
RID = re.compile(r"^\d{8}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])$")
# Remains empty until independent positive-source schema validation exists.
APPROVED_POSITIVE_SOURCE_SCHEMAS = frozenset()


@dataclass(frozen=True)
class DayEvidenceRow:
    race_id: str
    decision: str  # FROZEN, NO_BUY, PENDING; never inferred from results
    decision_cutoff_at: datetime | None
    deadline_at: datetime | None
    six_lanes: tuple[int, ...] | None
    six_lane_source_contract: str | None
    exhibition_first_observed_at: datetime | None
    exhibition_snapshot_at: datetime | None
    result_first_observed_at: datetime | None = None
    result_source_ref: str | None = None


@dataclass(frozen=True)
class RaceEvidenceAudit:
    race_id: str
    decision: str
    predecision_reasons: tuple[str, ...]
    result_reasons: tuple[str, ...]
    predecision_timestamps_consistent: bool
    historical_provenance_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class DayEvidenceAudit:
    day: date
    rows: tuple[RaceEvidenceAudit, ...]
    inventory_count: int
    frozen_count: int
    no_buy_count: int
    pending_count: int
    unaccounted_ids: tuple[str, ...]
    unexpected_ids: tuple[str, ...]
    caller_inventory_matches_decision_ledger: bool
    inventory_independently_verified: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _day_of_id(rid: object) -> date:
    if type(rid) is not str or not RID.fullmatch(rid):
        raise ValueError("RACE_ID_INVALID")
    try:
        return datetime.strptime(rid[:8], "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("RACE_ID_INVALID") from exc


def _aware(d: object) -> bool:
    return type(d) is datetime and d.tzinfo is not None and d.utcoffset() is not None


def _on_day(d: datetime, day: date) -> bool:
    return d.astimezone(JST).date() == day


def audit_day_evidence_coverage(
    day: date, inventory_race_ids: tuple[str, ...],
    inventory_source_ref: str, ledger: tuple[DayEvidenceRow, ...],
    frozen_race_ids: tuple[str, ...],
) -> DayEvidenceAudit:
    """Check claimed roster and time ordering without certifying their origin.

    This function deliberately has no result-based population filtering and no
    trust toggle. A caller's source_ref alone cannot prove the official roster.
    """
    if type(day) is not date or day < date(2025, 7, 1):
        raise ValueError("DAY_INVALID")
    if (type(inventory_source_ref) is not str or not inventory_source_ref.strip()
            or type(inventory_race_ids) is not tuple or not inventory_race_ids
            or type(ledger) is not tuple or type(frozen_race_ids) is not tuple):
        raise ValueError("INVENTORY_OR_LEDGER_INVALID")
    if any(type(r) is not DayEvidenceRow for r in ledger):
        raise ValueError("LEDGER_ROW_INVALID")
    inventory = tuple(inventory_race_ids)
    ledger_ids = tuple(row.race_id for row in ledger)
    for group in (inventory, ledger_ids, frozen_race_ids):
        if any(_day_of_id(rid) != day for rid in group):
            raise ValueError("CROSS_DAY_RACE_ID")
        if len(set(group)) != len(group):
            raise ValueError("DUPLICATE_RACE_ID")
    inventory_set = set(inventory)
    ledger_set = set(ledger_ids)
    frozen_set = set(frozen_race_ids)
    if not frozen_set <= ledger_set:
        raise ValueError("FROZEN_RACE_NOT_IN_LEDGER")
    unaccounted = tuple(sorted(inventory_set - ledger_set))
    unexpected = tuple(sorted(ledger_set - inventory_set))
    output = []
    for row in sorted(ledger, key=lambda r: r.race_id):
        reasons, result_reasons = [], []
        if row.decision not in ("FROZEN", "NO_BUY", "PENDING"):
            raise ValueError("DECISION_INVALID")
        if (row.race_id in frozen_set) != (row.decision == "FROZEN"):
            raise ValueError("FROZEN_DECISION_MISMATCH")
        if row.race_id not in inventory_set:
            reasons.append("RACE_NOT_IN_CLAIMED_INVENTORY")
        if (not _aware(row.deadline_at) or not _aware(row.decision_cutoff_at)
                or not _on_day(row.deadline_at, day)
                or not _on_day(row.decision_cutoff_at, day)
                or row.decision_cutoff_at >= row.deadline_at):
            reasons.append("DECISION_CLOCK_INVALID")
        if row.decision == "PENDING":
            reasons.append("PREDECISION_PENDING")
        if (type(row.six_lanes) is not tuple or len(row.six_lanes) != 6
                or any(type(x) is not int or x <= 0 for x in row.six_lanes)
                or len(set(row.six_lanes)) != 6):
            reasons.append("INDEPENDENT_SIX_LANE_POSITIVE_EVIDENCE_MISSING")
        # Even a well-formed claimant string cannot approve a source schema.
        if (type(row.six_lane_source_contract) is not str
                or row.six_lane_source_contract not in APPROVED_POSITIVE_SOURCE_SCHEMAS):
            reasons.append("OFFICIAL_POSITIVE_SOURCE_UNAPPROVED")
        if (not _aware(row.exhibition_first_observed_at)
                or not _aware(row.exhibition_snapshot_at)):
            reasons.append("ORIGINAL_FIRST_OBSERVATION_UNKNOWN")
        elif _aware(row.decision_cutoff_at) and _aware(row.deadline_at):
            if (row.exhibition_snapshot_at > row.decision_cutoff_at
                    or row.exhibition_first_observed_at > row.decision_cutoff_at):
                reasons.append("EXHIBITION_AFTER_DECISION_CUTOFF")
            if row.exhibition_first_observed_at > row.exhibition_snapshot_at:
                reasons.append("OBSERVATION_AFTER_SNAPSHOT_INCONSISTENT")
        if not _aware(row.result_first_observed_at):
            result_reasons.append("RESULT_FIRST_OBSERVATION_UNKNOWN")
        elif _aware(row.deadline_at) and row.result_first_observed_at < row.deadline_at:
            result_reasons.append("RESULT_OBSERVATION_BEFORE_DEADLINE_SUSPECT")
        if type(row.result_source_ref) is not str or not row.result_source_ref.strip():
            result_reasons.append("RESULT_SOURCE_MISSING")
        # Local timestamps and caller source IDs never verify authenticity.
        reasons.append("ORIGINAL_CAPTURE_INDEPENDENTLY_UNVERIFIED")
        result_reasons.append("RESULT_ORIGIN_INDEPENDENTLY_UNVERIFIED")
        output.append(RaceEvidenceAudit(row.race_id, row.decision, tuple(reasons),
                                        tuple(result_reasons),
                                        not any(x in reasons for x in (
                                            "DECISION_CLOCK_INVALID",
                                            "ORIGINAL_FIRST_OBSERVATION_UNKNOWN",
                                            "EXHIBITION_AFTER_DECISION_CUTOFF",
                                            "OBSERVATION_AFTER_SNAPSHOT_INCONSISTENT"))))
    return DayEvidenceAudit(day, tuple(output), len(inventory), len(frozen_set),
                            sum(r.decision == "NO_BUY" for r in ledger),
                            sum(r.decision == "PENDING" for r in ledger),
                            unaccounted, unexpected,
                            not unaccounted and not unexpected)
