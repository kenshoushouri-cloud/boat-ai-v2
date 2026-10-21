#!/usr/bin/env python3
"""V5 migration stage 1: narrow runtime writer-route audit (READ ONLY).

Reads local systemd metadata, cron identifiers and selected repository source files.
Never prints ExecStart, cron commands, URLs, connection strings or environment values.
No DB connection, no system modifications, no network calls.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess

ROOT = Path("/opt/boat-ai-v5")
TABLES = (
    "v2_races", "v2_race_entries", "v2_results", "v2_result_entries",
    "v2_realtime_exhibition_snapshots", "v2_realtime_odds_snapshots",
    "v2_realtime_weather_snapshots", "v2_realtime_race_condition_snapshots",
    "v2_realtime_racer_condition_snapshots", "v2_racer_course_stats_snapshots",
    "v2_v24_motor2_forward_shadow",
)
IMPORTANT = (
    "v5/conoha_realtime_window_pg.py",
    "v5/conoha_midnight_results_pg.py",
    "repair_month_all_pg.py",
    "save_k_day_results_pg.py",
    "collect_exhibition_st_forward_shadow_pg.py",
    "collect_v24_motor2_forward_shadow_pg.py",
    "v21_realtime_collector_pg_safe.py",
    "v21_realtime_collector_pg.py",
)
MATCH_TABLE = re.compile(r"\b(" + "|".join(map(re.escape, TABLES)) + r")\b", re.I)
DIRECT_WRITE = re.compile(
    r"\b(?:insert\s+into|update|delete\s+from|merge\s+into)\s+"
    r"(?:public\.)?(v2_[a-z_0-9]+)", re.I,
)
UPSERT_CALL = re.compile(r"\bupsert_rows\s*\(\s*['\"](v2_[a-z_0-9]+)['\"]", re.I)
MODULE = re.compile(r"(?:^|\s)-m\s+([a-zA-Z_][a-zA-Z0-9_.]*)")
LOCAL_PY = re.compile(r"/opt/boat-ai-v5/(?:[a-zA-Z0-9_.-]+/)*[a-zA-Z0-9_.-]+\.(?:py|sh)\b")

def command(*args: str) -> str:
    try:
        result = subprocess.run(args, check=False, text=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=8)
        return result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""

def installed(kind: str):
    lines = command("systemctl", "list-unit-files",
                    "--type="+kind, "--all", "--no-legend",
                    "--no-pager")
    names = set()
    for line in lines.splitlines():
        cols = line.split()
        if cols and ("boat-" in cols[0] or cols[0].startswith("v5-")):
            if cols[0].endswith("." + kind):
                names.add(cols[0])
    return sorted(names)

def unit(name: str):
    # Systemctl metadata is read internally but only allowlisted fields printed.
    raw = command("systemctl", "show", name, "--no-pager",
                  "--property=ActiveState,UnitFileState,ExecStart")
    fields = dict(x.split("=",1) for x in raw.splitlines() if "=" in x)
    state = fields.get("ActiveState", "unknown")
    enabled = fields.get("UnitFileState", "unknown")
    if state not in {"active","inactive","failed","activating","deactivating"}:
        state = "unknown"
    if enabled not in {"enabled","disabled","static","masked","indirect",
                       "generated","linked","enabled-runtime"}:
        enabled = "other"
    program = fields.get("ExecStart","")
    modules = sorted(set(MODULE.findall(program)))
    scripts = sorted(set(Path(x).name for x in LOCAL_PY.findall(program)))
    target = ",".join(modules + scripts[:3]) or "UNRESOLVED"
    return state, enabled, target

def print_units():
    svc = installed("service")
    timers = installed("timer")
    print(f"INSTALLED_BOAT_SERVICES={len(svc)} BOAT_TIMERS={len(timers)}",flush=True)
    for name in svc[:26]:
        state, enabled, target = unit(name)
        print(f"SERVICE|{name}|state={state}|unitfile={enabled}|target={target}",flush=True)
    for name in timers[:18]:
        state, enabled, _ = unit(name)
        print(f"TIMER|{name}|state={state}|unitfile={enabled}",flush=True)
    # Resolve template service instances, showing only safe module/script identifiers.
    for instance in ("morning", "night"):
        name = f"boat-v5-daily@{instance}.service"
        state, enabled, target = unit(name)
        print(f"DAILY_INSTANCE|{name}|state={state}|unitfile={enabled}|target={target}",flush=True)
    if len(svc)>26 or len(timers)>18:
        print("SERVICE_OR_TIMER_OUTPUT_TRUNCATED",flush=True)

def print_cron_identifiers():
    directory = Path("/etc/cron.d")
    names = []
    if directory.is_dir():
        for file in sorted(directory.iterdir()):
            if not file.is_file() or file.stat().st_size>262144:
                continue
            if ("boat" in file.name or "v5" in file.name):
                names.append(file.name)
    print("CRON_D_MATCHING_FILENAMES="+(",".join(names) or "-"),flush=True)
    for who in ("root","postgres"):
        raw = command("crontab", "-u", who, "-l")
        lines = [line for line in raw.splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        matched = sum("boat" in line.lower() or "v5" in line.lower()
                      for line in lines)
        # Never show cron expressions, full executable args, or secrets.
        print(f"CRONTAB|{who}|v5_boat_lines={matched}",flush=True)

def print_source_routes():
    for relative in IMPORTANT:
        p = ROOT / relative
        if not p.is_file():
            print("SOURCE|"+relative+"|MISSING",flush=True)
            continue
        data = p.read_text(encoding="utf-8",errors="replace")
        refs = sorted(set(x.lower() for x in MATCH_TABLE.findall(data)))
        direct = sorted(set(x.lower() for x in DIRECT_WRITE.findall(data)))
        indirect = sorted(set(x.lower() for x in UPSERT_CALL.findall(data)))
        # Legacy collector may create old tables again after a move.
        ddl_hint = "yes" if ("create table if not exists" in data.lower()
                          or "alter table" in data.lower()) else "no"
        print("SOURCE|"+relative+"|refs="+(",".join(refs) or "-")
              +"|direct_write_hint="+(",".join(direct) or "-")
              +"|helper_upsert_hint="+(",".join(indirect) or "-")
              +"|ddl_text_hint="+ddl_hint,flush=True)

def main():
    print("MODE=READ_ONLY_ACTIVE_WRITER_ROUTES",flush=True)
    print_units()
    print_cron_identifiers()
    print_source_routes()
    print("FORWARD_CHILD=v5.conoha_realtime_window_pg -> v21_realtime_collector_pg_safe.py -> v21_realtime_collector_pg.py",flush=True)
    print("NO_RUNTIME_WRITE_PATH_CERTIFICATION_YET",flush=True)
    print("V5_ACTIVE_WRITER_ROUTES_READONLY_COMPLETE_NO_DB_WRITES",flush=True)

if __name__ == "__main__":
    main()
