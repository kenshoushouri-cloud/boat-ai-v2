#!/usr/bin/env python3
"""V5 migration: safely identify morning/night unit entrypoints without executing jobs.

Read-only: inspect systemctl unit metadata and repo-local shell/Python file names.
Output contains NO raw ExecStart/Environment/connection strings or secret values.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path("/opt/boat-ai-v5").resolve()
UNITS = ("boat-v5-daily@morning.service", "boat-v5-daily@night.service")
REF = re.compile(r"(?<![\w-])(?:[./\w@-]+/)?[\w@.-]+\.(?:py|sh)\b")
MODULE = re.compile(r"(?<![\w-])-m\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)")
DISALLOWED = ("secret", "password", "token", "key", "credential", "config", "env")
MAX_BYTES = 200000

def call(*args: str) -> tuple[bool, str]:
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return p.returncode == 0, p.stdout

def scripts_from(raw: str) -> list[str]:
    return sorted(set(REF.findall(raw)))

def modules_from(raw: str) -> list[str]:
    return sorted(set(MODULE.findall(raw)))

def safe_name(s: str) -> str:
    # Do not emit arbitrary metadata as if it were an executable path.
    return Path(s).name if not any(x in s.lower() for x in DISALLOWED) else "HIDDEN"

def repo_local_files(raw: str) -> list[Path]:
    files = []
    for token in scripts_from(raw):
        p = Path(token)
        if not p.is_absolute():
            p = ROOT / token.lstrip("./")
        try:
            resolved = p.resolve()
            if resolved.is_relative_to(ROOT) and resolved.is_file() and resolved.stat().st_size <= MAX_BYTES:
                files.append(resolved)
        except OSError:
            continue
    return list(dict.fromkeys(files))

def show_service(unit: str) -> None:
    ok, raw = call("systemctl", "show", unit, "--no-pager",
                   "--property=LoadState,ActiveState,UnitFileState,FragmentPath,ExecStart")
    if not ok:
        print(f"UNIT|{unit}|METADATA_UNAVAILABLE", flush=True)
        return
    fields = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
    load = fields.get("LoadState", "unknown")
    state = fields.get("ActiveState", "unknown")
    enabled = fields.get("UnitFileState", "unknown")
    fragment = safe_name(fields.get("FragmentPath", "unknown"))
    program = fields.get("ExecStart", "")
    print(f"UNIT|{unit}|load={load}|state={state}|unitfile={enabled}|fragment={fragment}", flush=True)
    print("ENTRY_FILES|" + unit + "|" +
          (",".join(map(safe_name, scripts_from(program)[:12])) or "UNRESOLVED"), flush=True)
    print("ENTRY_MODULES|" + unit + "|" +
          (",".join(modules_from(program)[:10]) or "-"), flush=True)
    if "/bin/bash" in program or "/bin/sh" in program:
        print("SHELL_WRAPPER|" + unit + "|YES", flush=True)
    for file in repo_local_files(program)[:3]:
        code = file.read_text(encoding="utf-8", errors="replace")
        nested = scripts_from(code)
        modules = modules_from(code)
        print("LOCAL_SCRIPT|" + safe_name(file.name)
              + "|CHILD_FILES=" + (",".join(map(safe_name, nested[:12])) or "-")
              + "|CHILD_MODULES=" + (",".join(modules[:10]) or "-"),
              flush=True)
    # Explicitly avoid displaying raw unit commands, environment or file content.
    if not program:
        print("ENTRY_DIAGNOSTIC|" + unit + "|EMPTY_EXECSTART", flush=True)
    elif not scripts_from(program) and not modules_from(program):
        print("ENTRY_DIAGNOSTIC|" + unit + "|SHELL_OR_WRAPPER_NEEDS_MANUAL_REVIEW", flush=True)

def show_daily_wrapper() -> None:
    # Local entrypoint discovered from the 2026-10-20 ConoHa handoff.
    # Do not run the script, print its raw lines, or import it.
    p = Path("/opt/boat-ai-collector/daily_v5_safe.sh")
    if not p.is_file():
        print("DAILY_WRAPPER|NOT_FOUND_AT_EXPECTED_PATH", flush=True)
        return
    try:
        if p.stat().st_size > 250000:
            print("DAILY_WRAPPER|SKIP_OVERSIZED", flush=True)
            return
        body = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        print("DAILY_WRAPPER|READ_FAILED", flush=True)
        return
    names = sorted(set(safe_name(x) for x in scripts_from(body)))
    mods = modules_from(body)
    print("DAILY_WRAPPER|daily_v5_safe.sh|read_only=true", flush=True)
    print("WRAPPER_REFERENCED_FILES=" + (",".join(names[:20]) or "-"), flush=True)
    print("WRAPPER_PYTHON_MODULES=" + (",".join(mods[:12]) or "-"), flush=True)
    for marker in ("repair_month_all_pg.py", "save_k_day_results_pg.py",
                   "v21_realtime_collector_pg.py", "v21_realtime_collector_pg_safe.py",
                   "run_window_pipeline_pg.py", "run_window_refresh_pg.py"):
        print("WRAPPER_REFERENCE|" + marker + "|" +
              ("TEXT_MATCH" if marker in body else "NOT_FOUND_STATICALLY"), flush=True)
    print("WRAPPER_CLASSIFICATION_IS_STATIC_NOT_RUNTIME_CERTIFICATION", flush=True)

def main() -> None:
    print("MODE=V5_DAILY_ENTRYPOINTS_READ_ONLY", flush=True)
    for unit in UNITS:
        show_service(unit)
    show_daily_wrapper()
    print("NO_SERVICES_STARTED_NO_DB_ACCESSED_NO_SECRETS_PRINTED", flush=True)
    print("V5_DAILY_ENTRYPOINTS_READONLY_COMPLETE", flush=True)

if __name__ == "__main__":
    main()
