"""Pure offline validation of BOAT RACE official-index preview routing."""
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from v5 import native_official_index_preview as m


class OfficialIndexDiscoveryTests(unittest.TestCase):
    def test_strict_realistic_official_links(self):
        html = """<html>
        <a href="/owpc/pc/race/raceindex?hd=20261027&amp;jcd=02">02</a>
        <a href="https://www.boatrace.jp/owpc/pc/race/raceindex?jcd=04&amp;hd=20261027">04</a>
        <a href="/owpc/pc/race/raceindex?hd=20261027&amp;jcd=02">duplicate</a>
        </html>"""
        self.assertEqual(m.official_venues(html, "20261027"), ["02", "04"])

    def test_reject_wrong_day_or_outside_host(self):
        html = """<a href="/owpc/pc/race/raceindex?hd=20261026&jcd=01">old</a>
        <a href="https://evil.example/owpc/pc/race/raceindex?hd=20261027&jcd=02">wrong</a>"""
        self.assertEqual(m.official_venues(html, "20261027"), [])

    def test_reject_extra_parameters(self):
        html = """<a href="/owpc/pc/race/raceindex?hd=20261027&jcd=03&test=1">bad</a>
        <a href="/owpc/pc/race/raceindex?hd=20261027&jcd=03&jcd=04">duplicates</a>"""
        self.assertEqual(m.official_venues(html, "20261027"), [])

    def test_reject_out_of_range_venue(self):
        html = """<a href="/owpc/pc/race/raceindex?hd=20261027&jcd=00">bad</a>
        <a href="/owpc/pc/race/raceindex?hd=20261027&jcd=25">bad</a>
        <a href="/owpc/pc/race/raceindex?hd=20261027&jcd=24">good</a>"""
        self.assertEqual(m.official_venues(html, "20261027"), ["24"])

    def test_reject_non_raceindex_link(self):
        html = '<a href="/owpc/pc/race/racelist?hd=20261027&jcd=04">wrong</a>'
        self.assertEqual(m.official_venues(html, "20261027"), [])

    def test_date_default_tomorrow_jst(self):
        when = datetime(2026, 10, 26, 15, 25, tzinfo=timezone.utc)
        self.assertEqual(m.choose_day(when), "20261028")

    def test_date_today_or_tomorrow_only(self):
        when = datetime(2026, 10, 26, 23, 36, tzinfo=timezone(timedelta(hours=9)))
        self.assertEqual(m.choose_day(when, "20261027"), "20261027")
        with self.assertRaisesRegex(ValueError, "TODAY_OR_TOMORROW"):
            m.choose_day(when, "20261028")

    def test_no_venues_does_not_call_core_collector(self):
        with patch.object(m, "fetch_official_index", return_value="<html/>"):
            self.assertEqual(m.main(["--day", "20261027"]), 0)

    def test_index_parser_never_infers_from_random_urls(self):
        index = '<a href="/owpc/pc/race/index?hd=20261027">index</a>'
        self.assertEqual(m.official_venues(index, "20261027"), [])


if __name__ == "__main__":
    unittest.main()
