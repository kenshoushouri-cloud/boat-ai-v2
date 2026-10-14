#!/usr/bin/env python3
"""Offline contract tests for the already-approved ConoHa host read-only probe.

Runs a *copy* of the SHA-pinned script against synthetic OS files and
mocked resource commands. Never accesses ConoHa, Railway, Drive, DBs or keys.
Does not run the source probe on the host.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().with_name("v5_host_preflight_readonly.sh")
APPROVED_GIT_BLOB_SHA = "3fd4de929d07765379834fcd483d19daad52bbde"

MEM_OK = """MemTotal:        2097152 kB
MemAvailable:    1258291 kB
SwapTotal:        524288 kB
"""
OS_OK = 'ID=ubuntu\nVERSION_ID="24.04"\nNAME="EXCLUDED_SECRET_DO_NOT_PRINT"\n'

def git_blob_sha(payload: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(payload)).encode() + b"\0" + payload
    ).hexdigest()

class PreflightSafetyOffline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = SOURCE.read_bytes()
        if git_blob_sha(cls.original) != APPROVED_GIT_BLOB_SHA:
            raise AssertionError("host preflight script changed; review and re-pin first")

    def test_exact_approved_script_blob(self):
        self.assertEqual(git_blob_sha(self.original), APPROVED_GIT_BLOB_SHA)

    def test_read_only_contract_markers(self):
        source = self.original.decode()
        for required in (
            "set +x", "set -euo pipefail", "/proc/meminfo",
            "/etc/os-release", "df -Pk /", "uname -m",
            "CONOHA_PREFLIGHT_MODE=READ_ONLY",
            "V5_PRODUCTION_READINESS=NOT_ASSESSED",
            "BACKUP_RESTORE_VERIFIED=NO",
            "RAILWAY_SHUTDOWN_APPROVED=NO", "BUY=HARD_HOLD",
        ):
            with self.subTest(marker=required):
                self.assertIn(required, source)

    def test_no_network_secret_or_mutating_commands_in_pinned_source(self):
        source = "\n".join(
            line for line in self.original.decode().splitlines()[1:]
            if not line.lstrip().startswith("#")
        )
        # Exact git-blob pin is primary protection. This is a readable
        # secondary check; shell keyword matching alone is not a sandbox.
        for pattern in (
            r"\b(?:curl|wget|ssh|scp|nc|netcat|sudo|su|apt|apk|pip|rclone|"
            r"psql|pg_dump|pg_restore|rm|mv|cp|chmod|chown|systemctl|"
            r"service|crontab|env|printenv|hostname|ip|ifconfig)\s",
            r"\b(?:DATABASE_URL|PRIVATE_KEY|TOKEN|PASSWORD|OAUTH)\b",
        ):
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, source))

    def execute_fixture(
        self, *, os_release: str = OS_OK, meminfo: str = MEM_OK,
        disk_free_kib: str = "41943040", cpu: str = "2",
        arch: str = "x86_64", missing_os: bool = False
    ) -> subprocess.CompletedProcess:
        # Only the inspected script COPY is run; its absolute read paths
        # are replaced with fixture files. No live /proc or /etc is read.
        with tempfile.TemporaryDirectory(prefix="v5-pref-offline-") as t:
            root = Path(t)
            os_path = root / "os-release"
            mem_path = root / "meminfo"
            if not missing_os:
                os_path.write_text(os_release, encoding="utf-8")
            mem_path.write_text(meminfo, encoding="utf-8")
            code = self.original.decode()
            self.assertEqual(code.count("/proc/meminfo"), 4)
            self.assertEqual(code.count("/etc/os-release"), 3)
            code = code.replace("/proc/meminfo", str(mem_path))
            code = code.replace("/etc/os-release", str(os_path))
            self.assertNotIn("/proc/meminfo", code)
            self.assertNotIn("/etc/os-release", code)
            probe = root / "probe.sh"
            probe.write_text(code, encoding="utf-8")

            mockbin = root / "bin"
            mockbin.mkdir()
            for binary in ("awk", "grep"):
                resolved = shutil.which(binary)
                self.assertIsNotNone(resolved)
                (mockbin / binary).symlink_to(resolved)
            for name, output in {
                "df": "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                      + "/dev/synthetic 50000000 10 " + disk_free_kib + " 1% /\n",
                "uname": arch + "\n",
                "nproc": cpu + "\n",
            }.items():
                wrapper = mockbin / name
                wrapper.write_text(
                    "#!/bin/sh\nprintf '%b' " + "'" +
                    output.replace("'", "'\\''").replace("\n", "\\n") +
                    "'\n",
                    encoding="utf-8",
                )
                wrapper.chmod(0o700)
            environment = {
                "PATH": str(mockbin),
                "DATABASE_URL": "EXCLUDED_SECRET_DATABASE_URL",
                "OAUTH_TOKEN": "EXCLUDED_SECRET_TOKEN",
                "SSH_PRIVATE_KEY": "EXCLUDED_SECRET_PRIVATE_KEY",
            }
            result = subprocess.run(
                ["/bin/bash", str(probe)], text=True, capture_output=True,
                env=environment, timeout=8, check=False, cwd=root,
            )
            return result

    def assert_no_secrets(self, result):
        combined = result.stdout + result.stderr
        self.assertNotIn("EXCLUDED_SECRET", combined)
        self.assertNotIn("DATABASE_URL", combined)
        self.assertNotIn("OAUTH_TOKEN", combined)
        self.assertNotIn("SSH_PRIVATE_KEY", combined)
        self.assertNotIn("Filesystem", combined)
        self.assertNotIn("/dev/synthetic", combined)

    def test_ubuntu_24_04_baseline(self):
        r = self.execute_fixture()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OS_ID=ubuntu\n", r.stdout)
        self.assertIn("OS_VERSION=24.04\n", r.stdout)
        self.assertIn("CHECK_OS=EXPECTED_UBUNTU_24_04", r.stdout)
        self.assertIn("PREFLIGHT_WARNING_COUNT=0", r.stdout)
        self.assertIn("BUY=HARD_HOLD", r.stdout)
        self.assert_no_secrets(r)

    def test_different_os_warns_without_abort(self):
        r = self.execute_fixture(os_release="ID=debian\nVERSION_ID=12\n")
        self.assertEqual(r.returncode, 0)
        self.assertIn("CHECK_OS=REVIEW_NOT_UBUNTU_24_04", r.stdout)
        self.assertIn("PREFLIGHT_WARNING_COUNT=1", r.stdout)
        self.assert_no_secrets(r)

    def test_low_ram_rejected_as_warning(self):
        r = self.execute_fixture(meminfo=MEM_OK.replace("2097152", "1048576"))
        self.assertIn("CHECK_MEMORY=LOW_FOR_2GB_PLAN", r.stdout)
        self.assertIn("PREFLIGHT_WARNING_COUNT=1", r.stdout)
        self.assert_no_secrets(r)

    def test_low_available_ram_warns(self):
        r = self.execute_fixture(meminfo=MEM_OK.replace("1258291", "200000"))
        self.assertIn("CHECK_MEMORY=LOW_AVAILABLE_MEMORY", r.stdout)
        self.assert_no_secrets(r)

    def test_low_disk_warns(self):
        r = self.execute_fixture(disk_free_kib="20000000")
        self.assertIn("CHECK_DISK=REVIEW_BEFORE_RESTORE", r.stdout)
        self.assert_no_secrets(r)

    def test_low_cpu_warns(self):
        r = self.execute_fixture(cpu="1")
        self.assertIn("CHECK_CPU=REVIEW_BEFORE_MIGRATION", r.stdout)
        self.assert_no_secrets(r)

    def test_zero_swap_never_changes_settings(self):
        r = self.execute_fixture(meminfo=MEM_OK.replace("524288", "0"))
        self.assertIn("CHECK_SWAP=NOT_CONFIGURED_NO_AUTOMATIC_CHANGE", r.stdout)
        self.assert_no_secrets(r)

    def test_missing_os_metadata_fail_closed(self):
        r = self.execute_fixture(missing_os=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PREFLIGHT_ABORT=os_release_not_readable", r.stderr)
        self.assert_no_secrets(r)

    def test_nonnumeric_memory_fail_closed(self):
        r = self.execute_fixture(meminfo=MEM_OK.replace("2097152", "oops"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PREFLIGHT_ABORT=memory_total_invalid", r.stderr)
        self.assert_no_secrets(r)

    def test_command_injection_as_os_text_is_not_executed(self):
        r = self.execute_fixture(
            os_release='ID="$(printf HACKED)"\nVERSION_ID="24.04"\n'
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("HACKED", r.stdout + r.stderr)
        self.assert_no_secrets(r)

    def test_bad_architecture_fail_closed(self):
        r = self.execute_fixture(arch="unsafe invalid arch")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PREFLIGHT_ABORT=architecture_invalid", r.stderr)
        self.assert_no_secrets(r)


if __name__ == "__main__":
    unittest.main()
