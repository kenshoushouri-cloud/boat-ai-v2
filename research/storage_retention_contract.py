from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class ShadowRow:
    race_id: str
    ticket: str
    run_class: str
    window_name: str
    snapshot_key: str
    snapshot_at: datetime
    evaluated: bool
    protected: bool = False

    @property
    def logical_key(self) -> tuple[str, str, str, str]:
        return (self.race_id, self.ticket, self.run_class, self.window_name)


def retention_plan(rows: Iterable[ShadowRow]) -> tuple[tuple[ShadowRow, ...], tuple[ShadowRow, ...]]:
    """Return (keep, removable_candidate) without mutating or deleting anything.

    Safety contract:
    - any logical key containing an unevaluated row is fully retained;
    - evaluated-only logical keys always keep the latest snapshot;
    - any externally protected row is retained even when it is older than latest;
    - equal latest timestamps with different snapshot keys fail closed;
    - output is deterministic and intended only for offline impact analysis.

    `protected` exists for report-semantic preservation. The Production read-only
    audit marks every row belonging to the latest valid PRE snapshot selected by
    the existing Motor2 probability-health report as protected. This prevents a
    newer but health-invalid/post-deadline snapshot from erasing the older valid
    PRE evidence that the current report actually consumes.
    """
    groups: dict[tuple[str, str, str, str], list[ShadowRow]] = {}
    for row in rows:
        if not all(row.logical_key) or not row.snapshot_key:
            raise ValueError("malformed shadow identity")
        groups.setdefault(row.logical_key, []).append(row)

    keep: list[ShadowRow] = []
    removable: list[ShadowRow] = []

    for key in sorted(groups):
        group = groups[key]
        if any(not row.evaluated for row in group):
            keep.extend(group)
            continue

        latest_at = max(row.snapshot_at for row in group)
        latest = [row for row in group if row.snapshot_at == latest_at]
        if len({row.snapshot_key for row in latest}) != 1:
            raise ValueError("ambiguous latest snapshot")

        survivor = sorted(latest, key=lambda row: row.snapshot_key)[-1]
        survivors = {survivor}
        survivors.update(row for row in group if row.protected)
        keep.extend(survivors)
        removable.extend(row for row in group if row not in survivors)

    order = lambda row: (row.logical_key, row.snapshot_at, row.snapshot_key, row.protected)
    return tuple(sorted(keep, key=order)), tuple(sorted(removable, key=order))


def retained_latest_map(rows: Iterable[ShadowRow]) -> dict[tuple[str, str, str, str], ShadowRow]:
    keep, _ = retention_plan(rows)
    out: dict[tuple[str, str, str, str], ShadowRow] = {}
    for row in keep:
        if row.logical_key not in out or row.snapshot_at > out[row.logical_key].snapshot_at:
            out[row.logical_key] = row
    return out


def retention_impact(rows: Iterable[ShadowRow]) -> dict[str, int | float]:
    """Summarize a hypothetical compaction plan without changing any state."""
    materialized = tuple(rows)
    keep, removable = retention_plan(materialized)

    groups: dict[tuple[str, str, str, str], list[ShadowRow]] = {}
    for row in materialized:
        groups.setdefault(row.logical_key, []).append(row)

    blocked_keys = sum(
        1
        for group in groups.values()
        if any(not row.evaluated for row in group)
    )
    protected_rows = sum(1 for row in materialized if row.protected)
    protected_keys = sum(
        1
        for group in groups.values()
        if any(row.protected for row in group)
    )
    removable_pct = (
        len(removable) / len(materialized) * 100.0
        if materialized
        else 0.0
    )

    return {
        "input_rows": len(materialized),
        "logical_keys": len(groups),
        "keep_rows": len(keep),
        "removable_candidate_rows": len(removable),
        "unevaluated_blocked_keys": blocked_keys,
        "protected_rows": protected_rows,
        "protected_keys": protected_keys,
        "removable_candidate_pct": removable_pct,
    }
