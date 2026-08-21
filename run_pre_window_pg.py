# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-21 pre-window-log-cleanup-v3-shadow-rules-observability"

WINDOW_PRESETS = {
    "morning": ("08:30", "10:15"),
    "day": ("09:45", "15:00"),
    "night": ("14:45", None),
}


def _today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


LIVE_GUARD_ENABLED = _env_bool("PRE_LIVE_GUARD_ENABLED", True)
ALLOW_HISTORICAL_REPLAY = _env_bool("PRE_ALLOW_HISTORICAL_REPLAY", False)
ALLOW_FUTURE_TEST = _env_bool("PRE_ALLOW_FUTURE_TEST", False)
FORCE_DRY_RUN_FOR_REPLAY = _env_bool("PRE_FORCE_DRY_RUN_FOR_REPLAY", True)
DISABLE_SHADOW_ON_REPLAY = _env_bool("PRE_DISABLE_SHADOW_ON_REPLAY", True)


def _resolve_window() -> Tuple[str, Optional[str], str]:
    name = (os.getenv("WINDOW_NAME") or os.getenv("WINDOW_MODE") or "").strip().lower()
    start = (os.getenv("WINDOW_START") or "").strip()
    end = (os.getenv("WINDOW_END") or "").strip()

    if not start:
        if name in WINDOW_PRESETS:
            start, default_end = WINDOW_PRESETS[name]
            if not end:
                end = default_end or ""
        else:
            name = "morning"
            start, default_end = WINDOW_PRESETS[name]
            end = default_end or ""

    if not name:
        name = f"{start}-{end or 'end'}"

    return start, (end or None), name


def _default_pre_session(window_name: str) -> str:
    return "night" if window_name == "night" else "day"


def _connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL が未設定です")
    try:
        import psycopg

        return psycopg.connect(url)
    except Exception:
        import psycopg2

        return psycopg2.connect(url)


def _fetch_dicts(sql: str, params: Tuple[Any, ...]) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [getattr(d, "name", None) or d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def select_window_races(
    target_date: str,
    start: str,
    end: Optional[str],
) -> List[Dict[str, Any]]:
    if end:
        if start <= end:
            sql = """
                select race_id,race_date::text as race_date,venue_code,venue_name,
                       race_no,deadline_time,deadline_at
                from v2_races
                where race_date=%s
                  and deadline_time is not null
                  and deadline_time >= %s
                  and deadline_time < %s
                order by deadline_time,venue_code,race_no
            """
            params = (target_date, start, end)
        else:
            sql = """
                select race_id,race_date::text as race_date,venue_code,venue_name,
                       race_no,deadline_time,deadline_at
                from v2_races
                where race_date=%s
                  and deadline_time is not null
                  and (deadline_time >= %s or deadline_time < %s)
                order by deadline_time,venue_code,race_no
            """
            params = (target_date, start, end)
    else:
        sql = """
            select race_id,race_date::text as race_date,venue_code,venue_name,
                   race_no,deadline_time,deadline_at
            from v2_races
            where race_date=%s
              and deadline_time is not null
              and deadline_time >= %s
            order by deadline_time,venue_code,race_no
        """
        params = (target_date, start)
    return _fetch_dicts(sql, params)


def _deadline_at(race: Dict[str, Any], target_date: str) -> Optional[datetime]:
    value = race.get("deadline_at")
    if isinstance(value, datetime):
        return value.replace(tzinfo=JST) if value.tzinfo is None else value.astimezone(JST)

    if value:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt.replace(tzinfo=JST) if dt.tzinfo is None else dt.astimezone(JST)
        except Exception:
            pass

    deadline_time = str(race.get("deadline_time") or "").strip()
    if deadline_time:
        try:
            return datetime.strptime(
                f"{target_date} {deadline_time}",
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=JST)
        except Exception:
            return None
    return None


def _resolve_run_class(target_date: str) -> str:
    today = _today_jst()
    if target_date < today:
        return "historical_test"
    if target_date > today:
        return "future_test"
    return "live"


def _apply_live_guard(
    races: List[Dict[str, Any]],
    target_date: str,
) -> Tuple[List[Dict[str, Any]], str, int]:
    now_jst = datetime.now(JST)
    run_class = _resolve_run_class(target_date)

    if run_class == "historical_test":
        if LIVE_GUARD_ENABLED and not ALLOW_HISTORICAL_REPLAY:
            print(
                "LIVE_GUARD: 過去日のTARGET_DATEのためブロックします。",
                flush=True,
            )
            return [], run_class, len(races)
        return races, run_class, 0

    if run_class == "future_test":
        if LIVE_GUARD_ENABLED and not ALLOW_FUTURE_TEST:
            print(
                "LIVE_GUARD: 未来日のTARGET_DATEのためブロックします。",
                flush=True,
            )
            return [], run_class, len(races)
        return races, run_class, 0

    if not LIVE_GUARD_ENABLED:
        expired = sum(
            1
            for race in races
            if (
                _deadline_at(race, target_date) is not None
                and _deadline_at(race, target_date) <= now_jst
            )
        )
        return races, ("late_replay" if expired else "live"), 0

    kept: List[Dict[str, Any]] = []
    skipped = 0
    for race in races:
        deadline_at = _deadline_at(race, target_date)
        if deadline_at is None or deadline_at <= now_jst:
            skipped += 1
            continue
        kept.append(race)

    return kept, run_class, skipped


def _apply_replay_safety(run_class: str) -> None:
    if run_class not in {"late_replay", "historical_test", "future_test"}:
        return

    if FORCE_DRY_RUN_FOR_REPLAY:
        os.environ["DRY_RUN"] = "1"
        os.environ["TEST_MODE"] = "1"
        print("REPLAY_SAFETY: DRY_RUN=1 / TEST_MODE=1", flush=True)

    if DISABLE_SHADOW_ON_REPLAY:
        os.environ["CANDIDATE_SHADOW_ENABLED"] = "0"
        print("REPLAY_SAFETY: CANDIDATE_SHADOW_ENABLED=0", flush=True)


def _candidate_shadow_rule_observability() -> None:
    enabled = _env_bool("CANDIDATE_SHADOW_ENABLED", True)
    raw = (os.getenv("CANDIDATE_SHADOW_RULES") or "S01,S02,S03,S04,S05").strip()
    rules = {
        value.strip().upper()
        for value in re.split(r"[,\s]+", raw)
        if value.strip()
    }
    print(f"CANDIDATE_SHADOW_ENABLED={enabled}", flush=True)
    print(f"CANDIDATE_SHADOW_RULES effective={','.join(sorted(rules))}", flush=True)
    if enabled and "N02" not in rules:
        print(
            "WARNING: N02 PRE Forward collection is not enabled by the effective "
            "CANDIDATE_SHADOW_RULES. N02 rows will not be added by this PRE window "
            "unless Railway Variables explicitly include N02.",
            flush=True,
        )


def _run_script(script_path: Path, display_name: str, *, required: bool) -> None:
    if not script_path.exists():
        msg = f"{display_name} が見つかりません: {script_path}"
        if required:
            raise FileNotFoundError(msg)
        print(f"WARNING: {msg}", flush=True)
        return

    print(f"{display_name} を実行します。", flush=True)
    runpy.run_path(str(script_path), run_name="__main__")


def main() -> None:
    print(f"OK run_pre_window_pg.py VERSION {VERSION}", flush=True)

    target_date = os.getenv("TARGET_DATE") or _today_jst()
    window_start, window_end, window_name = _resolve_window()

    print(f"TARGET_DATE={target_date}", flush=True)
    print(f"WINDOW_NAME={window_name}", flush=True)
    print(f"WINDOW_START={window_start}", flush=True)
    print(f"WINDOW_END={window_end or ''}", flush=True)
    print(f"PRE_LIVE_GUARD_ENABLED={LIVE_GUARD_ENABLED}", flush=True)

    raw_races = select_window_races(target_date, window_start, window_end)
    races, run_class, skipped = _apply_live_guard(raw_races, target_date)

    os.environ["PRE_RUN_CLASS"] = run_class
    _apply_replay_safety(run_class)

    print(f"PRE_RUN_CLASS={run_class}", flush=True)
    print(f"window_races_before_guard={len(raw_races)}", flush=True)
    print(f"live_guard_skipped={skipped}", flush=True)
    print(f"target_races={len(races)}", flush=True)

    if not races:
        print("LIVE_GUARD適用後の対象レースなし。終了します。", flush=True)
        return

    race_ids = [str(race["race_id"]) for race in races]
    pre_session = os.getenv("PRE_SESSION") or _default_pre_session(window_name)

    os.environ["TARGET_DATE"] = target_date
    os.environ["TARGET_RACE_IDS"] = ",".join(race_ids)
    os.environ["PRE_WINDOW_START"] = window_start
    os.environ["PRE_WINDOW_END"] = window_end or ""
    os.environ["PRE_SESSION"] = pre_session
    os.environ["WINDOW_NAME"] = window_name

    print(f"TARGET_RACE_IDS exported: {len(race_ids)} races", flush=True)
    print(f"PRE_SESSION exported: {pre_session}", flush=True)
    print(f"WINDOW_NAME exported: {window_name}", flush=True)
    print(f"PRE_RUN_CLASS exported: {run_class}", flush=True)
    _candidate_shadow_rule_observability()

    base_dir = Path(__file__).resolve().parent

    _run_script(
        base_dir / "v24_pre_candidate_notifier_pg.py",
        "v24_pre_candidate_notifier_pg.py",
        required=True,
    )

    _run_script(
        base_dir / "collect_candidate_filter_shadow_pg.py",
        "collect_candidate_filter_shadow_pg.py",
        required=False,
    )

    print("=== run_pre_window_pg.py finished ===", flush=True)


if __name__ == "__main__":
    main()
