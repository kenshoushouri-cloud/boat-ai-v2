# -*- coding: utf-8 -*-
from copy import deepcopy

import pytest

from research.v4_point_count_formal_replay import (
    V4PointCountFormalReplayError,
    build_day_input,
    evaluate_formal_replays,
)


def artifact():
    feed = []
    outcomes = []
    fixtures = [
        ("01", 1, "10:00", ["1-2-3","1-3-2","1-2-4","1-4-2","1-3-4"], "1-2-3", 500),
        ("02", 2, "10:10", ["2-1-3","2-3-1","2-1-4","2-4-1","2-3-4"], "2-3-1", 900),
        ("03", 3, "10:20", ["3-1-2","3-2-1","3-1-4","3-4-1","3-2-4"], "3-1-4", 1400),
        ("04", 4, "10:30", ["4-1-2","4-2-1","4-1-3","4-3-1","4-2-3"], "6-5-4", 8000),
        ("05", 5, "10:40", ["5-1-2","5-2-1","5-1-3","5-3-1","5-2-3"], "5-2-3", 2000),
        ("06", 6, "10:50", ["6-1-2","6-2-1","6-1-3","6-3-1","6-2-3"], "1-6-2", 1100),
    ]
    for venue, rank, hhmm, ranked, actual, payout in fixtures:
        race_id = f"20260924_{venue}_0{rank}"
        feed.append(
            {
                "race_id": race_id,
                "race_date": "2026-09-24",
                "venue_id": venue,
                "race_no": rank,
                "deadline_at": f"2026-09-24T{hhmm}:00+09:00",
                "tier": "A" if rank <= 2 else ("B" if rank <= 4 else "C"),
                "daily_rank": rank,
                "tickets": [
                    {
                        "ticket": ranked[0],
                        "core_order": 1,
                        "source": ["DISCOVERY_CORE"],
                        "legacy_rules": [],
                    },
                    {
                        "ticket": ranked[1],
                        "core_order": 2,
                        "source": ["DISCOVERY_CORE"],
                        "legacy_rules": [],
                    },
                ],
                "research_ranked_tickets": ranked,
                "legacy_carryover": False,
            }
        )
        outcomes.append(
            {
                "race_id": race_id,
                "status": "final",
                "actual_trifecta": actual,
                "trifecta_payout_yen": payout,
            }
        )

    art = {
        "contract": "candidate_discovery_v4_main_feed_v1",
        "generated_at_jst": "2026-09-24T08:20:00+09:00",
        "prospective_evidence_eligible": True,
        "purchase_action": False,
        "freeze_provenance": {
            "target_date": "2026-09-24",
            "completed_at_jst": "2026-09-24T08:20:00+09:00",
            "all_frozen_rows_pre_deadline": True,
            "outcome_read": False,
            "payout_read": False,
        },
        "feed": feed,
    }
    out = {
        "contract": "v4_point_count_formal_outcomes_v1",
        "target_date": "2026-09-24",
        "races": outcomes,
    }
    return art, out


def record():
    art, outcomes = artifact()
    return {
        "artifact": art,
        "artifact_sha256": "a" * 64,
        "outcomes": outcomes,
    }


def test_real_shape_top_five_replay_evaluates_all_point_counts():
    result = evaluate_formal_replays([record()])
    assert result["available_pre_result_rank_count"] == 5
    assert [row["status"] for row in result["strategies"]] == [
        "EVALUATED",
        "EVALUATED",
        "EVALUATED",
        "EVALUATED",
        "EVALUATED",
    ]
    assert [row["hit_races"] for row in result["strategies"]] == [1, 2, 3, 3, 4]
    assert result["historical_3_to_5_reconstruction_performed"] is False
    assert result["purchase_action"] is False
    assert result["production_mutation"] is False


def test_builder_preserves_exact_pre_result_rank_order():
    art, outcomes = artifact()
    day = build_day_input(
        art,
        artifact_sha256="b" * 64,
        outcomes=outcomes,
    )
    assert day["ranking_count"] == 5
    assert day["ranking_evidence_generated_at"] == "2026-09-24T08:20:00+09:00"
    assert day["races"][0]["ranked_tickets"] == [
        "1-2-3","1-3-2","1-2-4","1-4-2","1-3-4"
    ]


def test_research_top_two_must_equal_formal_top_two():
    rec = record()
    rec["artifact"]["feed"][0]["research_ranked_tickets"][:2] = [
        "1-4-3",
        "1-3-2",
    ]
    with pytest.raises(
        V4PointCountFormalReplayError,
        match="research top two do not match formal core tickets",
    ):
        evaluate_formal_replays([rec])


def test_exact_six_outcomes_required_without_extra_or_missing():
    rec = record()
    rec["outcomes"]["races"] = rec["outcomes"]["races"][:-1]
    with pytest.raises(
        V4PointCountFormalReplayError,
        match="exact six formal core race IDs",
    ):
        evaluate_formal_replays([rec])

    rec = record()
    rec["outcomes"]["races"].append(
        {
            "race_id": "20260924_07_07",
            "status": "final",
            "actual_trifecta": "1-2-3",
            "trifecta_payout_yen": 500,
        }
    )
    with pytest.raises(
        V4PointCountFormalReplayError,
        match="exact six formal core race IDs",
    ):
        evaluate_formal_replays([rec])


def test_non_final_outcome_blocks_whole_day():
    rec = record()
    rec["outcomes"]["races"][0]["status"] = "cancelled"
    with pytest.raises(
        V4PointCountFormalReplayError,
        match="outcome must be final",
    ):
        evaluate_formal_replays([rec])


def test_missing_or_short_top_five_blocks_replay():
    rec = record()
    rec["artifact"]["feed"][0]["research_ranked_tickets"] = [
        "1-2-3",
        "1-3-2",
    ]
    with pytest.raises(
        V4PointCountFormalReplayError,
        match="exactly five pre-result ticket ranks",
    ):
        evaluate_formal_replays([rec])


def test_freeze_must_precede_every_core_deadline():
    rec = record()
    rec["artifact"]["generated_at_jst"] = "2026-09-24T10:00:00+09:00"
    rec["artifact"]["freeze_provenance"]["completed_at_jst"] = (
        "2026-09-24T10:00:00+09:00"
    )
    with pytest.raises(
        V4PointCountFormalReplayError,
        match="not pre-deadline",
    ):
        evaluate_formal_replays([rec])


def test_generated_timestamp_must_equal_freeze_completion():
    rec = record()
    rec["artifact"]["freeze_provenance"]["completed_at_jst"] = (
        "2026-09-24T08:20:01+09:00"
    )
    with pytest.raises(
        V4PointCountFormalReplayError,
        match="must equal freeze completion",
    ):
        evaluate_formal_replays([rec])


def test_artifact_sha_must_be_explicit_lowercase_hex():
    rec = record()
    rec["artifact_sha256"] = "NOT_A_SHA"
    with pytest.raises(
        V4PointCountFormalReplayError,
        match="artifact_sha256",
    ):
        evaluate_formal_replays([rec])


def test_module_has_no_network_db_or_production_surface():
    import inspect
    import research.v4_point_count_formal_replay as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "psycopg",
        "database_url",
        "requests",
        "urllib",
        "railway",
        "line_notify",
        "subprocess",
        "os.environ",
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in source
