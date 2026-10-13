#!/usr/bin/env python3
"""Pure-stdlib 4DB target/Drive/recipient binding regression tests; no network."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backup_target_binding import TARGETS, BindingError, validate_binding


class TestBindings(unittest.TestCase):
    def setUp(self):
        # Synthetic folders only. Never commit users' real private Drive IDs.
        self.folders = {name: "fakePrivateFolder_" + name for name in TARGETS}
        self.synthetic = {
            name: {
                **info,
                "folder_sha256": sha256(self.folders[name].encode()).hexdigest(),
                "recipient_sha256": "a" * 64 if name == "v3" else None,
            }
            for name, info in TARGETS.items()
        }
        self.patch = patch.dict(TARGETS, self.synthetic, clear=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def args(self, name, mode="validate"):
        return dict(target=name, mode=mode,
                    service_id=TARGETS[name]["service"],
                    remote=TARGETS[name]["remote"],
                    folder_id=self.folders[name],
                    recipient_hash="a" * 64, target_approval="")

    def require_error(self, expected, args):
        with self.assertRaisesRegex(BindingError, expected):
            validate_binding(**args)

    def test_no_extra_targets(self):
        self.assertEqual(set(TARGETS), {"v3", "archive", "v4", "v5"})

    def test_unknown_target(self):
        args = self.args("v3")
        self.require_error("unknown_target", {**args, "target": "other"})

    def test_invalid_mode(self):
        args = self.args("v3")
        self.require_error("invalid_mode", {**args, "mode": "unknown"})

    def test_live_ownership_not_asserted(self):
        # This helper is static only; DB identity and OAuth ownership require
        # authenticated live verification, in a separately approved stage.
        module = Path(__file__).with_name("backup_target_binding.py").read_text()
        self.assertIn("BACKUP_BINDING_LIVE_DB_IDENTITY=NOT_VERIFIED", module)
        self.assertIn("BACKUP_BINDING_DRIVE_OWNER=NOT_VERIFIED", module)
        for banned in ["psycopg", "requests.", "urllib.request", "subprocess.run("]:
            self.assertNotIn(banned, module)


def make_case(target, kind):
    def fn(self):
        args = self.args(target)
        if kind == "static_valid":
            validate_binding(**args)
        elif kind == "wrong_service":
            self.require_error("source_service_mismatch", {**args, "service_id": "00000000-0000-4000-8000-000000000000"})
        elif kind == "wrong_remote":
            others = [TARGETS[n]["remote"] for n in TARGETS if n != target]
            self.require_error("drive_remote_mismatch", {**args, "remote": others[0]})
        elif kind == "wrong_folder":
            others = [self.folders[n] for n in TARGETS if n != target]
            self.require_error("drive_folder_pin_mismatch", {**args, "folder_id": others[0]})
        elif kind == "missing_target_approval":
            self.require_error("target_specific_approval_required", {**args, "mode": "execute"})
        elif kind == "approved_execute":
            args["mode"] = "execute"
            args["target_approval"] = f"YES_SINGLE_{target.upper()}_ENCRYPTED_SNAPSHOT"
            if target == "v3":
                validate_binding(**args)
            else:
                self.require_error("recovery_recipient_not_pinned_for_target", args)
        else:
            raise AssertionError(kind)
    return fn


for name in ("v3", "archive", "v4", "v5"):
    for kind in ("static_valid", "wrong_service", "wrong_remote", "wrong_folder", "missing_target_approval", "approved_execute"):
        setattr(TestBindings, f"test_{name}_{kind}", make_case(name, kind))


def test_wrong_v3_recipient(self):
    args = self.args("v3")
    self.require_error("recovery_recipient_pin_mismatch", {**args, "recipient_hash": "b" * 64})


setattr(TestBindings, "test_v3_wrong_recipient", test_wrong_v3_recipient)

if __name__ == "__main__":
    unittest.main(verbosity=1)
