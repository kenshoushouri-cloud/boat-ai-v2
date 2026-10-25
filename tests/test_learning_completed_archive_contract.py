# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import replace
from datetime import date
import unittest

from research.learning_completed_archive_contract import (
    ARCHIVE_FORMAT,
    COMPRESSION_FORMAT,
    CONTRACT_VERSION,
    SOURCE_LABEL,
    TABLE_IDENTITIES,
    ArchiveContractError,
    ArchiveManifest,
    deletion_gate,
    validate_archive_set,
    validate_manifest,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def manifest(
    table: str = "v2_realtime_odds_snapshots",
    start: date = date(2026, 9, 1),
    end: date = date(2026, 9, 1),
) -> ArchiveManifest:
    identity = TABLE_IDENTITIES[table]
    cols = tuple(dict.fromkeys((
        "id", "race_id", "race_date", "snapshot_label", "snapshot_at", *identity, "odds", "raw"
    )))
    types = tuple("text" for _ in cols)
    return ArchiveManifest(
        contract_version=CONTRACT_VERSION,
        table_name=table,
        source_label=SOURCE_LABEL,
        archive_format=ARCHIVE_FORMAT,
        compression_format=COMPRESSION_FORMAT,
        start_date=start,
        end_date=end,
        source_row_count=120,
        restored_row_count=120,
        column_names=cols,
        column_type_names=types,
        identity_columns=identity,
        schema_sha256=SHA_A,
        source_content_sha256=SHA_B,
        restored_content_sha256=SHA_B,
        archive_file_sha256=SHA_C,
    )


class LearningCompletedArchiveContractTests(unittest.TestCase):
    TODAY = date(2026, 9, 12)

    def test_valid_manifest_passes(self):
        validate_manifest(manifest(), today=self.TODAY)

    def test_all_six_table_identities_pass(self):
        for table in TABLE_IDENTITIES:
            with self.subTest(table=table):
                validate_manifest(manifest(table=table), today=self.TODAY)

    def test_current_day_is_blocked(self):
        m = manifest(start=self.TODAY, end=self.TODAY)
        with self.assertRaises(ArchiveContractError):
            validate_manifest(m, today=self.TODAY)

    def test_non_learning_label_is_blocked(self):
        with self.assertRaises(ArchiveContractError):
            validate_manifest(replace(manifest(), source_label="final_ab"), today=self.TODAY)

    def test_unknown_table_is_blocked(self):
        with self.assertRaises(ArchiveContractError):
            validate_manifest(replace(manifest(), table_name="v2_results"), today=self.TODAY)

    def test_restore_count_mismatch_is_blocked(self):
        with self.assertRaises(ArchiveContractError):
            validate_manifest(replace(manifest(), restored_row_count=119), today=self.TODAY)

    def test_restore_checksum_mismatch_is_blocked(self):
        with self.assertRaises(ArchiveContractError):
            validate_manifest(replace(manifest(), restored_content_sha256=SHA_C), today=self.TODAY)

    def test_identity_contract_mismatch_is_blocked(self):
        with self.assertRaises(ArchiveContractError):
            validate_manifest(replace(manifest(), identity_columns=("race_id",)), today=self.TODAY)

    def test_missing_common_column_is_blocked(self):
        m = manifest()
        cols = tuple(x for x in m.column_names if x != "snapshot_at")
        types = tuple("text" for _ in cols)
        with self.assertRaises(ArchiveContractError):
            validate_manifest(replace(m, column_names=cols, column_type_names=types), today=self.TODAY)

    def test_overlapping_archive_units_are_blocked(self):
        a = manifest(start=date(2026, 9, 1), end=date(2026, 9, 3))
        b = manifest(start=date(2026, 9, 3), end=date(2026, 9, 4))
        with self.assertRaises(ArchiveContractError):
            validate_archive_set((a, b), today=self.TODAY)

    def test_nonoverlapping_units_pass(self):
        a = manifest(start=date(2026, 9, 1), end=date(2026, 9, 2))
        b = manifest(start=date(2026, 9, 3), end=date(2026, 9, 4))
        validate_archive_set((a, b), today=self.TODAY)

    def test_gate_never_returns_delete_authorization(self):
        result = deletion_gate((manifest(),), today=self.TODAY)
        self.assertIn("SEPARATE_APPROVAL", result)
        self.assertNotEqual(result, "DELETE_AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
