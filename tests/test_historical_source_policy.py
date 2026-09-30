# -*- coding: utf-8 -*-
from research.historical_source_policy import (
    HistoricalSource,
    HistoricalUse,
    classify_source,
    teikoku_request_policy,
)


def test_official_target_day_program_is_formal_backtest_input():
    assert classify_source(HistoricalSource(
        provider="boatrace_official",
        source_kind="archived_racelist",
        target_day_program_snapshot=True,
    )) == HistoricalUse.FORMAL_BACKTEST


def test_prior_only_official_reconstruction_is_allowed():
    assert classify_source(HistoricalSource(
        provider="boatrace_official",
        source_kind="prior_results_reconstruction",
        reconstructed_prior_only=True,
    )) == HistoricalUse.FORMAL_BACKTEST


def test_target_outcome_read_is_rejected():
    assert classify_source(HistoricalSource(
        provider="boatrace_official",
        source_kind="bad_target_leakage",
        target_day_program_snapshot=True,
        target_outcome_read=True,
    )) == HistoricalUse.REJECT


def test_teikoku_explicit_historical_asof_can_supplement():
    assert classify_source(HistoricalSource(
        provider="teikoku_db",
        source_kind="historical_motor_ledger",
        explicit_asof_before_deadline=True,
    )) == HistoricalUse.SUPPLEMENTAL_BACKTEST


def test_teikoku_current_aggregate_is_crosscheck_only():
    assert classify_source(HistoricalSource(
        provider="teikoku_db",
        source_kind="current_motor_aggregate",
        current_aggregate_only=True,
    )) == HistoricalUse.CROSSCHECK_ONLY


def test_teikoku_policy_respects_site_rules():
    p = teikoku_request_policy()
    assert p["minimum_interval_seconds"] >= 3.0
    assert p["known_existing_urls_only"] is True
    assert p["single_ip_only"] is True
    assert p["program_download_from_teikoku"] is False
    assert p["result_download_from_teikoku"] is False
    assert p["racer_term_download_from_teikoku"] is False
    assert p["historical_current_aggregate_backcast_allowed"] is False
