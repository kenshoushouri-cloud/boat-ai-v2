"""Synthetic rehearsal for 13 V5 Counter family totals, with HOLD always set."""
from __future__ import annotations

import unittest
import io
import os
import runpy
import sys
from contextlib import redirect_stdout
from types import ModuleType
from unittest.mock import MagicMock, patch
from dataclasses import replace
from datetime import date

from v5.conoha_research_one_day_sources_readonly import (
    assemble_source_proposals,
)
from v5.offline_unverified_counter_shape_preview import (
    rehearse_unverified_counter_shapes, preview_summary,
)
from v5.conoha_research_source_contract import SourceProposals

DAY=date(2026,10,20)

def one(rid, exh):
    return [
        dict(
            race_id=rid,lane=i,racer_number=4200+i,
            racer_class=(4,3,2,1,4,2)[i-1],
            racer_class_text=("A1","A2","B1","B2","A1","B1")[i-1],
            k_racer_number=4200+i,
            start_course=i,finish_position=(2,1,3,4,5,6)[i-1],
            finish_status="0"+str((2,1,3,4,5,6)[i-1]),
            is_flying=False,is_late=False,
            exhibition_time_rank=i if exh else None,
            snapshot_label="conoha_forward_20261020_100000" if exh else None,
            result_status="official",race_status="official",
            trifecta_ticket="2-1-3",
        ) for i in range(1,7)
    ]

class TestUnverifiedCounterShape(unittest.TestCase):
    def setUp(self):
        self.proposals=assemble_source_proposals(
            DAY, one("20261020_21_02",True)
            +one("20261020_21_03",False))
    def test_all_thirteen_family_totals_and_no_model(self):
        x=rehearse_unverified_counter_shapes(self.proposals)
        self.assertEqual((x.fit_candidates,x.course_candidates),(1,2))
        self.assertEqual(dict(x.aggregates),{
            "lw":1,"lcs":6,"lcw":1,"rks":6,"rkw":1,
            "cs":12,"ct":6,"rcs":12,"rct":6,"ps":30,
            "pw":5,"vc":1,"vn":1,
        })
        self.assertFalse(x.fitted_prior_day_state)
        self.assertFalse(x.buy_eligible)
        self.assertFalse(x.forward_eligible)
        txt=preview_summary(x)
        self.assertIn("V5_SHAPE_ONLY_13_COUNTER_FAMILIES=13",txt)
        self.assertIn("PRIOR_STATE_FITTED=0",txt)

    def test_reject_mismatched_fit_k_racer(self):
        src=self.proposals
        p=src.fit_proposals[0]
        b=list(p.boats)
        b[0]=replace(b[0],racer_number=9999)
        with self.assertRaisesRegex(ValueError,"FIT_AND_K_FIELDS_INCONSISTENT"):
            rehearse_unverified_counter_shapes(
                replace(src,fit_proposals=(replace(p,boats=tuple(b)),))
            )

    def test_no_fabricated_positive_incident_or_refund(self):
        src=self.proposals
        p=src.fit_proposals[0]
        with self.assertRaisesRegex(ValueError,"FIT_CANDIDATE_NOT_UNVERIFIED_MATCHED"):
            rehearse_unverified_counter_shapes(
                replace(src,fit_proposals=(replace(p,refund_boats=()),))
            )
        with self.assertRaisesRegex(ValueError,"AUTHORIZED_SOURCE_NOT_ALLOWED"):
            rehearse_unverified_counter_shapes(
                replace(src,retrospective_fit_authorized=True)
            )

    def test_reject_fit_without_corresponding_k(self):
        src=self.proposals
        with self.assertRaisesRegex(ValueError,"SOURCE_PROPOSAL_CARDINALITY_MISMATCH"):
            rehearse_unverified_counter_shapes(
                replace(src,course_proposals=())
            )
        with self.assertRaisesRegex(ValueError,"DUPLICATE_CANDIDATE_RACE"):
            rehearse_unverified_counter_shapes(
                replace(src,course_proposals=(src.course_proposals[1],src.course_proposals[1]))
            )
        with self.assertRaisesRegex(ValueError,"FIT_CANDIDATE_NOT_UNVERIFIED_MATCHED"):
            rehearse_unverified_counter_shapes(
                replace(src,course_proposals=(
                    replace(src.course_proposals[0],race_id="20261020_21_04"),
                    src.course_proposals[1],
                ))
            )

    def test_zero_sources_stays_zero_and_hold(self):
        src=assemble_source_proposals(DAY,[])
        x=rehearse_unverified_counter_shapes(src)
        self.assertEqual(len(x.aggregates),13)
        self.assertEqual(sum(v for _,v in x.aggregates),0)
        self.assertFalse(x.buy_eligible)

class TestModuleModeSourceContract(unittest.TestCase):
    def test_runpy_alias_uses_canonical_proposals_type(self):
        # Formerly this data class lived inside the -m program. Re-importing
        # the same code under another name yielded a distinct class object.
        with patch("warnings.warn"):
            isolated=runpy.run_module(
                "v5.conoha_research_one_day_sources_readonly",
                run_name="v5_second_import_for_test",
            )
        src=isolated["assemble_source_proposals"](
            DAY,one("20261020_21_02",True)
        )
        self.assertIs(type(src),SourceProposals)
        report=preview_summary(rehearse_unverified_counter_shapes(src))
        self.assertIn("SHAPE_LW_TOTAL=1",report)
        self.assertIn("PRIOR_STATE_FITTED=0",report)

    def test_exact_minus_m_entry_point_with_mocked_db(self):
        # Run the same __main__ execution pattern as the ConoHa command,
        # but intercept all database access. This catches -m type splits.
        conn=MagicMock()
        cur=conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value=one("20261020_21_02",True)
        pg=ModuleType("psycopg")
        pg.connect=MagicMock(return_value=conn)
        pg_rows=ModuleType("psycopg.rows")
        pg_rows.dict_row=object()
        output=io.StringIO()
        with patch.dict(sys.modules,{"psycopg":pg,"psycopg.rows":pg_rows}), \
             patch.dict(os.environ,{"DATABASE_URL":"postgresql:///railway"}), \
             patch.object(sys,"argv",["-m","--date","2026-10-20","--counter-shape-preview"]), \
             patch("research.v5_recent_form_asof_audit_pg.local_connection_url",return_value="postgresql:///railway"), \
             patch("warnings.warn"), redirect_stdout(output):
            with self.assertRaises(SystemExit) as status:
                runpy.run_module(
                    "v5.conoha_research_one_day_sources_readonly",
                    run_name="__main__",
                )
        self.assertEqual(status.exception.code,0)
        self.assertIn("V5_SHAPE_ONLY_13_COUNTER_FAMILIES=13",output.getvalue())
        self.assertIn("FIT_CANDIDATES_NOT_AUTHORIZED=1",output.getvalue())
        self.assertIn("PRIOR_STATE_FITTED=0",output.getvalue())
        self.assertIn("BUY_ELIGIBLE=0",output.getvalue())
        pg.connect.assert_called_once()
        conn.rollback.assert_called_once()


if __name__=="__main__":
    unittest.main()
