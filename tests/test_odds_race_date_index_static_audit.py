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

    def test_earlier_cte_race_date_does_not_taint_later_odds_reference(self) -> None:
        finding = classify_sql(
            "x.py",
            2,
            """
            with d as (
              select race_id from v2_races where race_date between %s and %s
            ), o as (
              select distinct race_id from v2_odds_trifecta
            )
            select count(*) from d left join o using(race_id)
            """,
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertFalse(finding.direct_candidate)

    def test_later_cte_race_date_after_odds_group_by_is_not_direct(self) -> None:
        finding = classify_sql(
            "x.py",
            3,
            """
            with races as (
              select race_id,race_date from v2_races where race_date between %s and %s
            ), o as (
              select o.race_id,count(distinct o.ticket) odds_n
              from v2_odds_trifecta o join races r using(race_id)
              where o.odds>1 group by o.race_id
            ), z as (
              select r.race_id,r.race_date from races r left join o using(race_id)
            )
            select to_char(race_date,'YYYY-MM') from z group by 1
            """,
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertFalse(finding.direct_candidate)

    def test_qualified_odds_date_is_direct_candidate(self) -> None:
        finding = classify_sql(
            "x.py",
            4,
            "select * from v2_odds_trifecta o where o.race_date=%s",
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertTrue(finding.direct_qualified_race_date)
        self.assertTrue(finding.direct_candidate)

    def test_unqualified_odds_date_is_conservative_candidate(self) -> None:
        finding = classify_sql(
            "x.py",
            5,
            "select * from v2_odds_trifecta where race_date >= %s",
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertTrue(finding.unqualified_where_race_date)
        self.assertTrue(finding.direct_candidate)

    def test_race_id_range_is_not_date_candidate(self) -> None:
        finding = classify_sql(
            "x.py",
            6,
            "select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s",
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertFalse(finding.direct_candidate)

    def test_table_name_without_from_or_join_is_not_sql_consumer(self) -> None:
        finding = classify_sql(
            "x.py",
            7,
            "documentation mentions v2_odds_trifecta and race_date",
        )
        self.assertIsNone(finding)

    def test_where_keyword_is_not_treated_as_alias(self) -> None:
        finding = classify_sql(
            "x.py",
            8,
            "select * from v2_odds_trifecta where race_id=%s",
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.aliases, ("v2_odds_trifecta",))


if __name__ == "__main__":
    unittest.main()
