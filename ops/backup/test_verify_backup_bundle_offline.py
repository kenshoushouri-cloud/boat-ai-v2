#!/usr/bin/env python3
"""Local only. Uses synthetic ciphertext; never accesses a DB or the network."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("verify_backup_bundle_offline.py")


class TestAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.name = "boat-ai-v3-20261014T100000Z-0123456789.dump.age"
        self.payload = b"SYNTHETIC_ONLY_NOT_AGE_CIPHERTEXT" * 20
        self.make_bundle()

    def make_bundle(self):
        (self.root / self.name).write_bytes(self.payload)
        sidecar = f"{hashlib.sha256(self.payload).hexdigest()}  {self.name}\n".encode()
        (self.root / (self.name + ".sha256")).write_bytes(sidecar)
        (self.root / (self.name + ".ready")).write_bytes(sidecar)

    def check(self, good=True, reason=None, target="v3", filename=None):
        p = subprocess.run([sys.executable, str(SCRIPT), "--directory", str(self.root),
                            "--filename", filename or self.name, "--target", target],
                           capture_output=True, text=True, timeout=8)
        if good:
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("PASS_LOCAL_SHA256_ONLY", p.stdout)
            self.assertIn("RESTORE_VERIFIED=NO", p.stdout)
        else:
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertIn("BUNDLE_ACCEPT=REJECT", p.stdout)
            if reason:
                self.assertIn(reason, p.stdout)

    def test_valid_v3(self): self.check()

    def test_valid_archive_v4_v5(self):
        for target in ("archive", "v4", "v5"):
            with self.subTest(target=target):
                old = self.name
                self.name = old.replace("v3", target, 1)
                self.make_bundle()
                self.check(target=target)
                self.name = old

    def test_missing_dump(self):
        (self.root / self.name).unlink()
        self.check(False, "FILE_UNAVAILABLE")

    def test_missing_sha(self):
        (self.root / (self.name + ".sha256")).unlink()
        self.check(False, "FILE_UNAVAILABLE")

    def test_missing_ready(self):
        (self.root / (self.name + ".ready")).unlink()
        self.check(False, "FILE_UNAVAILABLE")

    def test_corrupt_payload(self):
        (self.root / self.name).write_bytes(self.payload + b"!")
        self.check(False, "SHA256_MISMATCH")

    def test_sidecar_modified(self):
        (self.root / (self.name + ".sha256")).write_bytes(b"0" * 64 + b"  " + self.name.encode() + b"\n")
        self.check(False, "SIDECAR_MARKER_MISMATCH")

    def test_marker_modified(self):
        (self.root / (self.name + ".ready")).write_bytes(b"0" * 64 + b"  " + self.name.encode() + b"\n")
        self.check(False, "SIDECAR_MARKER_MISMATCH")

    def test_bad_sidecar_filename(self):
        incorrect = f"{hashlib.sha256(self.payload).hexdigest()}  another.dump.age\n".encode()
        for suffix in (".ready", ".sha256"):
            (self.root / (self.name + suffix)).write_bytes(incorrect)
        self.check(False, "INVALID_SIDECAR_FORMAT_OR_NAME")

    def test_staging_dump(self):
        (self.root / (self.name + ".uploading")).write_bytes(b"incomplete")
        self.check(False, "INCOMPLETE_STAGING_PRESENT")

    def test_staging_ready(self):
        (self.root / (self.name + ".ready.uploading")).write_bytes(b"incomplete")
        self.check(False, "INCOMPLETE_STAGING_PRESENT")

    def test_staging_sha(self):
        (self.root / (self.name + ".sha256.uploading")).write_bytes(b"incomplete")
        self.check(False, "INCOMPLETE_STAGING_PRESENT")

    def test_symlink_dump(self):
        (self.root / self.name).unlink()
        (self.root / self.name).symlink_to(self.root / "elsewhere")
        self.check(False, "NOT_REGULAR_FILE")

    def test_symlink_ready(self):
        (self.root / (self.name + ".ready")).unlink()
        (self.root / (self.name + ".ready")).symlink_to(self.root / (self.name + ".sha256"))
        self.check(False, "NOT_REGULAR_FILE")

    def test_target_mixup(self): self.check(False, "TARGET_MISMATCH", target="v5")

    def test_invalid_date(self):
        self.check(False, "INVALID_TIMESTAMP", filename=self.name.replace("20261014", "20261340"))

    def test_filename_traversal(self):
        self.check(False, "UNSAFE_FILENAME", filename="../" + self.name)

    def test_filename_bad_extension(self):
        self.check(False, "INVALID_FILENAME", filename=self.name + ".uploading")

    def test_empty_age(self):
        (self.root / self.name).write_bytes(b"")
        self.check(False, "EMPTY_ENCRYPTED_FILE")

    def test_oversized_sidecar(self):
        (self.root / (self.name + ".sha256")).write_bytes(b"x" * 300)
        self.check(False, "SIDECAR_TOO_LARGE")

    def test_missing_newline(self):
        (self.root / (self.name + ".sha256")).write_bytes(b"a" * 64 + b"  " + self.name.encode())
        (self.root / (self.name + ".ready")).write_bytes(b"a" * 64 + b"  " + self.name.encode())
        self.check(False, "INVALID_SIDECAR_FORMAT_OR_NAME")


if __name__ == "__main__":
    unittest.main(verbosity=1)
