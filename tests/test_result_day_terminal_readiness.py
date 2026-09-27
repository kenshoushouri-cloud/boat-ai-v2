from research.result_day_terminal_readiness_pg import classify_result, summarize


def row(race_id, *, present=True, rs="", rcs="", ticket=None, payout=0):
    return {
        "race_id": race_id,
        "result_present": present,
        "result_status": rs,
        "race_status": rcs,
        "trifecta_ticket": ticket,
        "trifecta_payout_yen": payout,
    }


def test_official_and_cancelled_are_terminal():
    rows = [
        row("a", rs="official", rcs="official", ticket="1-2-3", payout=1230),
        row("b", rs="cancelled", rcs="cancelled"),
    ]
    assert classify_result(rows[0]) == "OFFICIAL"
    assert classify_result(rows[1]) == "VOID"
    s = summarize(rows)
    assert s["ready"] is True
    assert s["terminal"] == 2


def test_missing_or_incomplete_is_not_ready():
    rows = [
        row("a", present=False),
        row("b", rs="official", rcs="official", ticket=None, payout=0),
    ]
    assert summarize(rows)["ready"] is False
    assert classify_result(rows[0]) == "MISSING"
    assert classify_result(rows[1]) == "PENDING"


def test_empty_day_fails_closed():
    s = summarize([])
    assert s["ready"] is False
    assert s["races"] == 0
