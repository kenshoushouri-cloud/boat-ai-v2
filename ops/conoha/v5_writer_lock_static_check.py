#!/usr/bin/env python3
"""Offline, fail-closed review of *declared* future V5 writer job commands.

Input is a manually prepared JSON inventory, NOT a live cron discovery.
No scheduler, DB, network, subprocess, secrets, or service side effects.
A PASS is only a static syntax check; inventory completeness, wrapper content,
actual cron settings, file ownership and process descendants need separate audit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

GUARD = "v5_serial_resource_guard.sh"
LOCK = "/run/boat-ai-v5/jobs.lock"
# Only candidates from 2026-10-14 writer/cron static audit. Legacy PRE/FINAL
# notification pipelines are deliberately not an allowed V5 job target.
WRITER_PHASE = {
    "run_daily_data_prepare_pg.py": "before_deadline",
    "run_odds_window_pg.py": "before_deadline",
    "run_window_refresh_pg.py": "before_deadline",
    "run_nightly_results_pg.py": "after_race",
    "save_k_day_results_pg.py": "after_race",
    "collect_exhibition_st_forward_shadow_pg.py": "research",
}


class UnsafePlan(ValueError):
    pass


def is_absolute_clean_path(value: str) -> bool:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        return False
    parts = value.split("/")
    return all(part not in (".", "..", "") for part in parts[1:])


def validate_manifest(doc: object) -> int:
    """Return number of checked declarations; raise on any bypass or ambiguity."""
    if not isinstance(doc, dict) or set(doc) != {"schema", "jobs"} or doc["schema"] != 1:
        raise UnsafePlan("schema_mismatch")
    jobs = doc["jobs"]
    if not isinstance(jobs, list) or not jobs:
        raise UnsafePlan("empty_inventory_not_audit")
    if len(jobs) > 100:
        raise UnsafePlan("too_many_jobs")
    names: set[str] = set()
    users: set[str] = set()
    for idx, job in enumerate(jobs):
        tag = f"job[{idx}]"
        if not isinstance(job, dict) or set(job) != {"name", "phase", "service_user", "lock_file", "argv"}:
            raise UnsafePlan(f"{tag}:job_schema_mismatch")
        name, phase, user, lock, argv = (job[k] for k in ("name", "phase", "service_user", "lock_file", "argv"))
        if not isinstance(name, str) or not name or name in names:
            raise UnsafePlan(f"{tag}:duplicate_or_invalid_name")
        names.add(name)
        users.add(user)
        if len(users) != 1:
            raise UnsafePlan(f"{tag}:mixed_service_users")
        if not isinstance(user, str) or not user or user == "root" or not user.replace("-", "").replace("_", "").isalnum():
            raise UnsafePlan(f"{tag}:dedicated_unprivileged_user_required")
        if lock != LOCK:
            raise UnsafePlan(f"{tag}:common_lock_not_proven")
        if not isinstance(argv, list) or not all(isinstance(s, str) and s for s in argv):
            raise UnsafePlan(f"{tag}:argv_must_be_literal_strings")
        # Exact positional argv; no shell -c, env, pipe, eval, interpolation,
        # background launch, or unreviewed flags. The guard holds its lock
        # through its foreground child and returns the child's status.
        offset = 0
        if len(argv) == 6 and argv[0] in ("/bin/bash", "/usr/bin/bash"):
            offset = 1
        if len(argv) != offset + 5:
            raise UnsafePlan(f"{tag}:unguarded_or_dynamic_command")
        wrapper, execute, delimiter, interpreter, script = argv[offset:]
        if (not is_absolute_clean_path(wrapper) or
                not wrapper.endswith("/ops/conoha/" + GUARD) or
                execute != "--execute" or delimiter != "--" or
                interpreter not in ("/usr/bin/python3", "/bin/python3") or
                not is_absolute_clean_path(script)):
            raise UnsafePlan(f"{tag}:guard_prefix_or_runner_bypass")
        repo_root = wrapper[: -len("ops/conoha/" + GUARD)]
        if not script.startswith(repo_root) or script == repo_root:
            raise UnsafePlan(f"{tag}:writer_outside_reviewed_repo")
        filename = script.rsplit("/", 1)[-1]
        if filename not in WRITER_PHASE:
            raise UnsafePlan(f"{tag}:unknown_or_forbidden_writer")
        if phase != WRITER_PHASE[filename]:
            raise UnsafePlan(f"{tag}:writer_phase_mismatch")
    return len(jobs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V5 declared writer lock check; offline only")
    parser.add_argument("manifest", type=Path, help="Local JSON job inventory; never executes it")
    args = parser.parse_args(argv)
    try:
        # Avoid unexpectedly large files or symlinked manifests.
        if args.manifest.is_symlink() or args.manifest.stat().st_size > 65536:
            raise UnsafePlan("unsafe_manifest_file")
        doc = json.loads(args.manifest.read_text(encoding="utf-8"))
        count = validate_manifest(doc)
    except (UnsafePlan, OSError, UnicodeError, ValueError, TypeError) as exc:
        print(f"V5_WRITER_LOCK_STATIC=HOLD reason={exc}")
        return 2
    print(f"V5_WRITER_LOCK_STATIC=DECLARED_COMMANDS_PASS count={count}")
    print("PRODUCTION_READINESS=NOT_ASSESSED inventory_completeness=NOT_VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
