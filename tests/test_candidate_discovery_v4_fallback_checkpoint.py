# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta, timezone

from research.candidate_discovery_v4_capture_arbiter import Capture
from research.candidate_discovery_v4_fallback_checkpoint import decide_fallback_checkpoint

JST = timezone(timedelta(hours=9))
TARGET = date(2026, 9, 18)


def primary(
    *,
    channel="github-primary",
    hh=8,
    mm=16,
    ss=30,
    sha="a" * 64,
    eligible=True,
    purchase=False,
    promotion=False,
    races=6,
    tickets=12,
    predeadline=True,
):
    return Capture(
        channel=channel,
        provider_run_id="run-1",
        target_date=TARGET,
        generated_at_jst=datetime(2026, 9, 18, hh, mm, ss, tzinfo=JST),
        canonical_payload_sha256=sha,
        prospective_evidence_eligible=eligible,
        purchase_action=purchase,
        promotion_allowed=promotion,
        core_races=races,
        core_tickets=tickets,
        all_frozen_rows_pre_deadline=predeadline,
    )


def observed(hh=8, mm=25, ss=0):
    return datetime(2026, 9, 18, hh, mm, ss, tzinfo=JST)


def test_before_checkpoint_is_not_due():
    result = decide_fallback_checkpoint([], target_date=TARGET, observed_at_jst=observed(8, 24, 59))
    assert result.action == "NOT_DUE"
    assert result.should_attempt is False


def test_missing_primary_at_checkpoint_allows_attempt_only():
    result = decide_fallback_checkpoint([], target_date=TARGET, observed_at_jst=observed())
    assert result.action == "ATTEMPT_FALLBACK"
    assert result.should_attempt is True
    assert result.valid_primary is None


def test_valid_primary_observable_at_checkpoint_forces_noop():
    cap = primary()
    result = decide_fallback_checkpoint([cap], target_date=TARGET, observed_at_jst=observed())
    assert result.action == "NOOP_VALID_PRIMARY"
    assert result.should_attempt is False
    assert result.valid_primary == cap


def test_invalid_primary_does_not_suppress_attempt():
    invalid = primary(eligible=False)
    result = decide_fallback_checkpoint([invalid], target_date=TARGET, observed_at_jst=observed())
    assert result.action == "ATTEMPT_FALLBACK"
    assert result.rejected_primary_count == 1


def test_future_primary_metadata_is_not_observable_at_checkpoint():
    future = primary(hh=8, mm=26)
    result = decide_fallback_checkpoint([future], target_date=TARGET, observed_at_jst=observed())
    assert result.action == "ATTEMPT_FALLBACK"
    assert result.rejected_primary_count == 1


def test_non_primary_channel_never_suppresses_fallback():
    previous_fallback = primary(channel="railway-fallback")
    result = decide_fallback_checkpoint([previous_fallback], target_date=TARGET, observed_at_jst=observed())
    assert result.action == "ATTEMPT_FALLBACK"
    assert result.rejected_primary_count == 0


def test_delayed_checkpoint_delivery_can_still_attempt_but_does_not_assert_eligibility():
    result = decide_fallback_checkpoint([], target_date=TARGET, observed_at_jst=observed(8, 31))
    assert result.action == "ATTEMPT_FALLBACK"
    assert result.should_attempt is True


def test_same_time_same_hash_primary_duplicates_still_noop():
    first = primary(sha="1" * 64)
    second = Capture(
        **{**first.__dict__, "provider_run_id": "run-2"}
    )
    result = decide_fallback_checkpoint([first, second], target_date=TARGET, observed_at_jst=observed())
    assert result.action == "NOOP_VALID_PRIMARY"


def test_same_time_different_hash_primary_duplicates_fail_closed():
    first = primary(sha="2" * 64)
    second = Capture(
        **{**first.__dict__, "provider_run_id": "run-2", "canonical_payload_sha256": "3" * 64}
    )
    result = decide_fallback_checkpoint([first, second], target_date=TARGET, observed_at_jst=observed())
    assert result.action == "FAIL_CLOSED_AMBIGUOUS_PRIMARY"
    assert result.should_attempt is False


def test_wrong_jst_date_fails_closed():
    result = decide_fallback_checkpoint(
        [],
        target_date=TARGET,
        observed_at_jst=datetime(2026, 9, 19, 8, 25, tzinfo=JST),
    )
    assert result.action == "FAIL_CLOSED_WRONG_DATE"
    assert result.should_attempt is False


def test_naive_observation_time_is_rejected():
    try:
        decide_fallback_checkpoint(
            [],
            target_date=TARGET,
            observed_at_jst=datetime(2026, 9, 18, 8, 25),
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError for naive observed_at_jst")
