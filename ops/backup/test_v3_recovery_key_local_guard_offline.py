#!/usr/bin/env python3
"""No owner key, network, DB or age crypto: mocked commands, local metadata only."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "test_v3_recovery_age_roundtrip_offline.sh"
PUBLIC = ROOT / "keys" / "v3_recovery_recipient_20261013.pub"


class OfflineLocalKeyGuardTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(dir=str(ROOT))
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        # Never mutate the checked-in script or public key during tests.
        self.fixture = self.root / "script"
        (self.fixture / "keys").mkdir(parents=True, mode=0o700)
        self.script = self.fixture / SCRIPT.name
        self.public = self.fixture / "keys" / PUBLIC.name
        shutil.copy2(SCRIPT, self.script)
        shutil.copy2(PUBLIC, self.public)
        self.mockbin = self.root / "bin"
        self.mockbin.mkdir(mode=0o700)
        mock_age = self.mockbin / "age"
        mock_age.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import sys\n"
            "args=sys.argv[1:]\n"
            "out=Path(args[args.index('-o')+1])\n"
            "out.write_bytes(Path(args[-1]).read_bytes())\n",
            encoding="utf-8",
        )
        mock_age.chmod(0o700)
        self.key = self.root / "dummy-not-real-private-key"
        self.key.write_text("SYNTHETIC_TEST_ONLY_NOT_A_KEY\n", encoding="utf-8")
        self.key.chmod(0o600)

    def run_guard(self, value=None, trace=False):
        env = os.environ.copy()
        env["PATH"] = str(self.mockbin) + os.pathsep + env.get("PATH", "")
        env.pop("RECOVERY_PRIVATE_KEY_FILE", None)
        if value is not None:
            env["RECOVERY_PRIVATE_KEY_FILE"] = str(value)
        cmd = ["bash", "-x", str(self.script)] if trace else ["bash", str(self.script)]
        return subprocess.run(
            cmd, text=True, capture_output=True, env=env, timeout=8, check=False,
        )

    def assert_rejected(self, value):
        result = self.run_guard(value)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("RECOVERY_ROUNDTRIP_OK=YES", result.stdout)
        self.assertIn("RECOVERY_TEST_ABORT=", result.stderr)

    def test_mock_roundtrip_only(self):
        result = self.run_guard(self.key)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RECOVERY_ROUNDTRIP_OK=YES", result.stdout)
        self.assertIn("RECOVERY_DATABASE_BACKUP_VERIFIED=NO", result.stdout)
        self.assertNotIn("SYNTHETIC_TEST_ONLY_NOT_A_KEY", result.stdout + result.stderr)

    def test_unset_key_path(self):
        self.assert_rejected(None)

    def test_relative_path(self):
        self.assert_rejected(self.key.name)

    def test_noncanonical_dotdot_path(self):
        self.assert_rejected(str(self.key.parent / "part" / ".." / self.key.name))

    def test_noncanonical_double_slash_path(self):
        self.assert_rejected(str(self.key).replace("/dummy-", "//dummy-"))

    def test_missing_file(self):
        self.assert_rejected(self.root / "missing-key")

    def test_empty_file(self):
        self.key.write_bytes(b"")
        self.assert_rejected(self.key)

    def test_directory_not_file(self):
        self.assert_rejected(self.root)

    def test_world_readable(self):
        self.key.chmod(0o644)
        self.assert_rejected(self.key)

    def test_group_readable(self):
        self.key.chmod(0o640)
        self.assert_rejected(self.key)

    def test_world_writable_parent(self):
        parent = self.root / "writable"
        parent.mkdir(mode=0o700)
        parent.chmod(0o777)
        child = parent / "private"
        child.write_bytes(b"dummy")
        child.chmod(0o600)
        self.assert_rejected(child)

    def test_symlink_file(self):
        link = self.root / "linked-key"
        link.symlink_to(self.key)
        self.assert_rejected(link)

    def test_symlink_parent(self):
        link = self.root / "linked-dir"
        link.symlink_to(self.root, target_is_directory=True)
        self.assert_rejected(link / self.key.name)

    def test_hardlink_file(self):
        os.link(self.key, self.root / "other-hardlink")
        self.assert_rejected(self.key)

    def test_bash_trace_does_not_echo_key_path(self):
        result = self.run_guard(self.key, trace=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(str(self.key), result.stderr)
        self.assertNotIn("SYNTHETIC_TEST_ONLY_NOT_A_KEY", result.stdout + result.stderr)

    def test_public_key_pin_mismatch(self):
        self.public.write_bytes(b"ssh-ed25519 AAAAfake boat-ai-recovery\n")
        self.assert_rejected(self.key)


if __name__ == "__main__":
    unittest.main()
