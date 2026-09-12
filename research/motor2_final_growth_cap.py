"""Pure research contract for reducing Motor2 FINAL shadow row growth.

This module is intentionally not imported by Production code.  It models an
opt-in future keying strategy only; the current Production behavior remains
unchanged until a separate runtime approval is granted.
"""
from __future__ import annotations

from datetime import datetime

VALID_MODES = {"timestamped", "latest_per_race"}
DEFAULT_MODE = "timestamped"


def build_snapshot_key(target_date: str, observed_at: datetime, mode: str = DEFAULT_MODE) -> str:
    """Return the proposed Motor2 FINAL snapshot key for a research mode.

    `timestamped` exactly models the current concept: every FINAL invocation
    receives a fresh time-qualified key.

    `latest_per_race` deliberately returns one stable FINAL key per date.  The
    table's existing unique key also contains race_id and ticket, so repeated
    writes for the same race/ticket would update the existing row while
    different races and tickets remain independent.
    """
    normalized = (mode or "").strip().lower()
    if normalized not in VALID_MODES:
        raise ValueError(f"unsupported Motor2 FINAL snapshot mode: {mode!r}")
    date_key = target_date.replace("-", "")
    if normalized == "latest_per_race":
        return f"{date_key}_final_latest"
    return f"{date_key}_final_{observed_at.strftime('%H%M%S')}"


def logical_unique_key(
    race_id: str,
    ticket: str,
    target_date: str,
    observed_at: datetime,
    mode: str = DEFAULT_MODE,
) -> tuple[str, str, str, str, str]:
    """Model the table's existing unique-key identity for FINAL rows."""
    return (
        race_id,
        ticket,
        "final",
        "final",
        build_snapshot_key(target_date, observed_at, mode),
    )


def projected_distinct_rows(
    race_ids: list[str],
    tickets: list[str],
    observed_times: list[datetime],
    target_date: str,
    mode: str = DEFAULT_MODE,
) -> int:
    """Count logical rows under repeated FINAL invocations without DB access."""
    keys = {
        logical_unique_key(race_id, ticket, target_date, observed_at, mode)
        for race_id in race_ids
        for ticket in tickets
        for observed_at in observed_times
    }
    return len(keys)
