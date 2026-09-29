from copy import deepcopy

import pytest

from research.candidate_discovery_v4_capture_arbiter import (
    canonical_core_payload_sha256,
)
from research.v4_fcount_companion_contract import (
    build_companion,
    canonical_companion_sha256,
)


def formal():
    feed=[]
    for rank in range(1,7):
        feed.append({
            "race_id":f"2026-10-01-01-{rank:02d}",
            "race_date":"2026-10-01",
            "venue_id":"01",
            "race_no":rank,
            "deadline_at":f"2026-10-01T10:{rank:02d}:00+09:00",
            "tier":"A" if rank<=2 else ("B" if rank<=4 else "C"),
            "daily_rank":rank,
            "race_score":0.9-rank/100,
            "head_lane":1,
            "head_p1":0.40,
            "course_usable_lanes":6,
            "opponent_pressure_available":False,
            "motor2_complete":True,
            "tickets":[
                {"ticket":"1-2-3","core_order":1,"source":["DISCOVERY_CORE"],"legacy_rules":[]},
                {"ticket":"1-3-2","core_order":2,"source":["DISCOVERY_CORE"],"legacy_rules":[]},
            ],
            "legacy_carryover":False,
        })
    return {
        "contract":"candidate_discovery_v4_main_feed_v1",
        "summary":{
            "date":"2026-10-01","scheduled_races":6,"evaluable_races":6,
            "skipped_incomplete_entries_or_deadline":0,"core_races":6,
            "core_tickets":12,"course_supported_races":6,"course_usable_lanes":36,
            "opponent_pressure_supported_races":0,"motor2_complete_races":6,
        },
        "policy":{
            "course_coefficient":0.5,"course_missing_lane":"neutral",
            "course_source_cutoff_jst":"08:15","opponent_pressure_coefficient":1.0,
            "opponent_pressure_role":"first_place_only","motor2_beta":0.06,
            "motor2_position_weights":[1.0,0.6,0.3],"core_races_per_day":6,
            "core_tickets_per_race":2,"expected_value_filter":False,
            "odds_filter":False,"odds_read":False,
        },
        "feed":feed,
        "generated_at_jst":"2026-10-01T08:20:00+09:00",
        "prospective_evidence_eligible":True,
        "freeze_provenance":{
            "target_date":"2026-10-01","mode":"prospective",
            "outcome_read":False,"all_frozen_rows_pre_deadline":True,
            "prospective_evidence_eligible":True,
        },
        "mutation_performed":False,"line_sent":False,"purchase_action":False,
        "production_behavior_changed":False,"promotion_allowed":False,
    }


def counts(x):
    return {
        row["race_id"]:{lane:(1 if lane==1 and x else 0) for lane in range(1,7)}
        for row in formal()["feed"]
    }


def test_companion_binds_exact_formal_core_without_changing_it():
    f=formal()
    before=canonical_core_payload_sha256(f)
    out=build_companion(f,f_counts_by_race=counts(True),captured_at_jst="2026-10-01T08:25:00+09:00")
    after=canonical_core_payload_sha256(f)
    assert before==after==out["formal_v4_canonical_core_sha256"]
    assert len(out["core"])==6
    assert out["core"][0]["predicted_head_f_count"]==1
    assert out["purchase_action"] is False
    assert len(canonical_companion_sha256(out))==64


def test_rejects_extra_or_missing_race():
    f=formal()
    bad=counts(False)
    bad.pop(next(iter(bad)))
    with pytest.raises(ValueError):
        build_companion(f,f_counts_by_race=bad,captured_at_jst="2026-10-01T08:25:00+09:00")


def test_rejects_late_capture():
    f=formal()
    with pytest.raises(ValueError):
        build_companion(f,f_counts_by_race=counts(False),captured_at_jst="2026-10-01T10:01:00+09:00")


def test_rejects_before_formal_freeze():
    f=formal()
    with pytest.raises(ValueError):
        build_companion(f,f_counts_by_race=counts(False),captured_at_jst="2026-10-01T08:19:00+09:00")


def test_extra_research_metadata_does_not_change_formal_core_hash():
    f=formal()
    h=canonical_core_payload_sha256(f)
    f2=deepcopy(f)
    f2["feed"][0]["research_only_f_count"]=99
    assert canonical_core_payload_sha256(f2)==h
