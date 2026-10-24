"""Offline stage executor safety unit tests. No DB, no side effects."""
import unittest

from deploy.conoha.v5_online_stage_batch_copy import COPY_GATES, assess
from deploy.conoha.boat_shared_staging_delta_plan_offline import blockers
from v5.offline_stage_chunk_copy_sql import make_key_select


def fixtures():
    columns = [
        ("id",23,-1,0,True,"","","nextval('public.shared_id_seq'::regclass)"),
        ("race_id",25,-1,100,True,"","",""),
        ("lane",23,-1,0,True,"","",""),
    ]
    stage_columns = [(*col[:7], "") for col in columns]
    src = dict(kind="r",oid=101,schema="public",name="v2_realtime_entry_snapshots",
               cols=columns,pk=("id",),user_triggers=0,foreign_keys=0)
    dst = dict(kind="r",oid=102,schema="boat_data_stage",name="entry_snapshots",
               cols=stage_columns,pk=("id",),user_triggers=0,foreign_keys=0)
    return src,dst


class StageExecutorOfflineTests(unittest.TestCase):
    def test_stage_absence_does_not_authorize_creation_or_copy(self):
        old,_ = fixtures()
        shape,issues=assess("public.v2_realtime_entry_snapshots",old,None)
        self.assertIsNone(shape)
        self.assertIn("stage_missing_or_not_physical",issues)

    def test_existing_venues_stage_is_preserve_only(self):
        old,dst=fixtures()
        shape,issues=assess("public.v2_venues",old,dst)
        self.assertIsNone(shape)
        self.assertIn("existing_venues_stage_preserve_only",issues)

    def test_stage_with_own_defaults_absent_gets_compatible_shape(self):
        old,dst=fixtures()
        shape,issues=assess("public.v2_realtime_entry_snapshots",old,dst)
        self.assertEqual(issues,[])
        self.assertEqual(shape.staged,"boat_data_stage.entry_snapshots")
        self.assertEqual(shape.pk,("id",))
        sql,params=make_key_select(shape,None,250)
        self.assertIn('FROM "public"."v2_realtime_entry_snapshots"',sql)
        self.assertEqual(params,(250,))

    def test_source_shared_sequence_not_copied_to_stage(self):
        old,dst=fixtures()
        dst["cols"][0]=(*dst["cols"][0][:7],"nextval('public.shared_id_seq'::regclass)")
        _,issues=assess("public.v2_realtime_entry_snapshots",old,dst)
        self.assertIn("unsafe_stage_identity_generated_or_serial",issues)

    def test_primary_key_mismatch_and_side_effects_denied(self):
        old,dst=fixtures()
        dst["pk"]=("race_id","lane")
        dst["user_triggers"]=1
        _,issues=assess("public.v2_realtime_entry_snapshots",old,dst)
        self.assertIn("source_stage_primary_key_mismatch",issues)
        self.assertIn("stage_side_effect_trigger_or_fk",issues)

    def test_copy_gates_fail_closed_and_no_string_yes(self):
        self.assertEqual(blockers(COPY_GATES,{}),COPY_GATES)
        self.assertEqual(blockers(COPY_GATES,{x:"YES" for x in COPY_GATES}),COPY_GATES)


if __name__=="__main__":
    unittest.main()
