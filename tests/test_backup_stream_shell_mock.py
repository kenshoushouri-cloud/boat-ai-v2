"""Offline tests for backup shell control flow; fake age does NOT encrypt.

Run from repo root: python3 -m unittest tests.test_backup_stream_shell_mock
These tests never open Railway/Drive connections and create only temp files.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "ops/backup/railway_pg_to_drive_stream.sh"
STUB = r'''#!/usr/bin/env python3
import hashlib, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
root = pathlib.Path(os.environ["MOCK_REMOTE_DIR"])
fault = os.environ.get("MOCK_FAULT", "")
if name == "pg_dump":
    if "--version" in args:
        print("pg_dump (PostgreSQL) 18.6")
    elif fault == "dump":
        sys.exit(8)
    else:
        sys.stdout.buffer.write(b"offline fake PG dump" * 100)
elif name == "psql":
    if "--version" in args:
        print("psql (PostgreSQL) 18.6")
    else:
        print(("wrong_db" if fault == "database" else "railway") + "|180006")
elif name == "age":
    # The marker is plain text: intentionally NOT a cryptographic test.
    sys.stdout.buffer.write(b"NOT_ENCRYPTED|" + sys.stdin.buffer.read())
elif name == "rclone":
    command = args[0]
    if command == "listremotes":
        print("boat-drive-v3:\nboat-drive-v4:\nboat-drive-v5:\nboat-drive-archive:")
    elif command == "config":
        print("[boat-drive-v3]\ntype=drive\nroot_folder_id="
              + ("wrong_folder" if fault == "folder" else os.environ["DRIVE_EXPECTED_FOLDER_ID"])
              + "\nclient_id=11111-abcd.apps.googleusercontent.com\nscope=drive")
    elif command == "lsf":
        if "--files-only" in args:
            for p in root.iterdir(): print(p.name)
    elif command == "rcat":
        path = root / args[1].split(":",1)[1]
        data = sys.stdin.buffer.read()
        if fault == "upload":
            path.write_bytes(data[:10])
            sys.exit(9)
        path.write_bytes(data)
    elif command == "md5sum":
        file = root / args[1].split(":",1)[1]
        value = hashlib.md5(file.read_bytes()).hexdigest()
        print(("0"*32 if fault == "checksum" else value) + "  " + file.name)
    elif command == "moveto":
        if fault == "promotion": sys.exit(10)
        (root / args[1].split(":",1)[1]).rename(root / args[2].split(":",1)[1])
    else:
        sys.exit(11)
'''


class BackupShellMockTest(unittest.TestCase):
    def execute(self, fault="", target="v3", mode="preflight", extra=None):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            bins = base / "bin"
            bins.mkdir()
            remote = base / "remote"
            remote.mkdir()
            for binary in ("pg_dump", "psql", "age", "rclone"):
                file = bins / binary
                file.write_text(STUB)
                file.chmod(0o700)
            recipient = "age1offlineplaceholdernotarealpublickey123"
            secret = "MOCK_DO_NOT_PRINT_PASSWORD_19"
            env = dict(os.environ)
            env.update({
                "PATH": str(bins) + os.pathsep + os.environ["PATH"],
                "MOCK_REMOTE_DIR": str(remote),
                "MOCK_FAULT": fault,
                "BACKUP_TARGET": target,
                "BACKUP_MODE": mode,
                "SOURCE_DATABASE_URL": "postgresql://postgres:" + secret + "@v3.internal:5432/railway",
                "SOURCE_EXPECTED_HOST": "v3.internal",
                "SOURCE_EXPECTED_DATABASE": "railway",
                "DRIVE_EXPECTED_FOLDER_ID": "folderABC1234567890",
                "AGE_RECIPIENT": recipient,
                "AGE_EXPECTED_RECIPIENT_SHA256": hashlib.sha256(recipient.encode()).hexdigest(),
            })
            env.update(extra or {})
            completed = subprocess.run(["bash", str(SCRIPT)], env=env,
                                       capture_output=True, text=True, timeout=90)
            output = completed.stdout + completed.stderr
            self.assertNotIn(secret, output)
            saved = list(remote.glob("*.dump.age"))
            if completed.returncode == 0 and mode == "execute":
                self.assertEqual(len(saved), 1)
                checksum = remote / (saved[0].name + ".sha256")
                self.assertEqual(checksum.read_text().split()[0],
                                 hashlib.sha256(saved[0].read_bytes()).hexdigest())
                self.assertIn("RESTORE_VERIFIED=NO", output)
            return completed.returncode, output, len(saved)

    def test_four_routes_are_no_write_preflight(self):
        for target in ("v3", "v4", "v5", "archive"):
            with self.subTest(target=target):
                code, out, count = self.execute(target=target)
                self.assertEqual(code, 0, out)
                self.assertIn("BACKUP_TRANSFER=NOT_STARTED", out)
                self.assertEqual(count, 0)

    def test_refuse_execute_without_approval(self):
        code, out, _ = self.execute(mode="execute")
        self.assertNotEqual(code, 0)
        self.assertIn("execution_not_approved", out)

    def test_mismatched_db_and_folder_rejected(self):
        for fault, expected in (("database", "source_database_name_mismatch"),
                                ("folder", "drive_root_folder_mismatch")):
            with self.subTest(fault=fault):
                code, out, count = self.execute(fault=fault)
                self.assertNotEqual(code, 0)
                self.assertIn(expected, out)
                self.assertEqual(count, 0)

    def test_failed_stream_never_promoted(self):
        for fault in ("dump", "upload", "checksum", "promotion"):
            with self.subTest(fault=fault):
                code, out, count = self.execute(
                    fault=fault, mode="execute", extra={"BACKUP_EXECUTE_APPROVED": "YES"})
                self.assertNotEqual(code, 0)
                self.assertEqual(count, 0, out)

    def test_successful_mock_pipeline_still_not_restore_verified(self):
        code, out, count = self.execute(
            mode="execute", extra={"BACKUP_EXECUTE_APPROVED": "YES"})
        self.assertEqual(code, 0, out)
        self.assertEqual(count, 1)
        self.assertIn("RESTORE_VERIFIED=NO", out)


if __name__ == "__main__":
    unittest.main()
