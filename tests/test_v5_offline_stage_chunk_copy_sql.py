"""Offline fail-closed copy SQL generator tests; no DB connections."""
import unittest

from v5.offline_stage_chunk_copy_sql import StageShape, make_window


def shape(**changes):
    base = dict(
        source="public.v2_realtime_entry_snapshots",
        staged="boat_data_stage.entry_snapshots",
        columns=("id", "race_id", "lane", "snapshot_label"),
        pk=("id",),
        stage_is_physical=True,
        schema_same=True,
        primary_key_same=True,
        stage_not_live_writer=True,
        no_shared_serial_defaults=True,
    )
    base.update(changes)
    return StageShape(**base)


class OnlineCopyGeneratorTest(unittest.TestCase):
    def test_first_chunk_is_bounded_and_explicit_columns(self):
        w = make_window(shape(), None, 200, (200,))
        self.assertIn('FROM "public"."v2_realtime_entry_snapshots"', w.select_keys_sql)
        self.assertIn('LIMIT %s', w.select_keys_sql)
        self.assertEqual(w.select_keys_params, (200,))
        self.assertEqual(w.insert_rows_params, (200,))
        self.assertIn('INSERT INTO "boat_data_stage"."entry_snapshots"', w.insert_rows_sql)
        self.assertIn('ON CONFLICT ("id") DO NOTHING', w.insert_rows_sql)
        self.assertNotIn("nextval", w.insert_rows_sql)
        self.assertEqual(w.mode, "SQL_GENERATION_ONLY_NOT_APPLIED")

    def test_keyset_cursor_uses_full_pk_and_advances(self):
        w = make_window(shape(pk=("race_id", "lane")), ("r01", 2), 300, ("r02", 6))
        self.assertEqual(w.select_keys_params, ("r01", 2, 300))
        self.assertEqual(w.insert_rows_params, ("r01", 2, "r02", 6))
        self.assertIn('("race_id", "lane") > (%s, %s)', w.select_keys_sql)
        self.assertIn('("race_id", "lane") <= (%s, %s)', w.insert_rows_sql)

    def test_venues_existing_stage_is_never_a_copy_target(self):
        with self.assertRaisesRegex(ValueError, "venues"):
            make_window(shape(source="public.v2_venues", staged="boat_data_stage.venues"), None, 3, ("01",))

    def test_missing_stage_proof_or_shared_sequence_denied(self):
        for field in ("stage_is_physical", "schema_same", "primary_key_same",
                      "stage_not_live_writer", "no_shared_serial_defaults"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "compatibility"):
                    make_window(shape(**{field:False}), None, 10, ("99",))

    def test_bad_identifiers_and_missing_pk_denied(self):
        for kw in (dict(columns=("id", "bad; DROP TABLE x")),
                   dict(columns=("id", "id")),
                   dict(pk=()),
                   dict(pk=("bad_column",))):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                make_window(shape(**kw), None, 10, (9,))

    def test_bounded_limit_and_cursor_rejection(self):
        for bad in (0, 501, True, 1.5):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "bounded"):
                make_window(shape(), None, bad, (9,))
        for after, end in (((2,), (2,)), ((4,), (3,)), ((1,2), (3,))):
            with self.subTest(after=after), self.assertRaises(ValueError):
                make_window(shape(), after, 10, end)


if __name__ == "__main__":
    unittest.main()
