"""Pure contract for resolving the PRE candidate daily LINE limit.

Research only. This module is not imported by Production runtime code and does
not access Railway, PostgreSQL, LINE, or the network.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PRE_DAILY_LINE_LIMIT = 3


class PreLineLimitContractError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedPreLineLimit:
    value: int
    source: str


def _parse_positive_int(raw: str | None, *, name: str) -> int | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise PreLineLimitContractError(f"{name} must be an integer") from exc
    if value <= 0:
        raise PreLineLimitContractError(f"{name} must be positive")
    return value


def resolve_pre_daily_line_limit(
    *,
    pre_daily_line_limit: str | None,
    legacy_daily_line_limit: str | None,
    default: int = DEFAULT_PRE_DAILY_LINE_LIMIT,
) -> ResolvedPreLineLimit:
    """Resolve PRE-only daily limit without affecting FINAL/report limits.

    Precedence is deliberately explicit:
      1. PRE_DAILY_LINE_LIMIT
      2. legacy DAILY_LINE_LIMIT
      3. frozen default 3
    """
    if default <= 0:
        raise PreLineLimitContractError("default must be positive")

    pre = _parse_positive_int(pre_daily_line_limit, name="PRE_DAILY_LINE_LIMIT")
    if pre is not None:
        return ResolvedPreLineLimit(pre, "PRE_DAILY_LINE_LIMIT")

    legacy = _parse_positive_int(legacy_daily_line_limit, name="DAILY_LINE_LIMIT")
    if legacy is not None:
        return ResolvedPreLineLimit(legacy, "DAILY_LINE_LIMIT")

    return ResolvedPreLineLimit(default, "default")
