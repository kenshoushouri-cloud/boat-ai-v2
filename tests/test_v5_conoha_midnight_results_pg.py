"""No network and no database are used in these fail-closed catcher tests."""
from datetime import date, timedelta
from types import ModuleType
from unittest.mock import patch

import pytest

from v5.conoha_midnight_results_pg import recover_one, resolved, target_date


def test_verified_payout_only():
    assert resolved("official", "1-2-3", 6180)
    assert not resolved("official", "1-1-2", 6180)
    assert not resolved("official", "1-2-3", 0)
    assert not resolved("official", "1-2-3", None)
    assert not resolved("official", "1-2-3", "6180")
    assert not resolved("no_result_page", None, 0)
    assert not resolved("parse_error", None, 0)
    assert resolved("cancelled", None, 0)
    assert resolved("trifecta_invalid", None, 0)


def test_previous_day_default_and_reject_today_or_future():
    today = date(2026, 10, 20)
    assert target_date(None, today) == today - timedelta(days=1)
    assert target_date("2026-10-18", today).isoformat() == "2026-10-18"
    for raw in ("2026-10-20", "2026-10-21", "20261019", "2026-02-30",
                "2025-06-30"):
        with pytest.raises(ValueError):
            target_date(raw, today)


def _fake_parser(page):
    parser = ModuleType("repair_month_all_pg")
    calls = []

    def fake_fetch(_url):
        return "OFFICIAL_HTML"

    def fake_no_race(_html):
        return False

    def fake_parse(_html):
        return dict(page)

    def fake_save(*args, **kwargs):
        calls.append((args, kwargs))
        return 1

    parser._fetch = fake_fetch
    parser._looks_no_race = fake_no_race
    parser._official_url = lambda *args: "https://example.invalid/"
    parser.parse_result = fake_parse
    parser.upsert_rows = fake_save
    return parser, calls


@pytest.mark.parametrize("unresolved", [
    {"result_status": "no_result_page", "race_status": "no_result_page"},
    {"result_status": "parse_error", "race_status": "parse_error"},
    {"result_status": "official", "trifecta_ticket": "1-2-3",
     "trifecta_payout_yen": 0},
])
def test_never_write_unverified_response(unresolved):
    fake, calls = _fake_parser(unresolved)
    with patch.dict("sys.modules", {"repair_month_all_pg": fake}):
        outcome = recover_one("20261019_19_12", date(2026, 10, 19))
    assert outcome == "PENDING_UNVERIFIED"
    assert calls == []


def test_only_confirmed_result_is_upserted():
    fake, calls = _fake_parser({
        "result_status": "official", "race_status": "official",
        "trifecta_ticket": "1-2-3", "trifecta_payout_yen": 6180,
    })
    with patch.dict("sys.modules", {"repair_month_all_pg": fake}):
        outcome = recover_one("20261019_19_12", date(2026, 10, 19))
    assert outcome == "SAVED_OFFICIAL"
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == "v2_results"
    assert args[1][0]["race_date"] == "2026-10-19"
    assert args[1][0]["race_id"] == "20261019_19_12"
    assert args[2] == "race_id"
    assert kwargs["chunk_size"] == 1
