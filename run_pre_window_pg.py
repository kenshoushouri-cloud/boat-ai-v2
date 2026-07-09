# -*- coding: utf-8 -*-
"""
run_pre_window_pg.py

Railway Postgres版：締切時刻ウィンドウ内のレースIDを抽出し、
既存の v24_pre_candidate_notifier_pg.py に渡すためのラッパーです。

重要:
- このファイルは TARGET_RACE_IDS / PRE_WINDOW_START / PRE_WINDOW_END を環境変数へセットします。
- v24_pre_candidate_notifier_pg.py 側が TARGET_RACE_IDS を読む実装になっていない場合、
  候補抽出側は従来どおり全体処理になる可能性があります。
- その場合は次工程で v24_pre_candidate_notifier_pg.py 側に TARGET_RACE_IDS フィルタを追加してください。

Start Command:
    python -u run_pre_window_pg.py

主な環境変数:
    TARGET_DATE=2026-07-09
    WINDOW_NAME=morning|day|night
    WINDOW_START=08:30
    WINDOW_END=10:15
    PRE_SESSION=morning
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
    name = (os.getenv("WINDOW_NAME") or os.getenv("PRE_SESSION") or "").strip().lower()

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


def _fetch_dicts(sql: str, params: Tuple[Any, ...]) -> List[Dict[str, Any]]:
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


def select_window_races(target_date: str, start: str, end: Optional[str]) -> List[Dict[str, Any]]:
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
                  and (deadline_time >= %s or deadline_time < %s)
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


def main() -> None:
    print("✅ run_pre_window_pg.py", flush=True)

    target_date = os.getenv("TARGET_DATE") or _today_jst()
    window_start, window_end, window_name = _resolve_window()

    print(f"TARGET_DATE={target_date}", flush=True)
    print(f"WINDOW_NAME={window_name}", flush=True)
    print(f"WINDOW_START={window_start}", flush=True)
    print(f"WINDOW_END={window_end or ''}", flush=True)
    print(f"DATABASE_URL={'OK' if os.getenv('DATABASE_URL') else 'MISSING'}", flush=True)

    races = select_window_races(target_date, window_start, window_end)
    race_ids = [str(r["race_id"]) for r in races]

    print(f"target_races={len(race_ids)}", flush=True)
    if races:
        print("target sample:", flush=True)
        for r in races[:30]:
            print(
                f"  {r['race_id']} {r.get('venue_name') or ''} {r.get('race_no')}R deadline={r.get('deadline_time')}",
                flush=True,
            )

    if not race_ids:
        print("対象レースなし。終了します。", flush=True)
        return

    # v24側へ渡す環境変数。
    os.environ["TARGET_DATE"] = target_date
    os.environ["TARGET_RACE_IDS"] = ",".join(race_ids)
    os.environ["PRE_WINDOW_START"] = window_start
    os.environ["PRE_WINDOW_END"] = window_end or ""
    os.environ["PRE_SESSION"] = os.getenv("PRE_SESSION") or window_name

    # LINE通知は既存v24側の DRY_RUN / TEST_MODE / DAILY_LINE_LIMIT に従う。
    print("TARGET_RACE_IDS exported.", flush=True)
    print("v24_pre_candidate_notifier_pg.py を実行します。", flush=True)

    base_dir = Path(__file__).resolve().parent
    v24_path = base_dir / "v24_pre_candidate_notifier_pg.py"

    if not v24_path.exists():
        raise FileNotFoundError(f"v24_pre_candidate_notifier_pg.py が見つかりません: {v24_path}")

    print(
        "注意: v24側が TARGET_RACE_IDS 非対応の場合、候補抽出は従来どおり全体対象になる可能性があります。",
        flush=True,
    )

    runpy.run_path(str(v24_path), run_name="__main__")


if __name__ == "__main__":
    main()