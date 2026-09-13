# -*- coding: utf-8 -*-
"""Pure contract for prospective V4 late-market corroboration annotation.

This module has no DB/network/result/payout access. It consumes an already-frozen
Candidate Discovery feed plus prevalidated timing-safe market snapshots and only
adds descriptive market TOP2 support tags.

Frozen prospective study: MKT_LATE07_TOP2_SUPPORT_V1
- hypothesis start: 2026-09-14 JST
- exact prospective evidence requires source contract candidate_discovery_v4_main_feed_v1
- late window: 0.0..7.0 minutes before deadline
- coherent market spread: <= 60 seconds
- complete trifecta market: exactly 120 positive tickets
- market may annotate, never create/delete/replace a Stage-1 candidate
- no EV/odds/tier/venue/race-number carveout
"""
from __future__ import annotations

import math
from typing import Any

PROSPECTIVE_START = "2026-09-14"
V4_FEED_CONTRACT = "candidate_discovery_v4_main_feed_v1"
LATE_MIN_LO = 0.0
LATE_MIN_HI = 7.0
MAX_SPREAD_SECONDS = 60.0
EXPECTED_TRIFECTA_TICKETS = 120


def _norm_ticket(value: Any) -> str:
    s = str(value or "").replace("=", "-").replace(" ", "")
    parts = [x for x in s.split("-") if x]
    if len(parts) == 3 and all(x in {"1", "2", "3", "4", "5", "6"} for x in parts):
        return "-".join(parts)
    return s


def extract_core_top1(feed_doc: dict[str, Any], *, expected_core_races: int = 6) -> list[dict[str, Any]]:
    """Extract exactly one immutable core_order=1 DISCOVERY_CORE ticket per core race."""
    if feed_doc.get("purchase_action") is not False:
        raise ValueError("feed must preserve purchase_action=false")
    if feed_doc.get("production_behavior_changed") is not False:
        raise ValueError("feed must preserve production_behavior_changed=false")

    feed = feed_doc.get("feed")
    if not isinstance(feed, list):
        raise ValueError("feed list required")

    rows: list[dict[str, Any]] = []
    for race in feed:
        if not isinstance(race, dict) or bool(race.get("legacy_carryover")):
            continue
        tickets = race.get("tickets")
        if not isinstance(tickets, list):
            raise ValueError("tickets list required for core race")
        core_top1 = []
        for ticket in tickets:
            if not isinstance(ticket, dict):
                continue
            source = ticket.get("source") or []
            if ticket.get("core_order") == 1 and "DISCOVERY_CORE" in source:
                core_top1.append(ticket)
        if len(core_top1) != 1:
            raise ValueError(f"expected one core_order=1 ticket for {race.get('race_id')}: {len(core_top1)}")
        t = core_top1[0]
        rows.append({
            "race_id": str(race.get("race_id") or ""),
            "race_date": str(race.get("race_date") or "")[:10],
            "venue_id": str(race.get("venue_id") or "").zfill(2),
            "race_no": int(race.get("race_no") or 0),
            "daily_rank": int(race.get("daily_rank") or 0),
            "tier": str(race.get("tier") or ""),
            "ticket": _norm_ticket(t.get("ticket")),
        })

    if len(rows) != expected_core_races:
        raise ValueError(f"expected {expected_core_races} core races, got {len(rows)}")
    if len({x["race_id"] for x in rows}) != len(rows):
        raise ValueError("duplicate core race_id")
    if any(not x["race_id"] or not x["ticket"] for x in rows):
        raise ValueError("missing core race_id/ticket")
    return sorted(rows, key=lambda x: (x["daily_rank"], x["race_id"]))


def market_top2(snapshot: dict[str, Any]) -> tuple[str, str] | None:
    """Return TOP2 only for the frozen timing-safe late-market contract."""
    try:
        lead = float(snapshot.get("lead_minutes"))
        spread = float(snapshot.get("spread_seconds"))
    except Exception:
        return None
    if not (LATE_MIN_LO <= lead <= LATE_MIN_HI):
        return None
    if not (0.0 <= spread <= MAX_SPREAD_SECONDS):
        return None

    odds = snapshot.get("odds")
    if not isinstance(odds, dict) or len(odds) != EXPECTED_TRIFECTA_TICKETS:
        return None

    scored: list[tuple[float, str]] = []
    for raw_ticket, raw_odd in odds.items():
        ticket = _norm_ticket(raw_ticket)
        try:
            odd = float(raw_odd)
        except Exception:
            return None
        if not ticket or not math.isfinite(odd) or odd <= 1.0:
            return None
        scored.append((1.0 / odd, ticket))
    if len({ticket for _, ticket in scored}) != EXPECTED_TRIFECTA_TICKETS:
        return None
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][1], scored[1][1]


def annotate_feed(
    feed_doc: dict[str, Any],
    market_by_race: dict[str, dict[str, Any]],
    *,
    expected_core_races: int = 6,
) -> dict[str, Any]:
    """Annotate frozen core TOP1 tickets; never mutate the input feed or candidate set."""
    core = extract_core_top1(feed_doc, expected_core_races=expected_core_races)
    source_contract = str(feed_doc.get("contract") or "")
    exact_v4_source = source_contract == V4_FEED_CONTRACT
    rows: list[dict[str, Any]] = []
    for frozen in core:
        snap = market_by_race.get(frozen["race_id"])
        top2 = market_top2(snap) if isinstance(snap, dict) else None
        counts_as_prospective = exact_v4_source and frozen["race_date"] >= PROSPECTIVE_START
        rows.append({
            **frozen,
            "late_snapshot_available": bool(top2),
            "market_top2": list(top2) if top2 else [],
            "market_top2_support": bool(top2 and frozen["ticket"] in set(top2)),
            "counts_as_prospective": counts_as_prospective,
        })

    return {
        "contract": "MKT_LATE07_TOP2_SUPPORT_V1",
        "source_feed_contract": source_contract,
        "exact_v4_source": exact_v4_source,
        "prospective_start": PROSPECTIVE_START,
        "late_window_minutes": [LATE_MIN_LO, LATE_MIN_HI],
        "max_spread_seconds": MAX_SPREAD_SECONDS,
        "core_top1": len(rows),
        "late_available": sum(1 for x in rows if x["late_snapshot_available"]),
        "top2_supported": sum(1 for x in rows if x["market_top2_support"]),
        "prospective_supported": sum(1 for x in rows if x["market_top2_support"] and x["counts_as_prospective"]),
        "rows": rows,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
