"""Q1 inventory + Q2 six-lane features, separate postrace Q3; OFFLINE ONLY.

No database calls, learning, bet selection, settlement authority or BUY.
An archived value can never authenticate its original first observation.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from collections.abc import Mapping
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
RID = re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")
CLASSES = frozenset(("A1", "A2", "B1", "B2"))
Q1 = {"race_id", "race_date", "deadline_at"}
Q2 = {"race_id", "race_date", "deadline_at", "lane", "racer_number",
      "racer_class", "recent_form_json_type", "parsed_history",
      "exhibition_source", "exhibition_time_rank", "exhibition_snapshot_at",
      "exhibition_reuse_contract", "exhibition_source_contract",
      "source_snapshot_label", "source_snapshot_at_text",
      "independent_official_six_active_verified",
      "original_first_observation_verified", "forward_eligible", "buy_eligible"}
Q3 = {"race_id", "race_date", "result_status", "race_status", "winning_ticket",
      "payout_per_100_yen", "refund_boats", "refund_section_verified",
      "whole_race_void_verified", "v5_real_roi_verified", "buy_eligible"}
FALSE_PROOFS = ("independent_official_six_active_verified",
                "original_first_observation_verified", "forward_eligible",
                "buy_eligible")


@dataclass(frozen=True)
class LaneValues:
    lane: int
    racer_number: int
    racer_class: str
    prior_form: tuple[tuple[date, int], ...]
    exhibition_rank: int
    exhibition_source: str
    exhibition_snapshot_at: datetime


@dataclass(frozen=True)
class RaceFeatures:
    race_id: str
    day: date
    deadline_at: datetime
    lanes: tuple[LaneValues, ...]
    retrospective_only: bool = field(default=True, init=False)
    buy_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class BatchFeatures:
    inventory_ids: tuple[str, ...]
    candidates: tuple[RaceFeatures, ...]
    pending_ids: tuple[str, ...]
    unrepresented_days: tuple[date, ...]
    issues: tuple[tuple[str, str], ...]
    original_capture_verified: bool = field(default=False, init=False)
    inventory_independently_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class PostraceValues:
    race_id: str
    stored_ticket: str
    stored_payout_yen_per_100: int
    refund_boats: None = field(default=None, init=False)
    refund_section_verified: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class BatchResults:
    stored_only: tuple[PostraceValues, ...]
    pending_ids: tuple[str, ...]
    issues: tuple[tuple[str, str], ...]
    hypothetical_roi_pct: None = field(default=None, init=False)
    v5_real_roi_verified: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _day(value):
    if type(value) is date:
        return value
    if type(value) is str and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return None


def _aware(v):
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def _stream(rows, maximum):
    if (type(rows) not in (list, tuple) or len(rows) > maximum
            or any(not isinstance(row, Mapping) for row in rows)):
        raise ValueError("INVALID_OR_OVERSIZED_STREAM")
    return rows


def audit_feature_streams(start, end_exclusive, inventory_rows, lane_rows):
    """No result/odds accepted or retained in prediction-safe features."""
    if (type(start) is not date or type(end_exclusive) is not date
            or start < date(2025, 7, 1)
            or not 1 <= (end_exclusive - start).days <= 7):
        raise ValueError("WINDOW_OUTSIDE_SEVEN_DAY_CONTRACT")
    inventory = {}
    observed_days = set()
    for row in _stream(inventory_rows, 4000):
        rid, day, deadline = row.get("race_id"), _day(row.get("race_date")), row.get("deadline_at")
        if (set(row) != Q1 or day is None or not start <= day < end_exclusive
                or type(rid) is not str or not RID.fullmatch(rid)
                or rid[:8] != day.strftime("%Y%m%d")
                or not _aware(deadline) or deadline.astimezone(JST).date() != day):
            raise ValueError("INVALID_INVENTORY_RECORD")
        if rid in inventory:
            raise ValueError("DUPLICATE_INVENTORY")
        inventory[rid] = (day, deadline)
        observed_days.add(day)
    if not inventory:
        raise ValueError("EMPTY_INVENTORY_CANNOT_PROVE_NO_RACES")
    groups = defaultdict(list)
    for row in _stream(lane_rows, 40000):
        rid = row.get("race_id")
        if type(rid) is not str or rid not in inventory:
            raise ValueError("LANE_NOT_IN_INVENTORY")
        groups[rid].append(row)
    candidates, pending, issues = [], [], []
    for rid in sorted(inventory):
        day, deadline = inventory[rid]
        group = groups[rid]
        reason = None
        if len(group) != 6:
            reason = "MISSING_OR_DUPLICATE_LANE_ROWS"
        else:
            chosen, lanes, racers, ranks = [], set(), set(), set()
            for row in group:
                lane, racer, cls, rank = (row.get(k) for k in
                                          ("lane", "racer_number", "racer_class",
                                           "exhibition_time_rank"))
                history = row.get("parsed_history")
                snapshot = row.get("exhibition_snapshot_at")
                if (set(row)-Q2 or _day(row.get("race_date")) != day
                        or row.get("deadline_at") != deadline
                        or type(lane) is not int or lane not in range(1, 7)
                        or lane in lanes or type(racer) is not int
                        or not 1 <= racer <= 9999 or racer in racers
                        or type(cls) is not str or cls not in CLASSES
                        or type(rank) is not int or rank not in range(1, 7)
                        or rank in ranks or type(history) is not list
                        or not 1 <= len(history) <= 5
                        or row.get("recent_form_json_type") not in ("array", "object")
                        or type(row.get("exhibition_source")) is not str
                        or not row["exhibition_source"].strip() or not _aware(snapshot)
                        or any(row.get(key) is not False for key in FALSE_PROOFS)):
                    reason = "UNSAFE_LANE_VALUE_OR_LEAK"
                    break
                prior = []
                for item in history:
                    hday = _day(item.get("race_date")) if isinstance(item, Mapping) else None
                    finish = item.get("finish_position") if isinstance(item, Mapping) else None
                    if (hday is None or hday >= day or type(finish) is not int
                            or finish not in range(1, 7)):
                        reason = "UNSAFE_PRIOR_HISTORY"
                        break
                    prior.append((hday, finish))
                if reason:
                    break
                lanes.add(lane)
                racers.add(racer)
                ranks.add(rank)
                chosen.append(LaneValues(lane, racer, cls, tuple(prior), rank,
                                         row["exhibition_source"], snapshot))
            if not reason and (lanes != set(range(1, 7)) or ranks != set(range(1, 7))):
                reason = "SIX_LANE_SET_INCOMPLETE"
        if reason:
            pending.append(rid)
            issues.append((rid, reason))
        else:
            candidates.append(RaceFeatures(rid, day, deadline,
                                           tuple(sorted(chosen, key=lambda x: x.lane))))
    missing_days = tuple(start+timedelta(days=i) for i in
                         range((end_exclusive-start).days)
                         if start+timedelta(days=i) not in observed_days)
    return BatchFeatures(tuple(sorted(inventory)), tuple(candidates),
                         tuple(pending), missing_days, tuple(issues))


def audit_postrace_stream(features, rows):
    """Call only after feature/selection handling; original refund remains UNKNOWN."""
    if type(features) is not BatchFeatures:
        raise ValueError("FEATURE_BATCH_REQUIRED")
    groups = defaultdict(list)
    for row in _stream(rows, 4000):
        rid = row.get("race_id")
        if type(rid) is not str or rid not in features.inventory_ids:
            raise ValueError("RESULT_OUTSIDE_INVENTORY")
        groups[rid].append(row)
    stored, pending, issues = [], [], []
    for rid in features.inventory_ids:
        group = groups[rid]
        if len(group) != 1:
            pending.append(rid)
            issues.append((rid, "MISSING_OR_DUPLICATE_RESULT"))
            continue
        row = group[0]
        day = date.fromisoformat(f"{rid[:4]}-{rid[4:6]}-{rid[6:8]}")
        ticket = row.get("winning_ticket")
        payout = row.get("payout_per_100_yen")
        ticket_valid = (type(ticket) is str
                        and re.fullmatch(r"[1-6]-[1-6]-[1-6]", ticket)
                        and len(set(ticket.split("-"))) == 3)
        if (set(row) != Q3 or _day(row.get("race_date")) != day
                or row.get("refund_boats") is not None
                or any(row.get(k) is not False for k in
                       ("refund_section_verified", "whole_race_void_verified",
                        "v5_real_roi_verified", "buy_eligible"))
                or str(row.get("result_status") or "").lower() != "official"
                or str(row.get("race_status") or "").lower() != "official"
                or not ticket_valid or type(payout) is not int or payout < 100):
            pending.append(rid)
            issues.append((rid, "STORED_RESULT_OR_REFUND_UNVERIFIED"))
            continue
        stored.append(PostraceValues(rid, ticket, payout))
        pending.append(rid)  # Official refund section was never authenticated.
        issues.append((rid, "REFUND_SECTION_ORIGINAL_NOT_VERIFIED"))
    return BatchResults(tuple(stored), tuple(pending), tuple(issues))
