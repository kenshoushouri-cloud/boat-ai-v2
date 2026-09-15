# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta, timezone

from research.candidate_discovery_v4_capture_arbiter import Capture, arbitrate_captures

JST = timezone(timedelta(hours=9))
TARGET = date(2026, 9, 16)


def cap(
    *,
    channel="github-primary",
    run_id="100",
    hh=8,
    mm=16,
    ss=0,
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
        provider_run_id=run_id,
        target_date=TARGET,
        generated_at_jst=datetime(2026, 9, 16, hh, mm, ss, tzinfo=JST),
        canonical_payload_sha256=sha,
        prospective_evidence_eligible=eligible,
        purchase_action=purchase,
        promotion_allowed=promotion,
        core_races=races,
        core_tickets=tickets,
        all_frozen_rows_pre_deadline=predeadline,
    )


def test_unique_earliest_valid_capture_is_formal_and_later_is_diagnostic():
    primary = cap(run_id="999", hh=8, mm=17, sha="1" * 64)
    fallback = cap(channel="railway-fallback", run_id="1", hh=8, mm=25, sha="2" * 64)
    result = arbitrate_captures([fallback, primary], target_date=TARGET)
    assert result.classification == "FORMAL_AVAILABLE"
    assert result.formal_capture == primary
    assert result.later_diagnostics == (fallback,)


def test_same_earliest_timestamp_same_payload_collapses_duplicate_copy():
    github = cap(channel="github-primary", run_id="9000", sha="3" * 64)
    railway = cap(channel="railway-fallback", run_id="2", sha="3" * 64)
    result = arbitrate_captures([railway, github], target_date=TARGET)
    assert result.classification == "FORMAL_AVAILABLE"
    assert result.formal_capture is not None
    assert result.formal_capture.canonical_payload_sha256 == "3" * 64
    assert len(result.duplicate_copies) == 1


def test_same_earliest_timestamp_different_payload_fails_closed():
    github = cap(channel="github-primary", run_id="1", sha="4" * 64)
    railway = cap(channel="railway-fallback", run_id="999999", sha="5" * 64)
    result = arbitrate_captures([github, railway], target_date=TARGET)
    assert result.classification == "UNAVAILABLE_AMBIGUOUS_DUPLICATE_CAPTURE"
    assert result.formal_capture is None
    assert len(result.duplicate_copies) == 2


def test_provider_run_id_never_overrides_earlier_generated_timestamp():
    earlier = cap(channel="railway-fallback", run_id="999999999", hh=8, mm=20, sha="6" * 64)
    later = cap(channel="github-primary", run_id="1", hh=8, mm=21, sha="7" * 64)
    result = arbitrate_captures([later, earlier], target_date=TARGET)
    assert result.formal_capture == earlier


def test_invalid_capture_is_rejected_not_rescued_by_later_metadata():
    invalid = cap(hh=8, mm=16, eligible=False, sha="8" * 64)
    valid = cap(channel="railway-fallback", run_id="2", hh=8, mm=25, sha="9" * 64)
    result = arbitrate_captures([invalid, valid], target_date=TARGET)
    assert result.classification == "FORMAL_AVAILABLE"
    assert result.formal_capture == valid
    assert result.rejected_captures == (invalid,)


def test_before_cutoff_or_incomplete_core_is_rejected():
    before_cutoff = cap(hh=8, mm=14, sha="a" * 64)
    incomplete = cap(hh=8, mm=16, races=5, tickets=10, sha="b" * 64)
    result = arbitrate_captures([before_cutoff, incomplete], target_date=TARGET)
    assert result.classification == "UNAVAILABLE_NO_VALID_CAPTURE"
    assert result.formal_capture is None
    assert len(result.rejected_captures) == 2


def test_purchase_promotion_or_postdeadline_flags_fail_closed():
    purchase = cap(purchase=True, sha="c" * 64)
    promotion = cap(promotion=True, sha="d" * 64)
    late = cap(predeadline=False, sha="e" * 64)
    result = arbitrate_captures([purchase, promotion, late], target_date=TARGET)
    assert result.classification == "UNAVAILABLE_NO_VALID_CAPTURE"
    assert len(result.rejected_captures) == 3
