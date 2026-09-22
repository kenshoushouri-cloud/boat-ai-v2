# -*- coding: utf-8 -*-
"""Pure notification layout helpers for final BUY LINE messages.

This module never creates a BUY candidate. It only limits/labels already-existing
BUY decisions for notification display. Prediction thresholds, candidate
generation, stake, and purchase behavior are outside this module.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Set, Tuple

MAX_POINTS_PER_RACE = 2


def select_notification_decisions(
    rows: Sequence[Mapping[str, Any]],
    *,
    sent_keys: Set[str],
    notified_tickets_by_race: Mapping[str, Set[str]],
    max_send: int,
    max_points_per_race: int = MAX_POINTS_PER_RACE,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Select at most two distinct existing BUY tickets per race.

    Input order is authoritative. The production query orders by final_score
    descending, so the first distinct eligible ticket is the main point and the
    second is the cover point.

    Already-notified tickets count toward the two-point lifetime cap for the
    target date. A later newly-eligible second ticket is labeled as cover
    (point_order=2); third and later BUY decisions are not notified.
    """

    if max_send < 1:
        raise ValueError("max_send must be >= 1")
    if max_points_per_race < 1:
        raise ValueError("max_points_per_race must be >= 1")

    selected: list[dict[str, Any]] = []
    seen_pending: dict[str, set[str]] = {}
    counts: dict[str, int] = {
        str(race_id): len(set(tickets))
        for race_id, tickets in notified_tickets_by_race.items()
    }
    metrics = {
        "sent_key_skipped": 0,
        "already_notified_skipped": 0,
        "duplicate_pending_skipped": 0,
        "extra_point_skipped": 0,
        "invalid_row_skipped": 0,
    }

    for raw in rows:
        race_id = str(raw.get("race_id") or "")
        ticket = str(raw.get("ticket") or "")
        if not race_id or not ticket:
            metrics["invalid_row_skipped"] += 1
            continue

        key = f"{race_id}|{ticket}"
        if key in sent_keys:
            metrics["sent_key_skipped"] += 1
            continue

        already = notified_tickets_by_race.get(race_id, set())
        if ticket in already:
            metrics["already_notified_skipped"] += 1
            continue

        race_seen = seen_pending.setdefault(race_id, set())
        if ticket in race_seen:
            metrics["duplicate_pending_skipped"] += 1
            continue
        race_seen.add(ticket)

        used = counts.get(race_id, 0)
        if used >= max_points_per_race:
            metrics["extra_point_skipped"] += 1
            continue

        row = dict(raw)
        row["_line_point_order"] = used + 1
        selected.append(row)
        counts[race_id] = used + 1

        if len(selected) >= max_send:
            break

    return selected, metrics


def group_notification_decisions(
    decisions: Sequence[Mapping[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Group selected notification rows by race while preserving race order."""

    groups: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for raw in decisions:
        race_id = str(raw.get("race_id") or "")
        if not race_id:
            continue
        groups.setdefault(race_id, []).append(dict(raw))

    for group in groups.values():
        group.sort(
            key=lambda row: (
                int(row.get("_line_point_order") or 999),
                -float(row.get("final_score") or 0.0),
                str(row.get("ticket") or ""),
            )
        )
    return list(groups.values())


def point_label(order: Any) -> str:
    try:
        value = int(order)
    except Exception:
        value = 1
    return "本線" if value <= 1 else "押さえ"
