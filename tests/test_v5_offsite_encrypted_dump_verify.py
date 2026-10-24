"""Synthetic-only tests, no Google Drive/network/age credentials/DB used."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from v5 import offsite_encrypted_dump_verify as verify


class OffsiteBundleGuardTests(unittest.TestCase):
    def test_known_two_old_generation_sizes_and_no_current_claim(self):
        self.assertEqual(verify.EXPECTED, {
            "main_current_20261019.dump.age": 297756932,
            "archive_current_20261019.dump.age": 52130144,
        })

    def test_small_synthetic_age_ciphertext_sha_calculated(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "synthetic.age"
            p.write_bytes(verify.AGE_MAGIC + b"\nnot-a-real-ciphertext")
            r = verify.inspect_file(p, p.stat().st_size)
            self.assertEqual(r["bytes"], p.stat().st_size)
            self.assertEqual(len(r["sha256"]), 64)

    def test_size_mismatch_and_non_age_input_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.age"
            p.write_bytes(b"not encrypted")
            with self.assertRaisesRegex(ValueError, "size"):
                verify.inspect_file(p, 777)
            with self.assertRaisesRegex(ValueError, "header"):
                verify.inspect_file(p, len(b"not encrypted"))

    def test_symlink_input_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "real"
            p.write_bytes(verify.AGE_MAGIC)
            alias = Path(tmp) / "alias"
            alias.symlink_to(p)
            with self.assertRaisesRegex(ValueError, "symlink"):
                verify.inspect_file(alias, len(verify.AGE_MAGIC))

    def test_decryption_requires_external_machine_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "independent host"):
                verify.main(["--folder", tmp, "--decrypt-toc"])

    def test_missing_local_identity_rejected_without_secret_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(verify.shutil, "which", return_value="/usr/bin/fake"):
                with self.assertRaisesRegex(ValueError, "identity"):
                    verify.verify_decrypt_toc(Path(tmp)/"none.age",Path(tmp)/"no-key")

    def test_missing_bundle_cannot_emit_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                with self.assertRaisesRegex(ValueError, "absent"):
                    verify.main(["--folder",tmp])
            self.assertNotIn("V5_OFFSITE_ENCRYPTED_BUNDLE_FILE_CHECK_FINISHED", stdout.getvalue())

    def test_old_bundle_is_not_independent_restore_certificate(self):
        with tempfile.TemporaryDirectory() as tmp:
            filenames = { "main_current_20261019.dump.age":len(verify.AGE_MAGIC)+1,
                          "archive_current_20261019.dump.age":len(verify.AGE_MAGIC)+2}
            for name,size in filenames.items():
                (Path(tmp)/name).write_bytes(verify.AGE_MAGIC+b"x"*(size-len(verify.AGE_MAGIC)))
            with patch.object(verify, "EXPECTED", filenames):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(verify.main(["--folder",tmp]), 0)
            txt=stdout.getvalue()
            self.assertIn('"full_independent_db_restore": "UNVERIFIED"',txt)
            self.assertIn('"current_2026_10_24_generation": "NOT_COVERED"',txt)
            self.assertIn('"production_cutover": "NO_GO"',txt)
            self.assertIn("V5_OFFSITE_ENCRYPTED_BUNDLE_FILE_CHECK_FINISHED",txt)


if __name__=="__main__":
    unittest.main()
