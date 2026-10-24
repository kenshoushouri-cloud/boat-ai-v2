"""Offline regression tests; never connect to PostgreSQL."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from deploy.conoha import v5_stage_12_bootstrap_guarded as bootstrap


class EmptyStageBootstrapTests(unittest.TestCase):
    def test_thirteen_route_contract_yields_exactly_twelve_new_stages(self):
        pairs=bootstrap.planned()
        self.assertEqual(len(pairs),12)
        self.assertEqual(len(set(dst for _,dst in pairs)),12)
        self.assertTrue(all(dst.startswith("boat_data_stage.") for _,dst in pairs))
        self.assertTrue(all(src != "public.v2_venues" for src,_ in pairs))

    def test_transactional_atomic_ddl_no_source_rows_or_shared_sequence(self):
        sql=bootstrap.ddl_plan()
        self.assertIn("BEGIN;",sql)
        self.assertIn("COMMIT;",sql)
        self.assertIn("SET LOCAL lock_timeout",sql)
        self.assertEqual(sql.count("CREATE TABLE "),12)
        self.assertIn('CREATE TABLE "boat_data_stage"."entries"',sql)
        self.assertIn('LIKE "public"."v2_race_entries"',sql)
        self.assertIn("INCLUDING CONSTRAINTS INCLUDING INDEXES",sql)
        self.assertNotIn("INCLUDING ALL",sql)
        self.assertNotIn("INCLUDING DEFAULTS",sql)
        self.assertNotIn("INCLUDING IDENTITY",sql)
        self.assertNotIn("INCLUDING GENERATED",sql)
        self.assertNotIn("INSERT INTO",sql)
        self.assertNotIn("DELETE FROM",sql)
        self.assertNotIn("DROP TABLE",sql)
        self.assertNotIn("ALTER VIEW",sql)
        self.assertNotIn('CREATE TABLE "boat_data_stage"."venues"',sql)

    def test_existing_stage_conflict_fails_transaction(self):
        sql=bootstrap.ddl_plan()
        self.assertIn("NO_GO_EXISTING_VENUES_STAGE_MISSING",sql)
        self.assertIn("NO_GO_STAGE_EXISTS",sql)
        self.assertIn("NO_GO_PK_MISSING_OR_AMBIGUOUS",sql)
        self.assertIn("NO_GO_STAGE_DEFAULT_SEQUENCE_OR_SIDE_EFFECT",sql)
        self.assertIn("NO_GO_STAGE_COLUMNS_MISMATCH",sql)

    def test_stage_apply_rejects_false_misleading_and_missing_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"gate.json"
            bad={"approval_marker":bootstrap.APPROVAL_MARKER}
            bad.update({k:"YES" for k in bootstrap.MANDATORY_EVIDENCE})
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,"gate missing"):
                bootstrap.gates_verified(str(path))
            bad.update({k:True for k in bootstrap.MANDATORY_EVIDENCE})
            path.write_text(json.dumps(bad))
            bootstrap.gates_verified(str(path))
            bad["approval_marker"]="V5_CUTOVER_ALLOWED"
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,"marker missing"):
                bootstrap.gates_verified(str(path))

    def test_unqualified_identifier_rejected(self):
        for val in ("public.v2_results;DELETE", "unqualified", "x.y.z", "x.abc-xyz"):
            with self.subTest(val=val):
                with self.assertRaises(ValueError):
                    bootstrap.qname(val)

    def test_apply_not_triggered_without_scoped_authorization(self):
        with patch.dict("os.environ",{},clear=True):
            with patch.object(bootstrap.subprocess,"run") as runner:
                with self.assertRaisesRegex(ValueError,"authorization missing"):
                    with patch("sys.argv",["test","--apply"]):
                        bootstrap.main()
                runner.assert_not_called()


if __name__=="__main__":
    unittest.main()
