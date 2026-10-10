# -*- coding: utf-8 -*-
"""V5 synthetic 3-ren-tan cash ledger; NO real bet, source authentication or BUY.

Predeadline committed orders and postrace settlements are separate. The entire
predecision cohort remains counted, including refunded VOID races. Caller-held
bytes/timestamps/hashes are MOCK structure, not independently trusted evidence.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo('Asia/Tokyo')
RACE_ID = re.compile(r'(20\d{6})_(0[1-9]|1\d|2[0-4])\_(0[1-9]|1[0-2])\Z')
TICKET = re.compile(r'([1-6])-([1-6])-([1-6])\Z')
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
MAX_RACES = 500


@dataclass(frozen=True, slots=True)
class MockOrder:
    ticket: str
    stake_yen: int
    odds_decimal: float
    odds_observed_at: datetime
    purchase_executed_at: datetime
    purchase_receipt_ref: str


@dataclass(frozen=True, slots=True)
class PredeadlineMockRace:
    race_id: str
    cutoff_at: datetime
    first_observed_at: datetime
    frozen_at: datetime
    original_source_ref: str
    original_source_bytes: bytes
    original_sha256: str
    orders: tuple[MockOrder, ...]


@dataclass(frozen=True, slots=True)
class MockTicketReturn:
    ticket: str
    payout_yen: int
    refund_yen: int


@dataclass(frozen=True, slots=True)
class PostraceMockResult:
    race_id: str
    observed_at: datetime
    source_ref: str
    raw_result_bytes: bytes
    raw_result_sha256: str
    status: str  # OFFICIAL, VOID, PENDING
    winning_ticket: str | None
    returns: tuple[MockTicketReturn, ...]


@dataclass(frozen=True, slots=True)
class SyntheticDayCash:
    day: str
    candidate_races: int
    purchased_tickets: int
    paid_yen: int
    returns_yen: int
    net_yen: int


@dataclass(frozen=True, slots=True)
class SyntheticLedgerVerdict:
    reason: str
    mock_shape_consistent: bool = False
    predecision_races: int = 0
    purchased_tickets: int = 0
    official_races: int = 0
    void_races: int = 0
    winning_tickets: int = 0
    synthetic_paid_yen: int = 0
    synthetic_returns_yen: int = 0
    synthetic_net_yen: int = 0
    synthetic_roi_pct: float | None = None
    synthetic_ticket_hit_pct: float | None = None
    days: tuple[SyntheticDayCash, ...] = ()
    # Mock data never authorizes actual economic or purchase conclusions.
    independently_authenticated_source: bool = field(default=False, init=False)
    actual_purchase_verified: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _aware(t: object) -> bool:
    return type(t) is datetime and t.tzinfo is not None and t.utcoffset() is not None


def _ticket(t: object) -> bool:
    if type(t) is not str:
        return False
    m = TICKET.fullmatch(t)
    return m is not None and len(set(m.groups())) == 3


def _digest(raw: object, hexdigest: object) -> bool:
    return (type(raw) is bytes and 0 < len(raw) <= 2_097_152
            and type(hexdigest) is str and SHA256.fullmatch(hexdigest) is not None
            and hashlib.sha256(raw).hexdigest() == hexdigest)


def audit_synthetic_trifecta_cash_ledger(
    predecision: object, postrace: object,
) -> SyntheticLedgerVerdict:
    """Check a mock cash ledger, fail closed before producing ANY monetary totals.

    Actual odds authenticity, independently audited first capture, purchase,
    payout and refund provenance must be established elsewhere in the future.
    No odds-to-payout equality is assumed: final odds may differ from prebet odds.
    """
    def hold(reason: str) -> SyntheticLedgerVerdict:
        return SyntheticLedgerVerdict(reason)

    if (type(predecision) not in (list, tuple) or not 0 < len(predecision) <= MAX_RACES
            or any(type(x) is not PredeadlineMockRace for x in predecision)):
        return hold('PREDECISION_COHORT_INVALID')
    rid_seen: set[str] = set()
    for race in predecision:
        m = RACE_ID.fullmatch(race.race_id) if type(race.race_id) is str else None
        if m is None:
            return hold('RACE_ID_INVALID')
        try:
            day = datetime.strptime(m[1], '%Y%m%d').date()
        except ValueError:
            return hold('RACE_ID_INVALID')
        if day < date(2025, 7, 1):
            return hold('RACE_ID_INVALID')
        if race.race_id in rid_seen:
            return hold('DUPLICATE_PREDECISION_RACE')
        rid_seen.add(race.race_id)
        if (not all(_aware(t) for t in (race.first_observed_at, race.frozen_at, race.cutoff_at))
                or not race.first_observed_at <= race.frozen_at < race.cutoff_at
                or race.cutoff_at.astimezone(JST).date() != day):
            return hold('PREDECISION_CLOCK_INVALID')
        if (type(race.original_source_ref) is not str or not race.original_source_ref.strip()
                or not _digest(race.original_source_bytes, race.original_sha256)):
            return hold('PREDECISION_RAW_SOURCE_UNBOUND')
        if (type(race.orders) is not tuple or not 1 <= len(race.orders) <= 120):
            return hold('MISSING_PURCHASE_RECEIPTS_OR_ORDERS')
        seen_tickets: set[str] = set()
        for order in race.orders:
            if type(order) is not MockOrder or not _ticket(order.ticket):
                return hold('INVALID_TICKET')
            if order.ticket in seen_tickets:
                return hold('DUPLICATE_TICKET')
            seen_tickets.add(order.ticket)
            if (type(order.stake_yen) is not int or order.stake_yen < 100
                    or order.stake_yen % 100 != 0):
                return hold('INVALID_STAKE')
            if (type(order.odds_decimal) not in (float, int)
                    or not math.isfinite(order.odds_decimal) or order.odds_decimal <= 0
                    or not _aware(order.odds_observed_at)):
                return hold('MISSING_OR_INVALID_PREDEADLINE_ODDS')
            if (not _aware(order.purchase_executed_at)
                    or not race.first_observed_at <= order.odds_observed_at
                        <= order.purchase_executed_at <= race.frozen_at
                    or type(order.purchase_receipt_ref) is not str
                    or not order.purchase_receipt_ref.strip()):
                return hold('MISSING_OR_LATE_PURCHASE_EVIDENCE')

    if (type(postrace) not in (list, tuple) or len(postrace) != len(predecision)
            or any(type(x) is not PostraceMockResult for x in postrace)):
        return hold('MISSING_SETTLEMENT_OR_REFUND_EVIDENCE')
    by_race = {}
    for result in postrace:
        if type(result.race_id) is not str:
            return hold('SETTLEMENT_RACE_SET_MISMATCH')
        if result.race_id in by_race:
            return hold('DUPLICATE_SETTLEMENT_RACE')
        by_race[result.race_id] = result
    if set(by_race) != rid_seen:
        return hold('SETTLEMENT_RACE_SET_MISMATCH')

    paid = returned = hits = bets = voids = officials = 0
    daily = defaultdict(lambda: [0, 0, 0, 0])
    for race in predecision:  # Fixed original cohort; NEVER postrace-filter.
        result = by_race[race.race_id]
        if (not _aware(result.observed_at) or result.observed_at <= race.cutoff_at
                or type(result.source_ref) is not str or not result.source_ref.strip()
                or not _digest(result.raw_result_bytes, result.raw_result_sha256)):
            return hold('POSTRACE_SOURCE_OR_CLOCK_UNVERIFIED')
        if result.status not in ('OFFICIAL', 'VOID'):
            return hold('UNRESOLVED_OR_INVALID_SETTLEMENT')
        if (type(result.returns) is not tuple
                or len(result.returns) != len(race.orders)
                or any(type(x) is not MockTicketReturn or not _ticket(x.ticket)
                       or type(x.payout_yen) is not int or x.payout_yen < 0
                       or type(x.refund_yen) is not int or x.refund_yen < 0
                       for x in result.returns)):
            return hold('MISSING_SETTLEMENT_OR_REFUND_EVIDENCE')
        orders = {x.ticket: x for x in race.orders}
        money = {x.ticket: x for x in result.returns}
        if len(money) != len(result.returns) or set(money) != set(orders):
            return hold('TICKET_SETTLEMENT_MISMATCH')
        if result.status == 'VOID':
            if (result.winning_ticket is not None
                    or any(x.payout_yen != 0 or x.refund_yen != orders[x.ticket].stake_yen
                           for x in result.returns)):
                return hold('VOID_REFUNDS_INCOMPLETE')
            voids += 1
        else:
            if not _ticket(result.winning_ticket):
                return hold('OFFICIAL_WINNING_TICKET_MISSING')
            for x in result.returns:
                if (x.refund_yen not in (0, orders[x.ticket].stake_yen)
                        or (x.payout_yen > 0 and (x.ticket != result.winning_ticket
                                                or x.refund_yen != 0))
                        or (x.ticket == result.winning_ticket and x.refund_yen == 0
                            and x.payout_yen == 0)):
                    return hold('OFFICIAL_PAYOUT_OR_REFUND_INCONSISTENT')
            officials += 1
        race_paid = sum(x.stake_yen for x in race.orders)
        race_returned = sum(x.payout_yen + x.refund_yen for x in result.returns)
        paid += race_paid
        returned += race_returned
        bets += len(race.orders)
        hits += sum(x.payout_yen > 0 for x in result.returns)
        group = daily[race.race_id[:8]]
        group[0] += 1
        group[1] += len(race.orders)
        group[2] += race_paid
        group[3] += race_returned
    days = tuple(SyntheticDayCash(day, *values[:2], values[2], values[3], values[3] - values[2])
                 for day, values in sorted(daily.items()))
    return SyntheticLedgerVerdict(
        'SYNTHETIC_CASH_LEDGER_SHAPE_HOLD_UNAUTHENTICATED', True,
        len(predecision), bets, officials, voids, hits, paid, returned,
        returned - paid, 100.0 * returned / paid, 100.0 * hits / bets, days,
    )
