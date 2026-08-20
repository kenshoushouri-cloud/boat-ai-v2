# -*- coding: utf-8 -*-
"""
repair_motor2_invalid_pg.py

v2_race_entries の motor_place2_rate 異常値（<0 または >100）を含む
レースだけを抽出し、repair_month_all_pg.py v12 で出走表を再取得する補修ラッパー。

- 対象は「異常行」ではなく「異常を含むレース」単位
- 各対象レースの6艇を再取得・再解析
- 結果・オッズは取得しない
- 補修前後で異常件数を監査
- 本番判定・LINE・BUYには影響しない

Start Command:
    python -u repair_motor2_invalid_pg.py

任意Variables:
    MOTOR2_REPAIR_START_DATE=2025-07-01
    MOTOR2_REPAIR_END_DATE=2026-08-20
    MOTOR2_REPAIR_WORKERS=4
    MOTOR2_REPAIR_SLEEP_SEC=0.1
    MOTOR2_REPAIR_MAX_RACES=0
    MOTOR2_REPAIR_DRY_RUN=0
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from db_pg import fetch_all

VERSION = "2026-08-20 motor2-invalid-repair-wrapper-v1"

START_DATE = (os.getenv("MOTOR2_REPAIR_START_DATE") or "2025-07-01").strip()
END_DATE = (os.getenv("MOTOR2_REPAIR_END_DATE") or "2026-08-20").strip()
WORKERS = max(1, int(os.getenv("MOTOR2_REPAIR_WORKERS", "4")))
SLEEP_SEC = os.getenv("MOTOR2_REPAIR_SLEEP_SEC", "0.1").strip()
MAX_RACES = max(0, int(os.getenv("MOTOR2_REPAIR_MAX_RACES", "0")))
DRY_RUN = (os.getenv("MOTOR2_REPAIR_DRY_RUN") or "0").strip().lower() in {
    "1", "true", "yes", "on"
}


def _fetch_invalid_races() -> List[str]:
    limit_sql = ""
    params: List[Any] = [START_DATE, END_DATE]

    if MAX_RACES > 0:
        limit_sql = "LIMIT %s"
        params.append(MAX_RACES)

    rows = fetch_all(
        f"""
        SELECT DISTINCT e.race_id
        FROM v2_race_entries e
        JOIN v2_races r
          ON r.race_id = e.race_id
        WHERE r.race_date >= %s
          AND r.race_date <= %s
          AND e.motor_place2_rate IS NOT NULL
          AND (
                e.motor_place2_rate < 0
             OR e.motor_place2_rate > 100
          )
        ORDER BY e.race_id
        {limit_sql}
        """,
        tuple(params),
    )

    return [
        str(row.get("race_id") or "")
        for row in rows
        if row.get("race_id")
    ]


def _fetch_audit(race_ids: List[str]) -> Dict[str, int]:
    if not race_ids:
        return {
            "races": 0,
            "entry_rows": 0,
            "invalid_rows": 0,
            "invalid_races": 0,
            "motor2_null_rows": 0,
        }

    rows = fetch_all(
        """
        SELECT
            COUNT(DISTINCT race_id)::int AS races,
            COUNT(*)::int AS entry_rows,
            COUNT(*) FILTER (
                WHERE motor_place2_rate IS NOT NULL
                  AND (
                        motor_place2_rate < 0
                     OR motor_place2_rate > 100
                  )
            )::int AS invalid_rows,
            COUNT(DISTINCT race_id) FILTER (
                WHERE motor_place2_rate IS NOT NULL
                  AND (
                        motor_place2_rate < 0
                     OR motor_place2_rate > 100
                  )
            )::int AS invalid_races,
            COUNT(*) FILTER (
                WHERE motor_place2_rate IS NULL
            )::int AS motor2_null_rows
        FROM v2_race_entries
        WHERE race_id = ANY(%s)
        """,
        (race_ids,),
    )

    row = rows[0] if rows else {}

    return {
        "races": int(row.get("races") or 0),
        "entry_rows": int(row.get("entry_rows") or 0),
        "invalid_rows": int(row.get("invalid_rows") or 0),
        "invalid_races": int(row.get("invalid_races") or 0),
        "motor2_null_rows": int(row.get("motor2_null_rows") or 0),
    }


def _print_audit(label: str, audit: Dict[str, int]) -> None:
    print(f"=== {label} ===", flush=True)
    print(f"races={audit['races']}", flush=True)
    print(f"entry_rows={audit['entry_rows']}", flush=True)
    print(f"invalid_rows={audit['invalid_rows']}", flush=True)
    print(f"invalid_races={audit['invalid_races']}", flush=True)
    print(f"motor2_null_rows={audit['motor2_null_rows']}", flush=True)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        f"✅ repair_motor2_invalid_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(
        f"PERIOD={START_DATE}..{END_DATE} "
        f"WORKERS={WORKERS} SLEEP_SEC={SLEEP_SEC} "
        f"MAX_RACES={MAX_RACES or 'ALL'} DRY_RUN={DRY_RUN}",
        flush=True,
    )
    print(
        "TARGET=only races containing invalid motor_place2_rate (<0 or >100)",
        flush=True,
    )
    print("RESULTS=0 ODDS=0 LINE=0 BUY=0", flush=True)

    race_ids = _fetch_invalid_races()

    print(f"target_races={len(race_ids)}", flush=True)

    if race_ids:
        print(
            "target_sample=" + ",".join(race_ids[:20]),
            flush=True,
        )

    if not race_ids:
        print("補修対象はありません。", flush=True)
        print("RESULT=NO_TARGETS", flush=True)
        return

    before = _fetch_audit(race_ids)
    _print_audit("BEFORE AUDIT", before)

    if DRY_RUN:
        print("DRY_RUN=1 のため再取得は実行しません。", flush=True)
        print("RESULT=PASS", flush=True)
        return

    base_dir = Path(__file__).resolve().parent
    repair_path = base_dir / "repair_month_all_pg.py"

    if not repair_path.exists():
        raise FileNotFoundError(
            f"repair_month_all_pg.py が見つかりません: {repair_path}"
        )

    child_env = os.environ.copy()
    child_env.update(
        {
            "REPAIR_RACE_IDS": ",".join(race_ids),
            "REPAIR_DO_RACES": "1",
            "REPAIR_DO_RESULTS": "0",
            "REPAIR_DO_ODDS": "0",
            "REPAIR_WORKERS": str(WORKERS),
            "REPAIR_ODDS_WORKERS": "1",
            "REPAIR_SLEEP_SEC": SLEEP_SEC,
            "ODDS_IS_FINAL": "0",
            "PYTHONUNBUFFERED": "1",
        }
    )

    print("=== REPAIR START ===", flush=True)

    result = subprocess.run(
        [sys.executable, "-u", str(repair_path)],
        cwd=str(base_dir),
        env=child_env,
        check=False,
        text=True,
    )

    print(
        f"=== REPAIR END returncode={result.returncode} ===",
        flush=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"repair_month_all_pg.py failed returncode={result.returncode}"
        )

    after = _fetch_audit(race_ids)
    _print_audit("AFTER AUDIT", after)

    remaining = _fetch_invalid_races()

    print("=== GLOBAL REMAINING AUDIT ===", flush=True)
    print(f"remaining_invalid_races={len(remaining)}", flush=True)

    if remaining:
        print(
            "remaining_sample=" + ",".join(remaining[:20]),
            flush=True,
        )
        print("RESULT=PARTIAL", flush=True)
    else:
        print("remaining_invalid_races=0", flush=True)
        print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()