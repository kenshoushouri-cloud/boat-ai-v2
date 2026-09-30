# -*- coding: utf-8 -*-
from research.historical_beforeinfo_probe import probe


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.apparent_encoding = "utf-8"
        self.encoding = "utf-8"

    def raise_for_status(self):
        return None


def test_probe_contract(monkeypatch):
    html = """
    <html><body>
    晴 気温 25.0℃ 水温 24.0℃ 風速 3m 北 波高 3cm
    <table>
      <tr><td>1</td><td>6.71</td><td>0.11</td></tr>
      <tr><td>2</td><td>6.72</td><td>0.12</td></tr>
      <tr><td>3</td><td>6.73</td><td>0.13</td></tr>
      <tr><td>4</td><td>6.74</td><td>0.14</td></tr>
      <tr><td>5</td><td>6.75</td><td>0.15</td></tr>
      <tr><td>6</td><td>6.76</td><td>0.16</td></tr>
    </table>
    </body></html>
    """
    monkeypatch.setattr(
        "research.historical_beforeinfo_probe.requests.get",
        lambda *args, **kwargs: FakeResponse(html),
    )
    out = probe("2025-07-01", "21", 1)
    assert out["predeadline_by_nature"] is True
    assert out["result_page_read"] is False
    assert out["odds_page_read"] is False
    assert out["db_write"] is False
    assert out["exhibition_rows"] == 6
    assert out["exhibition_time_values"] == 6
    assert out["start_timing_values"] == 6
    assert out["weather_nonnull_fields"] >= 4
