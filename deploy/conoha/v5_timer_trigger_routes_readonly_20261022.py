#!/usr/bin/env python3
"""Read-only ConoHa V5 timer -> service -> known entrypoint check.

No DB, Git or network access; no timer/service start, stop or reload.
Print only allowlisted unit names, statuses and known file/module identifiers.
Raw ExecStart, shell arguments, environment and credentials are never printed.
This is a point-in-time discovery, NOT a complete writer-path certification.
"""
from __future__ import annotations

import re
import subprocess

TIMERS = (
    "boat-v5-daily@morning.timer",
    "boat-v5-daily@night.timer",
    "boat-v5-forward-window.timer",
    "boat-v5-midnight-catchup.timer",
)
ALLOWED_SERVICE = re.compile(r"^boat-v5-[A-Za-z0-9@_.-]+\.service$")
KNOWN_WRAPPERS = (
    "daily_v5_safe.sh",
    "v21_realtime_collector_pg.py",
    "v21_realtime_collector_pg_safe.py",
    "conoha_realtime_window_pg.py",
    "conoha_midnight_results_pg.py",
    "save_k_day_results_pg.py",
    "repair_month_all_pg.py",
)
KNOWN_MODULES = (
    "v5.conoha_realtime_window_pg",
    "v5.conoha_midnight_results_pg",
    "v21_realtime_collector_pg",
)


def metadata(unit: str, props: str):
    try:
        p = subprocess.run(
            ["systemctl", "show", unit, "--no-pager", "--property=" + props],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False, timeout=8,
        )
        if p.returncode:
            return None
        return dict(line.split("=", 1) for line in p.stdout.splitlines()
                    if "=" in line)
    except (OSError, subprocess.TimeoutExpired):
        return None


def one_of(value, possible):
    return value if value in possible else "unknown"


def readable_timestamp(value):
    # No arbitrary unit metadata printed.
    if not value or value in ("n/a", "0", "Thu 1970-01-01 00:00:00 UTC"):
        return "NONE"
    return value[:44] if re.fullmatch(r"[A-Za-z0-9 :+.,/_-]{1,80}", value) else "UNKNOWN"


def identify(raw, allow):
    return [item for item in allow
            if re.search(r"(?<![A-Za-z0-9_.-])" + re.escape(item)
                         + r"(?![A-Za-z0-9_.-])", raw)]


def main():
    print("MODE=V5_TIMER_TRIGGER_ROUTES_READ_ONLY")
    for timer in TIMERS:
        t = metadata(timer,
                     "LoadState,ActiveState,UnitFileState,Unit,"
                     "LastTriggerUSec,NextElapseUSecRealtime,NextElapseUSecMonotonic")
        if t is None:
            print("TIMER|" + timer + "|METADATA_UNAVAILABLE")
            continue
        load = one_of(t.get("LoadState"), ("loaded", "not-found", "masked"))
        state = one_of(t.get("ActiveState"),
                       ("active", "inactive", "failed", "activating", "deactivating"))
        enabled = one_of(t.get("UnitFileState"),
                         ("enabled", "disabled", "static", "masked", "indirect"))
        service = t.get("Unit") or timer[:-6] + ".service"
        if not ALLOWED_SERVICE.fullmatch(service):
            print(f"TIMER|{timer}|load={load}|active={state}"
                  f"|enabled={enabled}|SERVICE_NOT_ALLOWLISTED")
            continue
        print(f"TIMER|{timer}|load={load}|active={state}|enabled={enabled}"
              f"|service={service}")
        print(f"TRIGGER|{timer}|last={readable_timestamp(t.get('LastTriggerUSec'))}"
              f"|next_realtime={readable_timestamp(t.get('NextElapseUSecRealtime'))}"
              f"|next_monotonic={'SET' if t.get('NextElapseUSecMonotonic') not in ('',None,'n/a') else 'NONE'}")
        s = metadata(service,
                     "LoadState,ActiveState,UnitFileState,ExecStart")
        if s is None:
            print(f"TARGET|{service}|METADATA_UNAVAILABLE")
            continue
        source = s.get("ExecStart", "")
        names = identify(source, KNOWN_WRAPPERS)
        modules = identify(source, KNOWN_MODULES)
        print(f"TARGET|{service}|load={one_of(s.get('LoadState'), ('loaded','not-found','masked'))}"
              f"|active={one_of(s.get('ActiveState'), ('active','inactive','failed','activating','deactivating'))}"
              f"|known_scripts={','.join(names) or 'UNRESOLVED'}"
              f"|known_modules={','.join(modules) or 'UNRESOLVED'}")
    print("LIMITATION=STATIC_SERVICE_WRAPPERS_AND_CHILD_PROCESS_PATHS_NOT_CERTIFIED")
    print("NO_DB_NO_SERVICE_CHANGES_NO_SECRETS_PRINTED")
    print("V5_TIMER_TRIGGER_ROUTES_READONLY_COMPLETE")


if __name__ == "__main__":
    main()
