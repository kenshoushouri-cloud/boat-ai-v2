# -*- coding: utf-8 -*-
from datetime import date

import pytest

from research.teikoku_motor_history_probe import (
    AccessLimiter,
    extract_dated_tokens,
    prior_only_tokens,
    summarize_motor_page,
    validate_known_motor_url,
)


def test_known_motor_url_only():
    assert validate_known_motor_url(
        "https://boatrace-db.net/stadium/mdetail/pid/24/mno/60/"
    ) == ("24", 60)
    with pytest.raises(ValueError):
        validate_known_motor_url("https://boatrace-db.net/result/highpo/month/202507/")
    with pytest.raises(ValueError):
        validate_known_motor_url("https://example.com/stadium/mdetail/pid/24/mno/60/")


def test_access_interval_cannot_be_below_published_rule():
    AccessLimiter(3.0)
    with pytest.raises(ValueError):
        AccessLimiter(2.99)


def test_prior_only_filter_excludes_cutoff_and_future():
    text = (
        "開催 2025年7月4日 ～ 7月5日 7月9日 "
        "次節 2025年7月15日 ～ 7月16日"
    )
    tokens = extract_dated_tokens(text, default_year=2025)
    prior = prior_only_tokens(tokens, date(2025, 7, 15))
    assert [x.iso for x in prior] == [
        "2025-07-04",
        "2025-07-05",
        "2025-07-09",
    ]


def test_summary_never_uses_aggregate_as_historical_snapshot():
    html = """
    <html><head><title>艇国DB motor</title></head><body>
      最終データ更新：2025/12/26 21:45
      ※集計期間 ： 2025年7月4日 ～ 2025年12月25日。
      <table>
        <tr><th>開催</th><td>大村一般 2025年7月4日 ～</td></tr>
        <tr><td>7月5日</td><td>7月9日</td></tr>
        <tr><th>開催</th><td>大村G2 2025年7月15日 ～</td></tr>
        <tr><td>7月16日</td></tr>
      </table>
    </body></html>
    """
    out = summarize_motor_page(html, cutoff=date(2025, 7, 15))
    assert out["prior_only_reconstruction_possible"] is True
    assert out["prior_only_max_date"] == "2025-07-09"
    assert out["target_or_future_min_date"] == "2025-07-15"
