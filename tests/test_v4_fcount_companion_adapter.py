import pytest

from research.candidate_discovery_v4_capture_arbiter import canonical_core_payload_sha256
from research.v4_fcount_companion_adapter import (
    FUTURE_APPROVED_SELECT,
    build_companion_from_entry_rows,
    normalize_f_counts,
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


def rows():
    out=[]
    for rank in range(1,7):
        rid=f"2026-10-01-01-{rank:02d}"
        for lane in range(1,7):
            out.append({"race_id":rid,"lane":lane,"f_count":1 if lane==rank else 0})
    return out


def test_normalizes_exact_formal_six():
    out=normalize_f_counts(formal(),rows())
    assert len(out)==6
    assert out["2026-10-01-01-01"][1]==1
    assert out["2026-10-01-01-02"][2]==1


def test_build_preserves_formal_hash_and_binds_companion():
    f=formal()
    h=canonical_core_payload_sha256(f)
    companion,digest=build_companion_from_entry_rows(
        f,rows(),captured_at_jst="2026-10-01T08:25:00+09:00"
    )
    assert canonical_core_payload_sha256(f)==h
    assert companion["formal_v4_canonical_core_sha256"]==h
    assert companion["purchase_action"] is False
    assert len(digest)==64


def test_rejects_duplicate_lane():
    bad=rows()
    bad[-1]=dict(bad[0])
    with pytest.raises(ValueError):
        normalize_f_counts(formal(),bad)


def test_rejects_outside_race():
    bad=rows()
    bad[0]["race_id"]="2026-10-01-99-01"
    with pytest.raises(ValueError):
        normalize_f_counts(formal(),bad)


def test_rejects_outcome_like_row():
    bad=rows()
    bad[0]["finish_position"]=1
    with pytest.raises(ValueError):
        normalize_f_counts(formal(),bad)


def test_rejects_bool_or_negative_f_count():
    bad=rows(); bad[0]["f_count"]=True
    with pytest.raises(ValueError):
        normalize_f_counts(formal(),bad)
    bad=rows(); bad[0]["f_count"]=-1
    with pytest.raises(ValueError):
        normalize_f_counts(formal(),bad)


def test_future_select_is_narrow_and_result_free():
    q=FUTURE_APPROVED_SELECT.lower()
    assert q=="select race_id,lane,f_count from v2_race_entries where race_id=any(%s) order by race_id,lane"
    for token in ("result","odds","payout","finish","winner"):
        assert token not in q
