#!/usr/bin/env python3
"""Offline GitHub Actions CMS archive ZIP verifier (read-only, stdlib only).

Verifies a locally stored ZIP container against GitHub's observed artifact
size and SHA-256. It never extracts/decrypts ZIPs or connects to any service.
A passing ZIP hash is not proof of CMS key availability or PG restorability.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
import unittest

# GitHub Actions metadata read 2026-10-14; not a live metadata query.
# Format: run_id -> (artifact name, exact GitHub ZIP bytes, ZIP SHA-256).
ARTIFACTS = {
    36796803697: (
        "boat-ai-pre-hobby-20261001", 301949989,
        "04ed2d614ac5808a555a84a55547a87e5984dbf68423ae5d70df48dbbc0113e4",
    ),
    36810769041: (
        "boat-ai-pre-hobby-restorable-20261001-v2", 302572594,
        "a2676ca0beb24853b7076088140641ca099c1adc92982c3dcf5f176f3003ea3a",
    ),
    36811231115: (
        "boat-ai-pre-hobby-restorable-20261001-v2", 302612349,
        "4f9f007e0e6ed6dce77a456c2741242f8aa5574c2616383717c622bb5fae834f",
    ),
    36812386066: (
        "boat-ai-pre-hobby-restorable-20261001-v3-parity-36812386066", 302656753,
        "e9e2f99e8503529430d0e9f9e58604d2b4abee2db2185ffd190c8de88a4ba42c",
    ),
}


class Rejected(Exception):
    pass


def verify_local_zip(directory: Path, filename: str, run_id: int) -> int:
    """Hash local ZIP without following symlinks or reading its contents into RAM."""
    if run_id not in ARTIFACTS:
        raise Rejected("UNKNOWN_RUN_ID")
    name, expected_size, expected_digest = ARTIFACTS[run_id]
    # Run-scoped suffix disambiguates the two distinct v2 artifacts.
    permitted = (f"{name}.zip", f"{name}-run-{run_id}.zip")
    if (not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", filename)
            or filename not in permitted):
        raise Rejected("FILENAME_OR_RUN_ID_MISMATCH")

    dir_fd = None
    file_fd = None
    try:
        dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        dstat = os.fstat(dir_fd)
        if not stat.S_ISDIR(dstat.st_mode):
            raise Rejected("DIRECTORY_NOT_REAL")
        file_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                          dir_fd=dir_fd)
        fst = os.fstat(file_fd)
        if not stat.S_ISREG(fst.st_mode) or fst.st_nlink != 1:
            raise Rejected("FILE_NOT_SINGLE_REGULAR_FILE")
        if fst.st_size != expected_size:
            raise Rejected("ZIP_SIZE_MISMATCH")
        sha = hashlib.sha256()
        with os.fdopen(file_fd, "rb") as f:
            file_fd = None
            for block in iter(lambda: f.read(1024 * 1024), b""):
                sha.update(block)
            end = os.fstat(f.fileno())
            if (fst.st_dev, fst.st_ino, fst.st_size, fst.st_mtime_ns) != (
                    end.st_dev, end.st_ino, end.st_size, end.st_mtime_ns):
                raise Rejected("ZIP_CHANGED_DURING_READ")
        if sha.hexdigest() != expected_digest:
            raise Rejected("ZIP_SHA256_MISMATCH")
        return fst.st_size
    except OSError as exc:
        raise Rejected("LOCAL_FILE_UNAVAILABLE_OR_UNSAFE") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if dir_fd is not None:
            os.close(dir_fd)


class OfflineFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cms-zip-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = b"SYNTHETIC_NO_REAL_ARCHIVE\n" * 20
        self.run_id = 36810769041
        self.name = ARTIFACTS[self.run_id][0] + f"-run-{self.run_id}.zip"
        self.original = ARTIFACTS[self.run_id]
        ARTIFACTS[self.run_id] = (
            self.original[0], len(self.payload), hashlib.sha256(self.payload).hexdigest()
        )
        self.addCleanup(lambda: ARTIFACTS.__setitem__(self.run_id, self.original))
        (self.root / self.name).write_bytes(self.payload)

    def assert_rejected(self, reason: str, **overrides):
        args = {"directory": self.root, "filename": self.name, "run_id": self.run_id}
        args.update(overrides)
        with self.assertRaisesRegex(Rejected, reason):
            verify_local_zip(**args)

    def test_valid_synthetic_fixture(self):
        self.assertEqual(verify_local_zip(self.root, self.name, self.run_id), len(self.payload))

    def test_original_name_allowed_if_run_explicit(self):
        original_name = ARTIFACTS[self.run_id][0] + ".zip"
        (self.root / self.name).rename(self.root / original_name)
        self.assertEqual(verify_local_zip(self.root, original_name, self.run_id), len(self.payload))

    def test_unknown_run_rejected(self):
        self.assert_rejected("UNKNOWN_RUN_ID", run_id=1)

    def test_cross_run_mismatch_rejected(self):
        self.assert_rejected("FILENAME_OR_RUN_ID_MISMATCH", run_id=36811231115)

    def test_other_filename_rejected(self):
        self.assert_rejected("FILENAME_OR_RUN_ID_MISMATCH", filename="another.zip")

    def test_path_traversal_rejected(self):
        self.assert_rejected("FILENAME_OR_RUN_ID_MISMATCH", filename="../" + self.name)

    def test_empty_payload_rejected(self):
        (self.root / self.name).write_bytes(b"")
        self.assert_rejected("ZIP_SIZE_MISMATCH")

    def test_tampered_same_size_rejected(self):
        (self.root / self.name).write_bytes(b"X" + self.payload[1:])
        self.assert_rejected("ZIP_SHA256_MISMATCH")

    def test_missing_file_rejected(self):
        (self.root / self.name).unlink()
        self.assert_rejected("LOCAL_FILE_UNAVAILABLE_OR_UNSAFE")

    def test_symlink_zip_rejected(self):
        (self.root / self.name).unlink()
        (self.root / "other.zip").write_bytes(self.payload)
        (self.root / self.name).symlink_to(self.root / "other.zip")
        self.assert_rejected("LOCAL_FILE_UNAVAILABLE_OR_UNSAFE")

    def test_symlink_directory_rejected(self):
        alias = self.root.parent / (self.root.name + "-alias")
        alias.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(alias.unlink)
        self.assert_rejected("LOCAL_FILE_UNAVAILABLE_OR_UNSAFE", directory=alias)

    def test_hardlink_zip_rejected(self):
        os.link(self.root / self.name, self.root / "second.zip")
        self.assert_rejected("FILE_NOT_SINGLE_REGULAR_FILE")

    def test_directory_instead_of_zip_rejected(self):
        (self.root / self.name).unlink()
        (self.root / self.name).mkdir()
        self.assert_rejected("FILE_NOT_SINGLE_REGULAR_FILE")

    def test_four_distinct_artifact_digests(self):
        self.assertEqual(len(ARTIFACTS), 4)
        self.assertEqual(len(set(x[2] for x in ARTIFACTS.values())), 4)
        self.assertNotEqual(ARTIFACTS[36810769041][1], ARTIFACTS[36811231115][1])


def main():
    parser = argparse.ArgumentParser(description="Local ZIP SHA-256 verification, no decryption or network")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--filename")
    parser.add_argument("--run-id", type=int)
    args = parser.parse_args()
    if args.selftest:
        # Disallow confusion between synthetic tests and real ZIP acceptance.
        return 0 if unittest.main(argv=["offline-fixtures"], exit=False).result.wasSuccessful() else 1
    if args.directory is None or args.filename is None or args.run_id is None:
        parser.error("--directory, --filename, --run-id required for local ZIP acceptance")
    try:
        size = verify_local_zip(args.directory, args.filename, args.run_id)
    except Rejected as exc:
        print(f"CMS_ZIP_ACCEPT=REJECT reason:{exc}")
        print("CMS_DECRYPT_VERIFIED=NO RESTORE_VERIFIED=NO DRIVE_COPY_VERIFIED=NO BUY=HARD_HOLD")
        return 2
    print("CMS_ZIP_ACCEPT=PASS_LOCAL_SHA256_ONLY")
    print(f"RUN_ID={args.run_id} ZIP_BYTES={size}")
    print("CMS_DECRYPT_VERIFIED=NO RESTORE_VERIFIED=NO DRIVE_COPY_VERIFIED=NO BUY=HARD_HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
