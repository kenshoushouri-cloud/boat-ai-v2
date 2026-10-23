"""Five synthetic checks; no HTTP, DB, fitted Counter state, or BUY."""
from __future__ import annotations

import io
import os
import runpy
import sys
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date
from types import ModuleType
from unittest.mock import MagicMock, patch

from v5.conoha_research_one_day_sources_readonly import assemble_source_proposals
from v5.offline_unverified_counter_cell_preview import (
    count_unverified_cells, cell_summary,
)

DAY = date(2026, 10, 20)


def rows(rid, with_exhibition):
    return [
        dict(
            race_id=rid, lane=i, racer_number=4200+i,
            racer_class=(4,3,2,1,4,2)[i-1],
            racer_class_text=("A1","A2","B1","B2","A1","B1")[i-1],
            k_racer_number=4200+i, start_course=i,
            finish_position=(2,1,3,4,5,6)[i-1],
            finish_status=f"{(2,1,3,4,5,6)[i-1]:02d}",
            is_flying=False,is_late=False,
            exhibition_time_rank=i if with_exhibition else None,
            snapshot_label="conoha_forward_20261020_100000" if with_exhibition else None,
            result_status="official",race_status="official",
            trifecta_ticket="2-1-3",
        ) for i in range(1,7)
    ]


class TestHeldCounterCellPreview(unittest.TestCase):
    def setUp(self):
        self.src=assemble_source_proposals(
            DAY,rows("20261020_21_02",True)+rows("20261020_21_03",False)
        )

    def test_anonymous_exact_cells_13_families(self):
        x=count_unverified_cells(self.src)
        cells={k:(n,u) for k,n,u in x.family_cells}
        self.assertEqual(len(cells),13)
        self.assertEqual(cells["lw"],(1,1))
        self.assertEqual(cells["lcs"],(6,6))
        self.assertEqual(cells["rks"],(6,6))
        self.assertEqual(cells["ps"],(30,30))
        self.assertEqual(cells["pw"],(5,5))
        self.assertEqual(cells["vn"],(1,1))
        self.assertEqual(cells["cs"],(12,6))
        self.assertEqual(cells["rcs"],(12,6))
        self.assertEqual(cells["ct"],(6,3))
        self.assertEqual(cells["rct"],(6,3))
        self.assertFalse(x.source_authenticated)
        self.assertFalse(x.prior_state_fitted)
        self.assertFalse(x.forward_eligible)
        self.assertFalse(x.buy_eligible)
        summary=cell_summary(x)
        self.assertIn("CELL_PS_TOTAL=30_DISTINCT_NONZERO=30",summary)
        self.assertIn("PRIOR_STATE_FITTED=0",summary)

    def test_13_family_distinct_cell_math_matches_isolated_research_projection(self):
        # SYNTHETIC math parity ONLY. Mock 'OFFICIAL'/clean flags below are
        # deliberate unit-test fixtures, NEVER evidence about real races.
        # The real source object remains UNVERIFIED / hard HOLD.
        from collections import Counter
        from v5.offline_prior_day_factor_export import MAP_KEYS, NESTED
        from v5.offline_research_two_population_day import project_two_population_day

        synthetic = rows("20261020_21_02", True)
        synthetic += rows("20261020_21_03", False)
        cross_venue = rows("20261020_17_04", True)
        for entry in cross_venue:
            entry["racer_number"] += 100
            entry["k_racer_number"] += 100
            entry["exhibition_time_rank"] = 7-entry["lane"]
        synthetic += cross_venue
        src = assemble_source_proposals(DAY, synthetic)
        self.assertEqual((len(src.fit_proposals),len(src.course_proposals)),(2,3))
        audit = count_unverified_cells(src)
        self.assertFalse(audit.prior_state_fitted)
        self.assertFalse(audit.forward_eligible)
        self.assertFalse(audit.buy_eligible)
        self.assertTrue(all(p.refund_boats is None for p in src.fit_proposals))
        self.assertTrue(all(p.refund_boats is None for p in src.course_proposals))

        # Reference maths uses separately constructed synthetic, presumed-clean
        # rows in this test ONLY; do not pass these claims to the DB adapter.
        fit = tuple(replace(r, result_status="OFFICIAL",
                            incident_free_verified=True,refund_boats=())
                    for r in src.fit_proposals)
        k = tuple(replace(r,result_status="OFFICIAL",
                          incident_free_verified=True,refund_boats=())
                  for r in src.course_proposals)
        reference = project_two_population_day(DAY, fit, k)
        self.assertEqual(reference.state.completed_races,2)
        self.assertEqual(len(reference.course_race_ids),3)
        self.assertEqual(set(reference.state.counters), MAP_KEYS)
        got={key:(total,distinct) for key,total,distinct in audit.family_cells}
        self.assertEqual(set(got),MAP_KEYS)

        for key in sorted(MAP_KEYS):
            values=reference.state.counters[key]
            if key in NESTED:
                # Flatten nested (lane/racer OR venue/lane) counters so that
                # distinct cells mean *exactly* the same keys in both paths.
                flattened=Counter({
                    (outer,inner):int(count)
                    for outer,group in values.items()
                    for inner,count in group.items() if count>0
                })
            else:
                flattened=Counter({k:int(v) for k,v in values.items() if v>0})
            with self.subTest(counter_family=key):
                self.assertEqual(got[key],(sum(flattened.values()),len(flattened)))
        self.assertEqual(got["vc"],(2,2))
        self.assertEqual(got["vn"],(2,2))
        self.assertEqual(got["cs"],(18,6))

    def test_refund_eligibility_claims_refused(self):
        p=self.src.fit_proposals[0]
        unsafe=replace(self.src,fit_proposals=(
            replace(p,refund_boats=()),))
        with self.assertRaisesRegex(ValueError,"FIT_CANDIDATE_NOT_UNVERIFIED_MATCHED"):
            count_unverified_cells(unsafe)

    def test_mismatched_K_and_fit_refused(self):
        p=self.src.fit_proposals[0]
        b=list(p.boats)
        b[0]=replace(b[0],racer_number=9999)
        unsafe=replace(self.src,fit_proposals=(
            replace(p,boats=tuple(b)),))
        with self.assertRaisesRegex(ValueError,"FIT_AND_K_FIELDS_INCONSISTENT"):
            count_unverified_cells(unsafe)

    def test_empty_candidate_cells_remain_zero(self):
        x=count_unverified_cells(assemble_source_proposals(DAY,[]))
        self.assertEqual(len(x.family_cells),13)
        self.assertTrue(all(n==0 and d==0 for _,n,d in x.family_cells))

    def test_entrypoint_minus_m_counter_cells_no_real_db(self):
        conn=MagicMock()
        cur=conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value=rows("20261020_21_02",True)
        pg=ModuleType("psycopg")
        pg.connect=MagicMock(return_value=conn)
        pg_rows=ModuleType("psycopg.rows")
        pg_rows.dict_row=object()
        out=io.StringIO()
        with patch.dict(sys.modules,{"psycopg":pg,"psycopg.rows":pg_rows}), \
             patch.dict(os.environ,{"DATABASE_URL":"postgresql:///railway"}), \
             patch.object(sys,"argv",["-m","--date","2026-10-20","--counter-cell-preview"]), \
             patch("research.v5_recent_form_asof_audit_pg.local_connection_url",return_value="postgresql:///railway"), \
             patch("warnings.warn"), redirect_stdout(out):
            with self.assertRaises(SystemExit) as status:
                runpy.run_module("v5.conoha_research_one_day_sources_readonly",
                                 run_name="__main__")
        self.assertEqual(status.exception.code,0)
        self.assertIn("CELL_LCS_TOTAL=6_DISTINCT_NONZERO=6",out.getvalue())
        self.assertIn("BUY_ELIGIBLE=0",out.getvalue())
        conn.__enter__.return_value.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
