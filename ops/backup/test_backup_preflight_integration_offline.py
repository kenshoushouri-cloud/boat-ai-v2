#!/usr/bin/env python3
"""Offline integration tests: the REAL Bash exporter calls REAL binding module.

Copies source scripts into a scratch directory and patches only Drive folder
hashes for synthetic IDs. External tools are replaced by failing mocks.
No credentials, service activation, network, real Drive folders, or DB writes.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parent
TARGETS = ("v3", "archive", "v4", "v5")


class TestPreflightIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_obj = tempfile.TemporaryDirectory(prefix="boat-ai-integration-")
        cls.root = Path(cls.temp_obj.name)
        cls.work = cls.root / "work"
        cls.bin_dir = cls.root / "bin"
        cls.work.mkdir()
        cls.bin_dir.mkdir()
        (cls.work / "keys").mkdir()
        for name in ("railway_pg_to_drive_stream.sh", "backup_target_binding.py"):
            shutil.copyfile(SRC / name, cls.work / name)
        shutil.copyfile(
            SRC / "keys/v3_recovery_recipient_20261013.pub",
            cls.work / "keys/v3_recovery_recipient_20261013.pub",
        )
        spec = importlib.util.spec_from_file_location("offline_target_manifest", SRC / "backup_target_binding.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.services = {k: v["service"] for k, v in module.TARGETS.items()}
        cls.folders = {k: f"fakePrivateFolder_{k}_20261014" for k in TARGETS}
        manifest = (cls.work / "backup_target_binding.py").read_text(encoding="utf-8")
        for target in TARGETS:
            old = module.TARGETS[target]["folder_sha256"]
            replacement = sha256(cls.folders[target].encode()).hexdigest()
            if manifest.count(old) != 1:
                raise AssertionError("fixture_replacement_must_be_unique")
            manifest = manifest.replace(old, replacement)
        (cls.work / "backup_target_binding.py").write_text(manifest, encoding="utf-8")
        cls.pub = (cls.work / "keys/v3_recovery_recipient_20261013.pub").read_text().strip()
        cls.pubhash = sha256(cls.pub.encode()).hexdigest()
        for cmd in ("psql", "pg_dump", "rclone", "age"):
            stub = cls.bin_dir / cmd
            stub.write_text('''#!/usr/bin/env bash
set -eu
name="${0##*/}"
if [[ "${1:-}" == --version && ("$name" == pg_dump || "$name" == psql) ]]; then
  printf '%s (PostgreSQL) 18.1\\n' "$name"
  exit 0
fi
printf '%s:%s\\n' "$name" "${1:-}" >> "$OFFLINE_MOCK_CALL_LOG"
printf 'MOCKED_EXTERNAL_CALL_REJECTED\\n' >&2
exit 97
''', encoding="utf-8")
            stub.chmod(0o700)
        cls.exporter = cls.work / "railway_pg_to_drive_stream.sh"
        cls.env_base = {
            "PATH": f"{cls.bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "HOME": str(cls.root),
            "SOURCE_DATABASE_URL": "postgresql://fakeuser:fakepassword@db.invalid:46406/fake_db?sslmode=require",
            "SOURCE_EXPECTED_HOST": "db.invalid",
            "SOURCE_EXPECTED_PORT": "46406",
            "SOURCE_EXPECTED_DATABASE": "fake_db",
            "AGE_RECIPIENT": cls.pub,
            "AGE_EXPECTED_RECIPIENT_SHA256": cls.pubhash,
            "BACKUP_CONNECT_APPROVED": "YES",  # Fake lab-only flags, not real authority.
            "BACKUP_NETWORK_COST_APPROVED": "YES",
            "BACKUP_EXECUTE_APPROVED": "YES",
            "BACKUP_RESTORE_KEY_VERIFIED": "YES",
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_obj.cleanup()

    def run_exporter(self, target="v3", mode="preflight", *, changes=None):
        env = dict(self.env_base)
        env.update({
            "BACKUP_TARGET": target,
            "BACKUP_MODE": mode,
            "SOURCE_EXPECTED_SERVICE_ID": self.services[target],
            "DRIVE_EXPECTED_FOLDER_ID": self.folders[target],
        })
        env.update(changes or {})
        log = self.root / "tool_calls.log"
        log.unlink(missing_ok=True)
        env["OFFLINE_MOCK_CALL_LOG"] = str(log)
        p = subprocess.run(["bash", str(self.exporter)], cwd=self.work,
                           env=env, capture_output=True, text=True,
                           timeout=8, check=False)
        # Tools can ONLY be stubs; no real DB/Drive invocation is possible here.
        calls = log.read_text().splitlines() if log.exists() else []
        return p, calls

    def check_rejected(self, target, fragment, *, mode="preflight", changes=None):
        p, calls = self.run_exporter(target, mode, changes=changes)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(fragment, p.stderr + p.stdout)
        self.assertEqual(calls, [], f"external tool attempted before guard: {calls}")

    def test_plan_default_without_any_real_credentials(self):
        log = self.root / "plan_calls.log"
        log.unlink(missing_ok=True)
        p = subprocess.run(["bash", str(self.exporter)],
                           env={"PATH": self.env_base["PATH"], "OFFLINE_MOCK_CALL_LOG": str(log)},
                           capture_output=True, text=True, timeout=8)
        self.assertEqual(p.returncode, 0)
        self.assertIn("BACKUP_CONNECTION=NOT_ATTEMPTED", p.stdout)
        self.assertFalse(log.exists())

    def test_validate_mode_defers_service_and_folder_binding(self):
        p, calls = self.run_exporter("v3", "validate", changes={
            "SOURCE_EXPECTED_SERVICE_ID": "invalid", "DRIVE_EXPECTED_FOLDER_ID": "fakeInvalidFolder0000"})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("BACKUP_TARGET_BINDING=DEFERRED_UNTIL_ONLINE_MODE", p.stdout)
        self.assertEqual(calls, [])

    def test_changed_v3_pub_and_hash_rejected_before_mock_tools(self):
        bogus = "age1" + "q" * 42
        self.check_rejected("v3", "v3_recipient_not_preapproved", changes={
            "AGE_RECIPIENT": bogus,
            "AGE_EXPECTED_RECIPIENT_SHA256": sha256(bogus.encode()).hexdigest(),
        })

    def test_approved_restore_key_flag_is_only_lab_mock(self):
        self.check_rejected("v3", "recovery_key_test_not_confirmed", mode="execute",
                            changes={"BACKUP_RESTORE_KEY_VERIFIED": "NO"})


def make_case(target: str, kind: str):
    def case(self: TestPreflightIntegration):
        if kind == "valid_preflight_reaches_mock_rclone_only":
            p, calls = self.run_exporter(target)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn(f"BACKUP_BINDING=PASS_STATIC target:{target}", p.stdout)
            self.assertEqual(calls, ["rclone:listremotes"])
            self.assertNotIn("BACKUP_PREFLIGHT_OK", p.stdout)
        elif kind == "incorrect_service_fails_before_external_tools":
            self.check_rejected(target, "source_service_mismatch", changes={
                "SOURCE_EXPECTED_SERVICE_ID": "00000000-0000-4000-8000-000000000000"})
        elif kind == "other_db_service_fails_before_external_tools":
            other = next(n for n in TARGETS if n != target)
            self.check_rejected(target, "source_service_mismatch", changes={
                "SOURCE_EXPECTED_SERVICE_ID": self.services[other]})
        elif kind == "other_folder_fails_before_external_tools":
            other = next(n for n in TARGETS if n != target)
            self.check_rejected(target, "drive_folder_pin_mismatch", changes={
                "DRIVE_EXPECTED_FOLDER_ID": self.folders[other]})
        elif kind == "cost_flag_required_before_external_tools":
            self.check_rejected(target, "network_cost_not_approved", changes={
                "BACKUP_NETWORK_COST_APPROVED": "NO"})
        elif kind == "execute_needs_target_consent_before_external_tools":
            self.check_rejected(target, "target_specific_approval_required",
                                mode="execute", changes={
                                    "BACKUP_EXECUTE_TARGET_APPROVED": "NO"})
        elif kind == "execute_approved_still_protected":
            p, calls = self.run_exporter(target, mode="execute", changes={
                "BACKUP_EXECUTE_TARGET_APPROVED": f"YES_SINGLE_{target.upper()}_ENCRYPTED_SNAPSHOT"})
            self.assertNotEqual(p.returncode, 0)
            if target == "v3":
                self.assertEqual(calls, ["rclone:listremotes"])
                self.assertIn("BACKUP_BINDING=PASS_STATIC", p.stdout)
            else:
                self.assertEqual(calls, [])
                self.assertIn("recovery_recipient_not_pinned_for_target", p.stderr)
        else:
            raise AssertionError(kind)
    return case


for _target in TARGETS:
    for _kind in (
        "valid_preflight_reaches_mock_rclone_only",
        "incorrect_service_fails_before_external_tools",
        "other_db_service_fails_before_external_tools",
        "other_folder_fails_before_external_tools",
        "cost_flag_required_before_external_tools",
        "execute_needs_target_consent_before_external_tools",
        "execute_approved_still_protected",
    ):
        setattr(TestPreflightIntegration, f"test_{_target}_{_kind}", make_case(_target, _kind))


if __name__ == "__main__":
    unittest.main(verbosity=1)
