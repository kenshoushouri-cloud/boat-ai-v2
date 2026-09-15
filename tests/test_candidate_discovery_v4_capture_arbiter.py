# -*- coding: utf-8 -*-
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

from research.candidate_discovery_v4_capture_arbiter import (
    Capture,
    arbitrate_captures,
    canonical_core_payload_sha256,
    capture_from_mapping,
)

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


def artifact():
    feed = []
    for rank in range(1, 7):
        feed.append(
            {
                "race_id": f"20260916_05_{rank:02d}",
                "race_date": "2026-09-16",
                "venue_id": "05",
                "race_no": rank,
                "deadline_at": f"2026-09-16T{9 + rank:02d}:00:00+09:00",
                "course_usable_lanes": 6,
                "opponent_pressure_available": True,
                "motor2_complete": True,
                "tier": "A" if rank <= 2 else ("B" if rank <= 4 else "C"),
                "daily_rank": rank,
                "race_score": round(1.0 - rank * 0.01, 8),
                "head_lane": 1,
                "head_p1": round(0.40 - rank * 0.01, 8),
                "tickets": [
                    {
                        "ticket": "1-2-3",
                        "core_order": 1,
                        "source": ["DISCOVERY_CORE"],
                        "legacy_rules": [],
                    },
                    {
                        "ticket": "1-3-2",
                        "core_order": 2,
                        "source": ["DISCOVERY_CORE"],
                        "legacy_rules": [],
                    },
                ],
                "legacy_carryover": False,
            }
        )
    return {
        "contract": "candidate_discovery_v4_main_feed_v1",
        "summary": {
            "date": "2026-09-16",
            "scheduled_races": 156,
            "evaluable_races": 156,
            "skipped_incomplete_entries_or_deadline": 0,
            "core_races": 6,
            "core_tickets": 12,
            "course_supported_races": 156,
            "course_usable_lanes": 936,
            "opponent_pressure_supported_races": 156,
            "motor2_complete_races": 156,
            "legacy_shadow_rows": 0,
            "legacy_added_races": 0,
            "legacy_added_tickets": 0,
            "legacy_exact_overlap_events": 0,
            "feed_races": 6,
            "feed_tickets": 12,
        },
        "policy": {
            "course_coefficient": 0.5,
            "course_missing_lane": "neutral",
            "course_source_cutoff_jst": "08:15",
            "opponent_pressure_coefficient": 1.0,
            "opponent_pressure_role": "first_place_only",
            "motor2_beta": 0.06,
            "motor2_position_weights": [1.0, 0.6, 0.3],
            "core_races_per_day": 6,
            "core_tickets_per_race": 2,
            "expected_value_filter": False,
            "odds_filter": False,
            "odds_read": False,
            "legacy_carryover": True,
        },
        "feed": feed,
        "generated_at_jst": "2026-09-16T08:16:30+09:00",
        "freeze_provenance": {
            "started_at_jst": "2026-09-16T08:16:00+09:00",
            "completed_at_jst": "2026-09-16T08:16:30+09:00",
        },
        "prospective_evidence_eligible": True,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }


def capture_mapping(**overrides):
    row = {
        "channel": "github-primary",
        "provider_run_id": "100",
        "target_date": "2026-09-16",
        "generated_at_jst": "2026-09-16T08:16:30+09:00",
        "canonical_payload_sha256": "a" * 64,
        "prospective_evidence_eligible": True,
        "purchase_action": False,
        "promotion_allowed": False,
        "core_races": 6,
        "core_tickets": 12,
        "all_frozen_rows_pre_deadline": True,
    }
    row.update(overrides)
    return row


def assert_value_error(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


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


def test_capture_mapping_requires_exact_boolean_and_integer_types():
    assert_value_error(
        lambda: capture_from_mapping(capture_mapping(prospective_evidence_eligible="false"))
    )
    assert_value_error(
        lambda: capture_from_mapping(capture_mapping(all_frozen_rows_pre_deadline="true"))
    )
    assert_value_error(lambda: capture_from_mapping(capture_mapping(core_races=6.0)))


def test_canonical_hash_ignores_capture_timestamps_and_legacy_auxiliary_changes():
    first = artifact()
    second = deepcopy(first)
    second["generated_at_jst"] = "2026-09-16T08:25:30+09:00"
    second["freeze_provenance"]["started_at_jst"] = "2026-09-16T08:25:00+09:00"
    second["freeze_provenance"]["completed_at_jst"] = "2026-09-16T08:25:30+09:00"
    second["summary"]["legacy_shadow_rows"] = 12
    second["summary"]["legacy_added_races"] = 1
    second["summary"]["legacy_added_tickets"] = 1
    second["summary"]["legacy_exact_overlap_events"] = 1
    second["summary"]["feed_races"] = 7
    second["summary"]["feed_tickets"] = 13
    second["feed"][0]["tickets"][0]["source"].append("LEGACY")
    second["feed"][0]["tickets"][0]["legacy_rules"].append("S01")
    second["feed"].append(
        {
            "race_id": "20260916_23_01",
            "race_date": "2026-09-16",
            "venue_id": "23",
            "race_no": 1,
            "deadline_at": "2026-09-16T08:44:00+09:00",
            "course_usable_lanes": None,
            "opponent_pressure_available": None,
            "motor2_complete": None,
            "tier": "L",
            "daily_rank": None,
            "race_score": None,
            "head_lane": None,
            "head_p1": None,
            "tickets": [
                {
                    "ticket": "2-1-3",
                    "core_order": None,
                    "source": ["LEGACY"],
                    "legacy_rules": ["S02"],
                }
            ],
            "legacy_carryover": True,
        }
    )
    assert canonical_core_payload_sha256(first) == canonical_core_payload_sha256(second)


def test_canonical_hash_changes_when_formal_core_ticket_changes():
    first = artifact()
    second = deepcopy(first)
    second["feed"][0]["tickets"][0]["ticket"] = "1-2-4"
    assert canonical_core_payload_sha256(first) != canonical_core_payload_sha256(second)


def test_canonical_hash_rejects_frozen_policy_drift_but_tracks_score_change():
    base = artifact()
    policy_changed = deepcopy(base)
    policy_changed["policy"]["motor2_beta"] = 0.07
    assert_value_error(lambda: canonical_core_payload_sha256(policy_changed))

    score_changed = deepcopy(base)
    score_changed["feed"][0]["race_score"] = 0.12345678
    assert canonical_core_payload_sha256(base) != canonical_core_payload_sha256(score_changed)


def test_canonical_hash_rejects_missing_required_formal_fields():
    missing_policy = artifact()
    del missing_policy["policy"]["motor2_beta"]
    assert_value_error(lambda: canonical_core_payload_sha256(missing_policy))

    missing_core = artifact()
    del missing_core["feed"][0]["deadline_at"]
    assert_value_error(lambda: canonical_core_payload_sha256(missing_core))

    null_core = artifact()
    null_core["feed"][0]["race_score"] = None
    assert_value_error(lambda: canonical_core_payload_sha256(null_core))


def test_canonical_hash_rejects_malformed_formal_core_types():
    bad_legacy_flag = artifact()
    bad_legacy_flag["feed"][0]["legacy_carryover"] = "false"
    assert_value_error(lambda: canonical_core_payload_sha256(bad_legacy_flag))

    bad_opponent_flag = artifact()
    bad_opponent_flag["feed"][0]["opponent_pressure_available"] = "false"
    assert_value_error(lambda: canonical_core_payload_sha256(bad_opponent_flag))

    bad_ticket = artifact()
    bad_ticket["feed"][0]["tickets"][0]["ticket"] = "1-1-2"
    assert_value_error(lambda: canonical_core_payload_sha256(bad_ticket))


def test_canonical_hash_rejects_incomplete_or_duplicate_core_orders():
    incomplete = artifact()
    incomplete["feed"].pop()
    incomplete["summary"]["core_races"] = 5
    incomplete["summary"]["core_tickets"] = 10
    assert_value_error(lambda: canonical_core_payload_sha256(incomplete))

    duplicate_order = artifact()
    duplicate_order["feed"][0]["tickets"][1]["core_order"] = 1
    assert_value_error(lambda: canonical_core_payload_sha256(duplicate_order))
