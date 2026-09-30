# -*- coding: utf-8 -*-
"""Historical source provenance policy.

Pure classification only. No network, DB, LINE, stake, or purchase action.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HistoricalUse(str, Enum):
    FORMAL_BACKTEST = "FORMAL_BACKTEST"
    SUPPLEMENTAL_BACKTEST = "SUPPLEMENTAL_BACKTEST"
    CROSSCHECK_ONLY = "CROSSCHECK_ONLY"
    REJECT = "REJECT"


@dataclass(frozen=True)
class HistoricalSource:
    provider: str
    source_kind: str
    target_day_program_snapshot: bool = False
    explicit_asof_before_deadline: bool = False
    reconstructed_prior_only: bool = False
    target_outcome_read: bool = False
    current_aggregate_only: bool = False


def classify_source(source: HistoricalSource) -> HistoricalUse:
    """Classify whether a historical datum may enter a target-race feature row.

    The project adopts a practical pre-deadline convention:
    - archived target-day official program/racelist data are treated as
      pre-deadline-by-nature historical inputs;
    - prior-race results may be used only to reconstruct features from events
      strictly before the target race;
    - current aggregates retrieved after the fact are never pasted backward
      into historical feature rows.
    """
    if source.target_outcome_read:
        return HistoricalUse.REJECT
    if source.current_aggregate_only:
        return HistoricalUse.CROSSCHECK_ONLY
    if source.provider == "boatrace_official":
        if source.target_day_program_snapshot:
            return HistoricalUse.FORMAL_BACKTEST
        if source.explicit_asof_before_deadline:
            return HistoricalUse.FORMAL_BACKTEST
        if source.reconstructed_prior_only:
            return HistoricalUse.FORMAL_BACKTEST
        return HistoricalUse.CROSSCHECK_ONLY
    if source.provider == "teikoku_db":
        if source.explicit_asof_before_deadline or source.reconstructed_prior_only:
            return HistoricalUse.SUPPLEMENTAL_BACKTEST
        return HistoricalUse.CROSSCHECK_ONLY
    return HistoricalUse.CROSSCHECK_ONLY


def teikoku_request_policy() -> dict:
    return {
        "minimum_interval_seconds": 3.0,
        "known_existing_urls_only": True,
        "single_ip_only": True,
        "repeat_static_asset_fetch": False,
        "program_download_from_teikoku": False,
        "result_download_from_teikoku": False,
        "racer_term_download_from_teikoku": False,
        "preferred_for_program_result_racer_term": "boatrace_official_download",
        "historical_current_aggregate_backcast_allowed": False,
    }
