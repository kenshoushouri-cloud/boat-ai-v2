#!/usr/bin/env python3
"""Read-only live process/SQL reference inventory before V5 physical migration.

No DB connection, HTTP requests, Git changes, unit mutations, or secret outputs.
Classifications are a conservative static hint, not proof of all write paths.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path("/opt/boat-ai-v5")
TARGETS = (
    "v2_races", "v2_race_entries", "v2_results", "v2_result_entries",
    "v2_realtime_exhibition_snapshots", "v2_realtime_odds_snapshots",
    "v2_realtime_weather_snapshots", "v2_realtime_race_condition_snapshots",
    "v2_realtime_racer_condition_snapshots", "v2_racer_course_stats_snapshots",
    "v2_v24_motor2_forward_shadow",
)
TARGET_PATTERN = re.compile(r"\b(" + "|".join(map(re.escape, TARGETS)) + r")\b", re.I)
WRITE_SQL = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE\s+INTO|"
    r"TRUNCATE(?:\s+TABLE)?|ALTER\s+TABLE)\s+(?:public\.)?(v2_[a-z0-9_]+)\b",
    re.I,
)
UPSERT = re.compile(
    r"\bupsert_rows\s*\(\s*['\"](v2_[a-z0-9_]+)['\"]", re.I
)
MATCH_MODULE = re.compile(r"(?:-m\s+([a-zA-Z0-9_.]+)|(/[a-zA-Z0-9_./-]+\.py))")
VALID_SUFFIX = {".py", ".sh", ".sql", ".service", ".timer"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache",
             ".pytest_cache", "node_modules", "archive", "backups"}
MAX_KB = 500

def systemctl(*args: str) -> str:
    try:
        p = subprocess.run(
            ["systemctl", *args], capture_output=True, text=True, timeout=7,
            check=False
        )
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""

def live_units():
    rows = []
    for line in systemctl("list-units", "--all", "--type=service",
                          "--no-legend", "--no-pager").splitlines():
        parts = line.lstrip("● ").split()
        if len(parts) < 4:
            continue
        unit = parts[0]
        if unit.startswith("boat-") or unit.startswith("boat_"):
            rows.append((unit, parts[2] if len(parts)>2 else "unknown"))
    rows.sort()
    print("LIVE_BOAT_SERVICES=" + str(len(rows)), flush=True)
    for unit, state in rows[:35]:
        print("SERVICE|" + unit + "|" + state, flush=True)
    if len(rows) > 35:
        print("SERVICE_TRUNCATED=" + str(len(rows)-35), flush=True)

    t = []
    for line in systemctl("list-timers", "--all", "--no-legend",
                          "--no-pager").splitlines():
        units = re.findall(r"\bboat-[\w@.-]+\.timer\b", line)
        if units:
            t.extend(units)
    t = sorted(set(t))
    print("BOAT_TIMERS=" + str(len(t)), flush=True)
    for item in t[:30]:
        print("TIMER|" + item, flush=True)

def scan_repo():
    found = []
    count = 0
    for directory in [ROOT, ROOT / "v5", ROOT / "deploy" / "conoha"]:
        if not directory.is_dir():
            continue
        files = directory.glob("*") if directory == ROOT else directory.rglob("*")
        for file in files:
            if not file.is_file() or file.suffix not in VALID_SUFFIX:
                continue
            if any(part in SKIP_DIRS for part in file.relative_to(ROOT).parts):
                continue
            if file.stat().st_size > MAX_KB * 1024:
                continue
            count += 1
            body = file.read_text(encoding="utf-8", errors="replace")
            refs = sorted(set(TARGET_PATTERN.findall(body)), key=str.casefold)
            if not refs:
                continue
            writers = {x.lower() for x in WRITE_SQL.findall(body)}
            writers.update(x.lower() for x in UPSERT.findall(body))
            write_targets = sorted(set(refs) & writers)
            # Only show file names and known table identifiers, never source contents
            path = str(file.relative_to(ROOT))
            found.append((path, sorted(set(r.lower() for r in refs)), write_targets))
    print("FILES_SCANNED=" + str(count), flush=True)
    print("TARGET_REFERENCING_FILES=" + str(len(found)), flush=True)
    priority = lambda x: (
        0 if x[0].startswith("v5/") else
        1 if x[0] in ("repair_month_all_pg.py","save_k_day_results_pg.py") else
        2 if x[0].startswith("deploy/conoha/") else 3, x[0]
    )
    for path, refs, writes in sorted(found, key=priority)[:48]:
        print("REFERENCE|" + path + "|WRITE_HINT=" + (",".join(writes) or "-")
              + "|TABLES=" + ",".join(refs[:7]), flush=True)
    if len(found)>48:
        print("REFERENCES_TRUNCATED=" + str(len(found)-48),flush=True)
    print("STATIC_WRITE_HINTS_REQUIRE_RUNTIME_CONFIRMATION", flush=True)

def main():
    print("MODE=READ_ONLY_LIVE_WRITER_INVENTORY", flush=True)
    print("NO_DB_WRITES_NO_SERVICE_CHANGES_NO_SECRETS", flush=True)
    live_units()
    scan_repo()
    print("LIVE_WRITER_INVENTORY_COMPLETE_NO_DB_WRITES",flush=True)

if __name__=="__main__":
    main()
