# -*- coding: utf-8 -*-
from datetime import date

import pytest

from research.historical_predeadline_pilot import (
    MinInterval,
    extract_predeadline_text,
    official_b_url,
    teikoku_url,
)


def test_urls_are_deterministic_and_existing_shape_only():
    d = date(2025, 7, 17)
    assert teikoku_url(d, 24, 12) == (
        "https://boatrace-db.net/race/detail/date/20250717/pid/24/rno/12/"
    )
    assert official_b_url(d) == (
        "https://www1.mbrace.or.jp/od2/B/202507/b250717.lzh"
    )


def test_extract_uses_only_tail_after_predeadline_marker():
    html = """
    <html><body>
      <div>結果 3連単 1-2-3 999999円</div>
      <div>場外締切 20:45</div>
      <div>F 今期 全国 モータ</div>
      <div>L 当地 ボート</div>
      <div>3908 重成 一人 A1 ST.14</div>
    </body></html>
    """
    out = extract_predeadline_text(html)
    assert out["deadline_text"] == "20:45"
    assert out["outcome_prefix_removed"] is True
    assert "999999" not in out["predeadline_text"]
    assert "3連単" not in out["predeadline_text"]
    assert "ST.14" in out["predeadline_text"]


def test_extract_fails_closed_when_race_card_markers_missing():
    with pytest.raises(ValueError):
        extract_predeadline_text("<html>場外締切 12:34 全国</html>")


def test_min_interval_cannot_be_configured_below_three_seconds():
    assert MinInterval(0.1).seconds == 3.0
    assert MinInterval(3.2).seconds == 3.2
