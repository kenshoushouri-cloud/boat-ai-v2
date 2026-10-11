"""Bind an actual offline FrozenDay to the retrospective day-evidence audit.

FROZEN in the evidence ledger denotes frozen *selected hypothetical tickets*,
not an actual purchase. FrozenRace with zero tickets must instead be NO_BUY.
PENDING rows have no corresponding FrozenRace. Nothing here authenticates the
claimed official roster or independently proves the first observation time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from v5.offline_day_evidence_coverage import (
    DayEvidenceAudit, DayEvidenceRow, audit_day_evidence_coverage,
)
from v5.offline_prior_day_counter_update import FrozenDay, FrozenRace


@dataclass(frozen=True)
class FrozenDayEvidenceBinding:
    audit: DayEvidenceAudit
    actual_frozen_race_ids: tuple[str, ...]
    frozen_hypothetical_ticket_ids: tuple[str, ...]
    frozen_no_buy_ids: tuple[str, ...]
    # A caller-submitted official roster and a FrozenDay are still not
    # independent proof of six active starters or historic capture timing.
    independently_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def audit_actual_frozen_day(
    frozen_day: FrozenDay,
    inventory_race_ids: tuple[str, ...],
    inventory_source_ref: str,
    ledger: tuple[DayEvidenceRow, ...],
    claimed_frozen_race_ids: tuple[str, ...],
) -> FrozenDayEvidenceBinding:
    """Fail closed on any claimed-vs-actual FrozenDay discrepancy.

    The caller must supply a ledger for every FrozenRace and preserve any
    other inventoried races as PENDING (without manufacturing a frozen guess).
    NO_BUY FrozenRace predictions remain in the overall frozen cohort, but the
    underlying evidence audit's FROZEN count means ticketed predictions only.
    """
    if (type(frozen_day) is not FrozenDay or type(frozen_day.day) is not date
            or type(frozen_day.baseline_fitted_through) is not date
            or frozen_day.baseline_fitted_through >= frozen_day.day
            or type(frozen_day.races) is not tuple or not frozen_day.races
            or type(claimed_frozen_race_ids) is not tuple
            or type(ledger) is not tuple):
        raise ValueError("ACTUAL_FROZEN_DAY_REQUIRED")
    actual = {}
    for race in frozen_day.races:
        if (type(race) is not FrozenRace or type(race.race_id) is not str
                or type(race.selected_tickets) is not tuple):
            raise ValueError("FROZEN_RACE_SHAPE_INVALID")
        if race.race_id in actual:
            raise ValueError("DUPLICATE_ACTUAL_FROZEN_RACE")
        actual[race.race_id] = race
    if (len(claimed_frozen_race_ids) != len(actual)
            or len(set(claimed_frozen_race_ids)) != len(actual)
            or set(claimed_frozen_race_ids) != set(actual)):
        raise ValueError("CLAIMED_FROZEN_IDS_MISMATCH")
    rows = {}
    for entry in ledger:
        if type(entry) is not DayEvidenceRow:
            raise ValueError("EVIDENCE_LEDGER_ROW_INVALID")
        if entry.race_id in rows:
            raise ValueError("DUPLICATE_LEDGER_RACE")
        rows[entry.race_id] = entry
    if set(actual) - set(rows):
        raise ValueError("ACTUAL_FROZEN_RACE_MISSING_FROM_LEDGER")
    for rid, entry in rows.items():
        if rid not in actual:
            # Unfrozen race outcome cannot establish a historical NO_BUY.
            if entry.decision != "PENDING":
                raise ValueError("UNFROZEN_RACE_MUST_BE_PENDING")
            continue
        race = actual[rid]
        expected = "FROZEN" if race.selected_tickets else "NO_BUY"
        if entry.decision != expected:
            raise ValueError("FROZEN_TICKET_DECISION_MISMATCH")
        # An entry may omit its six-lane source to remain HOLD. But a
        # contradictory claimed six-lane identity cannot be allowed through.
        if entry.six_lanes is not None and entry.six_lanes != race.racer_numbers:
            raise ValueError("FROZEN_RACER_IDENTITY_MISMATCH")

    ticketed_ids = tuple(sorted(rid for rid, r in actual.items()
                               if r.selected_tickets))
    no_buy_ids = tuple(sorted(set(actual) - set(ticketed_ids)))
    base = audit_day_evidence_coverage(
        frozen_day.day, inventory_race_ids, inventory_source_ref, ledger,
        ticketed_ids,
    )
    return FrozenDayEvidenceBinding(
        base, tuple(sorted(actual)), ticketed_ids, no_buy_ids,
    )
