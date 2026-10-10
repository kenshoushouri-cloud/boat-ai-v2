from research.historical_racer_term_capture import FILES


def test_term_windows_cover_2025_07_through_2026_09():
    assert FILES[0]["name"] == "fan2504.lzh"
    assert FILES[0]["applies_from"] == "2025-07-01"
    assert FILES[1]["name"] == "fan2510.lzh"
    assert FILES[2]["name"] == "fan2604.lzh"
    assert FILES[2]["applies_through"] == "2026-12-31"
