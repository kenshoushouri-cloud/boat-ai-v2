# -*- coding: utf-8 -*-
"""Opt-in repeated base-odds refresh for live PRE windows.

This runner is intentionally dormant unless WINDOW_REFRESH_EXECUTE=1.
It refreshes only non-final trifecta odds for upcoming races close enough to the
start deadline, skips races whose dynamic ticket set is already complete, and
never invokes PRE/LINE, FINAL decisions, or model promotion logic.

The intended future use is a small recurring Railway cron/service after a
separate review of scheduling/cost. Merging this file alone changes no Railway
schedule or Variable.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import run_odds_window_pg as odds

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-24 repeat-odds-refresh-v2-60min-default"
VALID_WINDOWS = ("morning", "day", "night")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    return default if not raw else float(raw)


def _today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


def _clock_at(target_date: str, hhmm: str) -> datetime:
    return datetime.strptime(
        f"{target_date} {hhmm}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=JST)


def _deadline_at(row: Dict[str, Any], target_date: str) -> Optional[datetime]:
    value = row.get("deadline_at")
    if isinstance(value, datetime):
        return value.replace(tzinfo=JST) if value.tzinfo is None else value.astimezone(JST)
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=JST) if parsed.tzinfo is None else parsed.astimezone(JST)
        except Exception:
            pass
    clock = str(row.get("deadline_time") or "").strip()[:5]
    if not clock:
        return None
    try:
        return _clock_at(target_date, clock)
    except Exception:
        return None


def _parse_requested_windows() -> List[str]:
    raw = (os.getenv("WINDOW_REFRESH_WINDOWS") or "").strip().lower()
    if not raw:
        return []
    values = [x.strip() for x in raw.replace(" ", ",").split(",") if x.strip()]
    invalid = [x for x in values if x not in VALID_WINDOWS]
    if invalid:
        raise ValueError(f"invalid WINDOW_REFRESH_WINDOWS: {invalid}")
    return list(dict.fromkeys(values))


def _active_windows(now_jst: datetime, target_date: str) -> List[str]:
    requested = _parse_requested_windows()
    if requested:
        return requested

    prewarm_min = max(0.0, _env_float("WINDOW_REFRESH_PREWARM_MIN", 15.0))
    active: List[str] = []
    for name in VALID_WINDOWS:
        start, end = odds.WINDOW_PRESETS[name]
        active_start = _clock_at(target_date, start) - timedelta(minutes=prewarm_min)
        active_end = (
            _clock_at(target_date, end)
            if end
            else _clock_at(target_date, "23:59") + timedelta(minutes=1)
        )
        if active_start <= now_jst < active_end:
            active.append(name)
    return active


def _scoped_selector(
    target_date: str,
    start: str,
    end: Optional[str],
) -> List[Dict[str, Any]]:
    rows = _ORIGINAL_SELECTOR(target_date, start, end)
    now_jst = datetime.now(JST)
    min_before = max(0.0, _env_float("WINDOW_REFRESH_MIN_MINUTES_BEFORE_DEADLINE", 10.0))
    max_before = max(min_before, _env_float("WINDOW_REFRESH_MAX_MINUTES_BEFORE_DEADLINE", 60.0))

    kept: List[Dict[str, Any]] = []
    missing_deadline = 0
    too_late = 0
    too_early = 0
    for row in rows:
        deadline = _deadline_at(row, target_date)
        if deadline is None:
            missing_deadline += 1
            continue
        minutes_before = (deadline - now_jst).total_seconds() / 60.0
        if minutes_before < min_before:
            too_late += 1
            continue
        if minutes_before > max_before:
            too_early += 1
            continue
        kept.append(row)

    print(
        "WINDOW_REFRESH_SCOPE="
        f"window:{os.getenv('WINDOW_NAME','')} before:{len(rows)} kept:{len(kept)} "
        f"min_before:{min_before:.1f} max_before:{max_before:.1f} "
        f"too_late:{too_late} too_early:{too_early} missing_deadline:{missing_deadline}",
        flush=True,
    )
    if kept:
        sample = ",".join(str(row.get("race_id") or "") for row in kept[:20])
        print(f"WINDOW_REFRESH_TARGET_SAMPLE={sample}", flush=True)
    return kept


def _run_one(window_name: str, target_date: str) -> None:
    os.environ["TARGET_DATE"] = target_date
    os.environ["WINDOW_NAME"] = window_name
    os.environ.pop("WINDOW_START", None)
    os.environ.pop("WINDOW_END", None)

    # Repeated refresh must remain efficient and non-final.
    os.environ["WINDOW_SKIP_FULL_ODDS"] = "1"
    os.environ.setdefault("WINDOW_WORKERS", "2")
    os.environ.setdefault("WINDOW_ODDS_RETRIES", "1")
    os.environ.setdefault("WINDOW_ODDS_RETRY_WAIT_SEC", "10")

    print(f"WINDOW_REFRESH_RUN=window:{window_name} target_date:{target_date}", flush=True)
    odds.main()


def main() -> None:
    execute = _env_bool("WINDOW_REFRESH_EXECUTE", False)
    allow_replay = _env_bool("WINDOW_REFRESH_ALLOW_REPLAY", False)
    target_date = (os.getenv("TARGET_DATE") or _today_jst()).strip()
    now_jst = datetime.now(JST)
    today = now_jst.strftime("%Y-%m-%d")

    print(f"OK run_window_refresh_pg.py VERSION {VERSION}", flush=True)
    print(f"WINDOW_REFRESH_EXECUTE={execute}", flush=True)
    print(f"TARGET_DATE={target_date}", flush=True)
    print(f"WINDOW_REFRESH_NOW_JST={now_jst.isoformat(timespec='seconds')}", flush=True)
    print("WINDOW_REFRESH_POLICY=base_odds_only_no_pre_no_line_no_final_no_promotion", flush=True)

    if target_date != today and not allow_replay:
        print(
            f"WINDOW_REFRESH_RESULT=BLOCKED_NONLIVE_DATE target:{target_date} today:{today}",
            flush=True,
        )
        return

    windows = _active_windows(now_jst, target_date)
    print(
        "WINDOW_REFRESH_ACTIVE_WINDOWS=" + (",".join(windows) if windows else "none"),
        flush=True,
    )

    if not execute:
        print("WINDOW_REFRESH_RESULT=PLAN_ONLY_DISABLED_BY_DEFAULT", flush=True)
        return

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required when WINDOW_REFRESH_EXECUTE=1")
    if not windows:
        print("WINDOW_REFRESH_RESULT=NO_ACTIVE_WINDOW", flush=True)
        return

    for window_name in windows:
        _run_one(window_name, target_date)

    print(f"WINDOW_REFRESH_RESULT=PASS windows:{len(windows)}", flush=True)


_ORIGINAL_SELECTOR = odds.select_window_races
odds.select_window_races = _scoped_selector


if __name__ == "__main__":
    main()
