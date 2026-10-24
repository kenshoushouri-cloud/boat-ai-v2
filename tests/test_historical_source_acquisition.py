# -*- coding: utf-8 -*-
from datetime import date

from research.historical_official_archive_capture import archive_url, iter_days
from research.teikoku_historical_raw_capture import validate_url


def test_official_b_k_url_contract():
    day = date(2025, 7, 31)
    assert archive_url("B", day) == (
        "https://www1.mbrace.or.jp/od2/B/202507/b250731.lzh"
    )
    assert archive_url("K", day) == (
        "https://www1.mbrace.or.jp/od2/K/202507/k250731.lzh"
    )


def test_iter_days_inclusive():
    assert [d.isoformat() for d in iter_days("2025-07-01", "2025-07-03")] == [
        "2025-07-01", "2025-07-02", "2025-07-03"
    ]


def test_teikoku_only_accepts_known_race_detail_shape():
    m = validate_url(
        "https://boatrace-db.net/race/detail/date/20250731/pid/14/rno/07/"
    )
    assert m == {"date": "20250731", "pid": "14", "rno": "07"}


def test_teikoku_rejects_non_detail_paths():
    try:
        validate_url("https://boatrace-db.net/stadium/index2/pid/23/")
    except ValueError:
        pass
    else:
        raise AssertionError("non-race-detail URL must fail")
