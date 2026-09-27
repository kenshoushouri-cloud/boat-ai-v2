from research.forward_economics import (
    coverage,
    forward_report,
    investment_yen,
    is_economically_settled,
    metrics,
    risk,
)


def row(day, status, *, hit=False, ret=0, payout=None, inv=100):
    return {
        "race_date": day,
        "evaluation_status": status,
        "hit": hit,
        "return_yen": ret,
        "payout_yen": ret if payout is None else payout,
        "investment_yen": inv,
    }


def test_invalid_result_is_void_not_a_losing_bet():
    rows = [
        row("2026-09-21", "evaluated", hit=False),
        row("2026-09-21", "invalid_result", hit=False, ret=0),
        row("2026-09-21", "pending", hit=False, ret=0),
    ]
    assert coverage(rows) == {
        "rows": 3,
        "evaluated": 1,
        "invalid_result": 1,
        "pending": 1,
    }
    assert investment_yen(rows[1]) == 0
    assert not is_economically_settled(rows[1])
    m = metrics(rows)
    assert m["evaluated"] == 1
    assert m["investment_yen"] == 100
    assert m["profit_yen"] == -100
    assert m["roi_pct"] == 0.0


def test_metrics_and_largest_hit_share():
    rows = [
        row("2026-09-21", "evaluated", hit=True, ret=400),
        row("2026-09-21", "evaluated", hit=False),
        row("2026-09-22", "evaluated", hit=True, ret=200),
        row("2026-09-22", "invalid_result"),
    ]
    m = metrics(rows)
    assert m["evaluated"] == 3
    assert m["hits"] == 2
    assert m["investment_yen"] == 300
    assert m["return_yen"] == 600
    assert m["profit_yen"] == 300
    assert m["roi_pct"] == 200.0
    assert m["largest_hit_share_pct"] == 66.6667


def test_risk_ignores_invalid_results():
    rows = [
        row("2026-09-21", "evaluated", hit=False),
        row("2026-09-21", "invalid_result"),
        row("2026-09-22", "evaluated", hit=False),
        row("2026-09-23", "evaluated", hit=True, ret=500),
        row("2026-09-24", "evaluated", hit=False),
    ]
    r = risk(rows)
    assert r["max_losing_streak"] == 2
    assert r["max_drawdown_yen"] == 200


def test_forward_report_is_policy_neutral():
    rows = [
        row("2026-09-21", "evaluated", hit=True, ret=300),
        row("2026-09-22", "evaluated", hit=False),
        row("2026-09-23", "invalid_result"),
    ]
    report = forward_report(rows, bootstrap_samples=100, bootstrap_seed=7)
    assert report["coverage"]["evaluated"] == 2
    assert report["coverage"]["invalid_result"] == 1
    assert report["overall"]["investment_yen"] == 200
    assert report["promotion_allowed"] is False
    assert report["production_change"] is False
    assert report["purchase_action"] is False
