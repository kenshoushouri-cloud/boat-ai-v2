#!/usr/bin/env python3
"""Pure offline tests: no cron, DB, subprocess or network operations."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from v5_writer_lock_static_check import UnsafePlan, main, validate_manifest


PREFIX = "/opt/boat-ai-v2/"


def job(name="odds", writer="run_odds_window_pg.py", phase="before_deadline"):
    return {
        "name": name,
        "phase": phase,
        "service_user": "boatv5",
        "lock_file": "/run/boat-ai-v5/jobs.lock",
        "argv": [PREFIX + "ops/conoha/v5_serial_resource_guard.sh", "--execute", "--",
                 "/usr/bin/python3", PREFIX + writer],
    }


def plan(*jobs):
    return {"schema": 1, "jobs": list(jobs)}


class StaticLockTests(unittest.TestCase):
    def test_approved_jobs_share_lock(self):
        self.assertEqual(validate_manifest(plan(job(), job("night", "run_nightly_results_pg.py", "after_race"))), 2)

    def test_bash_direct_guard_allowed(self):
        j = job()
        j["argv"].insert(0, "/bin/bash")
        self.assertEqual(validate_manifest(plan(j)), 1)

    def assert_hold(self, p):
        with self.assertRaises(UnsafePlan):
            validate_manifest(p)

    def test_missing_guard(self):
        j = job()
        j["argv"] = ["/usr/bin/python3", PREFIX + "run_odds_window_pg.py"]
        self.assert_hold(plan(j))

    def test_shell_wrapper_bypass(self):
        j = job()
        j["argv"] = ["/bin/sh", "-c", "flock -n /tmp/lock python3 writer.py"]
        self.assert_hold(plan(j))

    def test_guard_plan_mode_not_execution(self):
        j = job()
        j["argv"][1] = "--plan"
        self.assert_hold(plan(j))

    def test_wrong_lock_path(self):
        j = job()
        j["lock_file"] = "/tmp/jobs.lock"
        self.assert_hold(plan(j))

    def test_path_traversal(self):
        j = job()
        j["argv"][0] = "/opt/a/../ops/conoha/v5_serial_resource_guard.sh"
        self.assert_hold(plan(j))

    def test_legacy_pre_notification_forbidden(self):
        self.assert_hold(plan(job(writer="run_window_pipeline_pg.py")))

    def test_unapproved_final_forbidden(self):
        self.assert_hold(plan(job(writer="run_final_pg.py")))

    def test_wrong_phase(self):
        self.assert_hold(plan(job(writer="run_nightly_results_pg.py")))

    def test_background_or_unreviewed_args(self):
        j = job()
        j["argv"].append("&")
        self.assert_hold(plan(j))

    def test_root_identity(self):
        j = job()
        j["service_user"] = "root"
        self.assert_hold(plan(j))

    def test_mixed_service_users(self):
        j = job("night", "run_nightly_results_pg.py", "after_race")
        j["service_user"] = "otheruser"
        self.assert_hold(plan(job(), j))

    def test_writer_outside_repo(self):
        j = job()
        j["argv"][-1] = "/tmp/run_odds_window_pg.py"
        self.assert_hold(plan(j))

    def test_duplicate_name(self):
        self.assert_hold(plan(job(), copy.deepcopy(job())))

    def test_empty_inventory(self):
        self.assert_hold(plan())

    def test_schema_expansion(self):
        j = job()
        j["env"] = {"V5_SERIAL_LOCK_FILE": "/tmp/fake"}
        self.assert_hold(plan(j))

    def test_cli_reads_only_local_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "jobs.json"
            path.write_text(json.dumps(plan(job())), encoding="utf-8")
            self.assertEqual(main([str(path)]), 0)
            path.write_text(json.dumps(plan()), encoding="utf-8")
            self.assertEqual(main([str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
