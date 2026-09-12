from __future__ import annotations

import unittest

from research.odds_race_date_index_static_audit import classify_sql


class OddsRaceDateIndexStaticAuditTests(unittest.TestCase):
    def test_join_filters_races_date_not_odds_date(self) -> None:
        finding = classify_sql(
            "x.py",
            1,
            """
            select o.race_id,o.ticket,o.odds
            from v2_races r
            join v2_odds_trifecta o on o.race_id=r.race_id
            where r.race_date between %s and %s
            """,
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertFalse(finding.direct_candidate)

    def test_qualified_odds_date_is_direct_candidate(self) -> None:
        finding = classify_sql(
            "x.py",
            2,
            "select * from v2_odds_trifecta o where o.race_date=%s",
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertTrue(finding.direct_qualified_race_date)
        self.assertTrue(finding.direct_candidate)

    def test_unqualified_odds_date_is_conservative_candidate(self) -> None:
        finding = classify_sql(
            "x.py",
            3,
            "select * from v2_odds_trifecta where race_date >= %s",
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertTrue(finding.unqualified_where_race_date)
        self.assertTrue(finding.direct_candidate)

    def test_race_id_range_is_not_date_candidate(self) -> None:
        finding = classify_sql(
            "x.py",
            4,
            "select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s",
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertFalse(finding.direct_candidate)

    def test_table_name_without_from_or_join_is_not_sql_consumer(self) -> None:
        finding = classify_sql(
            "x.py",
            5,
            "documentation mentions v2_odds_trifecta and race_date",
        )
        self.assertIsNone(finding)

    def test_where_keyword_is_not_treated_as_alias(self) -> None:
        finding = classify_sql(
            "x.py",
            6,
            "select * from v2_odds_trifecta where race_id=%s",
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.aliases, ("v2_odds_trifecta",))


if __name__ == "__main__":
    unittest.main()
