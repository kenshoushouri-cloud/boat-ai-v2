# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.v4_selector_rank_forward_diagnostic import (
    SOURCE_CONTRACT,
    summarize_selector_rank,
)


def row(day, rank, *, score, tickets=None, actual="1-2-3", payout=1000):
    tickets = tickets or ["1-2-3", "1-3-2"]
    return {
        "source_feed_contract": SOURCE_CONTRACT,
        "source_prospective_evidence_eligible": True,
        "purchase_action": False,
        "result_ready": True,
        "race_date": day,
        "race_id": f"{day.replace('-', '')}_01_{rank:02d}",
        "daily_rank": rank,
        "race_score": score,
        "formal_top2": tickets,
        "actual_trifecta": actual,
        "payout_yen": payout,
    }


def complete_day(day="2026-09-24"):
    rows = []
    for rank in range(1, 7):
        if rank <= 3:
            rows.append(
                row(
                    day,
                    rank,
                    score=0.99 - rank * 0.01,
                    actual="1-2-3",
                    payout=900,
                )
            )
        else:
            rows.append(
                row(
                    day,
                    rank,
                    score=0.95 - rank * 0.01,
                    actual="2-1-3",
                    payout=900,
                )
            )
    return rows


def test_rank_half_summary_is_diagnostic_only():
    out = summarize_selector_rank(complete_day(), bootstrap_reps=200, bootstrap_seed=7)
    assert out["formal_points"] == 2
    assert out["overall"]["races"] == 6
    assert out["rank_halves"]["rank_1_3"]["races"] == 3
    assert out["rank_halves"]["rank_4_6"]["races"] == 3
    assert out["rank_halves"]["rank_1_3"]["roi_percent"] == 450.0
    assert out["rank_halves"]["rank_4_6"]["roi_percent"] == 0.0
    assert out["race_score_gate_allowed"] is False
    assert out["candidate_count_change_allowed"] is False
    assert out["threshold_change_allowed"] is False
    assert out["rerank_allowed"] is False
    assert out["purchase_action"] is False
    assert out["promotion_allowed"] is False
    assert out["interpretation"] == "DIAGNOSTIC_ONLY_NO_SELECTOR_CHANGE"


def test_requires_exact_six_and_unique_ranks():
    rows = complete_day()
    try:
        summarize_selector_rank(rows[:-1], bootstrap_reps=20)
    except ValueError as exc:
        assert "exact six" in str(exc)
    else:
        raise AssertionError("missing formal race must fail closed")

    rows = complete_day()
    rows[-1]["daily_rank"] = 5
    try:
        summarize_selector_rank(rows, bootstrap_reps=20)
    except ValueError as exc:
        assert "ranks must be exactly 1..6" in str(exc)
    else:
        raise AssertionError("duplicate daily rank must fail closed")


def test_rejects_nonprospective_or_purchase_enabled_rows():
    rows = complete_day()
    rows[0]["source_prospective_evidence_eligible"] = False
    try:
        summarize_selector_rank(rows, bootstrap_reps=20)
    except ValueError as exc:
        assert "prospective timing eligibility" in str(exc)
    else:
        raise AssertionError("nonprospective row must fail closed")

    rows = complete_day()
    rows[0]["purchase_action"] = True
    try:
        summarize_selector_rank(rows, bootstrap_reps=20)
    except ValueError as exc:
        assert "purchase_action must be false" in str(exc)
    else:
        raise AssertionError("purchase-enabled row must fail closed")


def test_rejects_result_not_ready_and_does_not_reconstruct_tickets():
    rows = complete_day()
    rows[0]["result_ready"] = False
    try:
        summarize_selector_rank(rows, bootstrap_reps=20)
    except ValueError as exc:
        assert "exact-settled" in str(exc)
    else:
        raise AssertionError("unsettled row must fail closed")

    rows = complete_day()
    rows[0].pop("formal_top2")
    try:
        summarize_selector_rank(rows, bootstrap_reps=20)
    except ValueError as exc:
        assert "formal_top2" in str(exc)
    else:
        raise AssertionError("missing frozen ticket set must fail closed")


def test_source_has_no_mutating_or_integration_surface():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "research/v4_selector_rank_forward_diagnostic.py"
    ).read_text(encoding="utf-8").lower()

    for forbidden in (
        "psycopg",
        "requests",
        "httpx",
        "urllib",
        "subprocess",
        "insert into ",
        "update v2_",
        "delete from ",
        "alter table ",
        "drop table ",
        "truncate ",
        "vacuum ",
        "line_notify",
        "send_line",
        "purchase_action=true",
    ):
        assert forbidden not in source, forbidden

    assert '"race_score_gate_allowed": false' not in source
    assert '"candidate_count_change_allowed": false' not in source
    assert '"threshold_change_allowed": false' not in source
    assert '"promotion_allowed": false' not in source
    assert '"race_score_gate_allowed": false' not in source
