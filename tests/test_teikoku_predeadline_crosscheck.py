# -*- coding: utf-8 -*-
import pytest

from research.teikoku_predeadline_crosscheck import (
    MIN_INTERVAL_SEC,
    RespectfulFetcher,
    find_pre_race_table,
    validate_url,
)


def test_only_known_teikoku_race_detail_url_is_allowed():
    m = validate_url(
        "https://boatrace-db.net/race/detail/date/20250701/pid/19/rno/10/"
    )
    assert m.group("date") == "20250701"
    assert m.group("pid") == "19"
    assert m.group("rno") == "10"
    with pytest.raises(ValueError):
        validate_url("https://example.com/race/detail/date/20250701/pid/19/rno/10/")
    with pytest.raises(ValueError):
        validate_url("https://boatrace-db.net/result/highpo/month/202507/")


def test_pre_race_table_is_selected_without_result_table():
    html = """
    <html><body>
      <table><tr><td>3連単</td><td>1-2-3</td><td>1000円</td></tr></table>
      <table>
        <tr><th>艇番</th><th>登録番号</th><th>F</th><th>今期</th><th>全国</th><th>モータ</th></tr>
        <tr><td>1</td><td>3618 選手A</td><td>0</td><td>5.0</td><td>5.5</td><td>69</td></tr>
        <tr><th>L</th><th>当地</th><th>ボート</th></tr>
      </table>
    </body></html>
    """
    out = find_pre_race_table(html)
    assert "3618" in out["racer_number_candidates"]
    assert out["result_markers_excluded"] is True


def test_rate_limiter_sleeps_to_three_seconds_between_requests(monkeypatch):
    times = iter([10.0, 10.0, 11.0, 13.05])
    sleeps = []
    f = RespectfulFetcher(
        sleep_fn=lambda sec: sleeps.append(sec),
        clock_fn=lambda: next(times),
    )

    class Resp:
        apparent_encoding = "utf-8"
        text = "<html></html>"
        def raise_for_status(self):
            return None

    monkeypatch.setattr(f.session, "get", lambda *a, **k: Resp())
    url = "https://boatrace-db.net/race/detail/date/20250701/pid/19/rno/10/"
    f.get(url)
    f.get(url)
    assert len(sleeps) == 1
    assert round(sleeps[0], 2) == round(MIN_INTERVAL_SEC - 1.0, 2)
