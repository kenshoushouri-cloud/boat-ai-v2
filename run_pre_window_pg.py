# -*- coding: utf-8 -*-
"""
run_pre_window_pg.py

Railway Postgres版：締切時刻ウィンドウ内のレースIDを抽出し、
v24_pre_candidate_notifier_pg.py に TARGET_RACE_IDS として渡すラッパーです。

v24仮候補処理の完了後、候補フィルターShadow保存処理
collect_candidate_filter_shadow_pg.py を実行します。

Start Command:
    python -u run_pre_window_pg.py

主な環境変数:
    TARGET_DATE=2026-07-09          # 未指定ならJST当日
    WINDOW_NAME=morning|day|night   # 任意。WINDOW_START/ENDが優先
    WINDOW_START=08:30
    WINDOW_END=10:15                # 後半枠は空でもOK
    PRE_SESSION=day|night|all       # 未指定なら morning/day は day、night は night

Shadow任意環境変数:
    CANDIDATE_SHADOW_ENABLED=1
    CANDIDATE_SHADOW_REQUIRE_COMPLETE_ODDS=1
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

JST = timezone(timedelta(hours=9))

WINDOW_PRESETS = {
    "morning": ("08:30", "10:15"),
    "day": ("09:45", "15:00"),
    "night": ("14:45", None),
}


def _today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


def _resolve_window() -> Tuple[str, Optional[str], str]:
    name = (
        os.getenv("WINDOW_NAME")
        or os.getenv("WINDOW_MODE")
        or ""
    ).strip().lower()

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
    """
    v24_pre_candidate_notifier_pg.py の PRE_SESSION は day|night|all 想定。
    morning は昼間扱いにする。
    """
    if window_name == "night":
        return "night"
    return "day"


def _connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL が未設定です")

    try:
        import psycopg  # type: ignore
        return psycopg.connect(url)
    except Exception:
        import psycopg2  # type: ignore
        return psycopg2.connect(url)


def _fetch_dicts(
    sql: str,
    params: Tuple[Any, ...],
) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = []
            for d in cur.description:
                cols.append(getattr(d, "name", None) or d[0])
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
                select
                    race_id,
                    race_date::text as race_date,
                    venue_code,
                    venue_name,
                    race_no,
                    deadline_time,
                    deadline_at
                from v2_races
                where race_date = %s
                  and deadline_time is not null
                  and deadline_time >= %s
                  and deadline_time < %s
                order by deadline_time, venue_code, race_no
            """
            params = (target_date, start, end)
        else:
            sql = """
                select
                    race_id,
                    race_date::text as race_date,
                    venue_code,
                    venue_name,
                    race_no,
                    deadline_time,
                    deadline_at
                from v2_races
                where race_date = %s
                  and deadline_time is not null
                  and (
                      deadline_time >= %s
                      or deadline_time < %s
                  )
                order by deadline_time, venue_code, race_no
            """
            params = (target_date, start, end)
    else:
        sql = """
            select
                race_id,
                race_date::text as race_date,
                venue_code,
                venue_name,
                race_no,
                deadline_time,
                deadline_at
            from v2_races
            where race_date = %s
              and deadline_time is not null
              and deadline_time >= %s
            order by deadline_time, venue_code, race_no
        """
        params = (target_date, start)

    return _fetch_dicts(sql, params)


def _run_script(
    script_path: Path,
    display_name: str,
    *,
    required: bool,
) -> None:
    if not script_path.exists():
        message = f"{display_name} が見つかりません: {script_path}"
        if required:
            raise FileNotFoundError(message)
        print(f"⚠️ {message}", flush=True)
        return

    print(f"{display_name} を実行します。", flush=True)
    runpy.run_path(str(script_path), run_name="__main__")


def main() -> None:
    print(
        "✅ run_pre_window_pg.py VERSION "
        "2026-08-01 candidate-filter-shadow-v1",
        flush=True,
    )

    target_date = os.getenv("TARGET_DATE") or _today_jst()
    window_start, window_end, window_name = _resolve_window()

    print(f"TARGET_DATE={target_date}", flush=True)
    print(f"WINDOW_NAME={window_name}", flush=True)
    print(f"WINDOW_START={window_start}", flush=True)
    print(f"WINDOW_END={window_end or ''}", flush=True)
    print(
        f"DATABASE_URL="
        f"{'OK' if os.getenv('DATABASE_URL') else 'MISSING'}",
        flush=True,
    )

    races = select_window_races(
        target_date,
        window_start,
        window_end,
    )
    race_ids = [str(r["race_id"]) for r in races]

    print(f"target_races={len(race_ids)}", flush=True)
    if races:
        print("target sample:", flush=True)
        for race in races[:30]:
            print(
                f"  {race['race_id']} "
                f"{race.get('venue_name') or ''} "
                f"{race.get('race_no')}R "
                f"deadline={race.get('deadline_time')}",
                flush=True,
            )

    if not race_ids:
        print("対象レースなし。終了します。", flush=True)
        return

    pre_session = (
        os.getenv("PRE_SESSION")
        or _default_pre_session(window_name)
    )

    # v24とShadow処理へ渡す環境変数。
    os.environ["TARGET_DATE"] = target_date
    os.environ["TARGET_RACE_IDS"] = ",".join(race_ids)
    os.environ["PRE_WINDOW_START"] = window_start
    os.environ["PRE_WINDOW_END"] = window_end or ""
    os.environ["PRE_SESSION"] = pre_session
    os.environ["WINDOW_NAME"] = window_name

    print(
        f"TARGET_RACE_IDS exported: {len(race_ids)} races",
        flush=True,
    )
    print(
        f"PRE_SESSION exported: {pre_session}",
        flush=True,
    )
    print(
        f"WINDOW_NAME exported: {window_name}",
        flush=True,
    )

    base_dir = Path(__file__).resolve().parent

    # 1. 既存の仮候補判定・LINE通知
    _run_script(
        base_dir / "v24_pre_candidate_notifier_pg.py",
        "v24_pre_candidate_notifier_pg.py",
        required=True,
    )

    # 2. 新規の候補フィルターShadow保存
    _run_script(
        base_dir / "collect_candidate_filter_shadow_pg.py",
        "collect_candidate_filter_shadow_pg.py",
        required=False,
    )

    print(
        "=== run_pre_window_pg.py finished ===",
        flush=True,
    )


if __name__ == "__main__":
    main()