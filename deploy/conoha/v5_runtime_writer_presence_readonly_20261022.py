#!/usr/bin/env python3
"""Bounded read-only snapshot of possible active V5 write entrypoints.

No database/network calls, no unit modifications, no process signalling.
Never print raw ExecStart, process arguments, environ, cron expressions,
tokens, paths outside an explicit safe allowlist, or secrets.
Presence is only a point-in-time signal, not a complete writer certification.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ALLOW = (
    "daily_v5_safe.sh",
    "repair_month_all_pg.py",
    "save_k_day_results_pg.py",
    "v21_realtime_collector_pg.py",
    "v21_realtime_collector_pg_safe.py",
    "v21_realtime_collector_pg_safe.sh",
    "conoha_realtime_window_pg.py",
    "conoha_midnight_results_pg.py",
    "k_missing_results_bounded_20261021.py",
    "k_results_background72_20261021.sh",
    "k_results_192_20261021.sh",
)
SERVICE_RE = re.compile(r"^(?:boat-[A-Za-z0-9@_.-]+|v5-[A-Za-z0-9@_.-]+)\.service$")
MAX_UNITS = 32
MAX_PROC = 20000


def call(*args):
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           check=False, timeout=8)
        return p.stdout if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def matched_names(raw):
    if not raw:
        return []
    # Match source basenames with boundaries; never emit arbitrary command text.
    return [name for name in ALLOW
            if re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w.-])", raw)]


def systemd_inventory():
    raw = call("systemctl", "list-unit-files", "--type=service",
               "--all", "--no-legend", "--no-pager")
    if raw is None:
        print("SYSTEMD_SERVICE_DISCOVERY=UNKNOWN")
        return
    units = {line.split()[0] for line in raw.splitlines()
             if line.split() and SERVICE_RE.fullmatch(line.split()[0])}
    units.update(("boat-v5-daily@morning.service",
                  "boat-v5-daily@night.service"))
    units = sorted(units)
    print(f"SERVICE_CANDIDATES={len(units)}")
    for name in units[:MAX_UNITS]:
        meta = call("systemctl", "show", name, "--no-pager",
                    "--property=LoadState,ActiveState,UnitFileState,ExecStart")
        if meta is None:
            print(f"SERVICE|{name}|STATUS_UNKNOWN")
            continue
        fields = dict(line.split("=", 1) for line in meta.splitlines()
                      if "=" in line)
        state = fields.get("ActiveState", "unknown")
        load = fields.get("LoadState", "unknown")
        if state not in ("active", "inactive", "failed", "activating", "deactivating"):
            state = "unknown"
        if load not in ("loaded", "not-found", "masked", "error"):
            load = "unknown"
        matched = matched_names(fields.get("ExecStart", ""))
        print(f"SERVICE|{name}|load={load}|active={state}"
              f"|known_entry={','.join(matched) or 'UNRESOLVED'}")
    if len(units) > MAX_UNITS:
        print(f"SERVICE_UNSCANNED={len(units)-MAX_UNITS}")


def live_processes():
    root = Path("/proc")
    if not root.is_dir():
        print("PROC_DISCOVERY=UNKNOWN")
        return
    try:
        items = sorted((p for p in root.iterdir() if p.name.isdigit()),
                       key=lambda p: int(p.name))[:MAX_PROC]
    except OSError:
        print("PROC_DISCOVERY=UNKNOWN")
        return
    matches = {name: 0 for name in ALLOW}
    unreadable = 0
    for pid_dir in items:
        try:
            with (pid_dir / "cmdline").open("rb") as stream:
                raw = stream.read(8192).decode("utf-8", "replace").replace("\x00", " ")
        except (OSError, ValueError):
            unreadable += 1
            continue
        for name in matched_names(raw):
            matches[name] += 1
    print(f"PROC_INSPECTED={len(items)} PROC_UNREADABLE={unreadable}")
    for name, count in matches.items():
        if count:
            print(f"LIVE_CMDLINE_NAME_HINT|{name}|matches={count}")
    if not any(matches.values()):
        print("LIVE_ALLOWLISTED_WRITER_NAMES=NONE_AT_THIS_INSTANT")
    if len(items) == MAX_PROC:
        print("PROC_LIMIT_REACHED=1")


def main():
    print("MODE=READ_ONLY_V5_RUNTIME_WRITER_PRESENCE")
    systemd_inventory()
    live_processes()
    print("LIMITATION=SHORT_LIVED_TIMERS_AND_DYNAMIC_EXEC_NOT_CERTIFIED")
    print("NO_DB_CONNECTION_NO_SERVICES_STARTED_NO_SECRETS_PRINTED")
    print("V5_RUNTIME_WRITER_PRESENCE_READONLY_COMPLETE")


if __name__ == "__main__":
    main()
