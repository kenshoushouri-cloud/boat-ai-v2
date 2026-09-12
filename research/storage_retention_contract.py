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

    @property
    def logical_key(self) -> tuple[str, str, str, str]:
        return (self.race_id, self.ticket, self.run_class, self.window_name)


def retention_plan(rows: Iterable[ShadowRow]) -> tuple[tuple[ShadowRow, ...], tuple[ShadowRow, ...]]:
    """Return (keep, removable_candidate) without mutating or deleting anything.

    Safety contract:
    - any logical key containing an unevaluated row is fully retained;
    - evaluated-only logical keys keep exactly the latest snapshot;
    - equal latest timestamps with different snapshot keys fail closed;
    - output is deterministic and intended only for offline impact analysis.
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
        keep.append(survivor)
        removable.extend(row for row in group if row is not survivor)

    order = lambda row: (row.logical_key, row.snapshot_at, row.snapshot_key)
    return tuple(sorted(keep, key=order)), tuple(sorted(removable, key=order))


def retained_latest_map(rows: Iterable[ShadowRow]) -> dict[tuple[str, str, str, str], ShadowRow]:
    keep, _ = retention_plan(rows)
    out: dict[tuple[str, str, str, str], ShadowRow] = {}
    for row in keep:
        if row.logical_key not in out or row.snapshot_at > out[row.logical_key].snapshot_at:
            out[row.logical_key] = row
    return out
