# -*- coding: utf-8 -*-
"""
run_gap_repair_20260701_20260815_pg.py

2026-07-01 ～ 2026-08-15 の不足データをまとめて補修するワンタイム用ラッパー。

Phase 1:
  repair_month_all_pg.py
  - races / entries
  - results
  - trifecta odds

Phase 2:
  backfill_historical_beforeinfo_pg.py
  - historical weather
  - historical exhibition
  - historical race condition
  - historical racer condition

既存データはupsertされるため再実行可能。
LINE通知・本番予想・購入処理は行わない。

Start Command:
    python -u run_gap_repair_20260701_20260815_pg.py

Variables:
    DATABASE_URL

任意:
    GAP_REPAIR_START_DATE=2026-07-01
    GAP_REPAIR_END_DATE=2026-08-15

    GAP_REPAIR_CORE=1
    GAP_REPAIR_BEFOREINFO=1

    REPAIR_WORKERS=6
    REPAIR_ODDS_WORKERS=2
    HIST_WORKERS=6
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

VERSION = "2026-08-15 gap-repair-jul-aug-v1"

START_DATE = os.getenv("GAP_REPAIR_START_DATE", "2026-07-01").strip()
END_DATE = os.getenv("GAP_REPAIR_END_DATE", "2026-08-15").strip()

DO_CORE = os.getenv("GAP_REPAIR_CORE", "1").strip().lower() in {
    "1", "true", "yes", "on"
}
DO_BEFOREINFO = os.getenv("GAP_REPAIR_BEFOREINFO", "1").strip().lower() in {
    "1", "true", "yes", "on"
}


def run_script(script: Path, env: dict[str, str], title: str) -> None:
    if not script.exists():
        raise FileNotFoundError(f"{title} が見つかりません: {script}")

    print("\n" + "=" * 88, flush=True)
    print(f"PHASE START: {title}", flush=True)
    print(f"SCRIPT={script.name}", flush=True)
    print(f"RANGE={START_DATE}..{END_DATE}", flush=True)
    print("=" * 88, flush=True)

    p = subprocess.run(
        [sys.executable, "-u", str(script)],
        cwd=str(script.parent),
        env=env,
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"{title} failed: returncode={p.returncode}"
        )

    print(f"PHASE DONE: {title}", flush=True)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    base = Path(__file__).resolve().parent

    print(
        f"✅ run_gap_repair_20260701_20260815_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(f"RANGE={START_DATE}..{END_DATE}", flush=True)
    print(
        f"GAP_REPAIR_CORE={int(DO_CORE)} "
        f"GAP_REPAIR_BEFOREINFO={int(DO_BEFOREINFO)}",
        flush=True,
    )
    print(
        "ワンタイム補修。LINE通知・本番予想・購入処理なし。",
        flush=True,
    )

    if DO_CORE:
        env = os.environ.copy()
        env["REPAIR_START_DATE"] = START_DATE
        env["REPAIR_END_DATE"] = END_DATE
        env["REPAIR_DO_RACES"] = "1"
        env["REPAIR_DO_RESULTS"] = "1"
        env["REPAIR_DO_ODDS"] = "1"
        env.setdefault(
            "REPAIR_VENUES",
            ",".join(f"{i:02d}" for i in range(1, 25)),
        )
        env.setdefault(
            "REPAIR_RACE_NOS",
            ",".join(str(i) for i in range(1, 13)),
        )
        env.setdefault("REPAIR_SLEEP_SEC", "0.1")
        env.setdefault("REPAIR_WORKERS", "6")
        env.setdefault("REPAIR_ODDS_WORKERS", "2")

        run_script(
            base / "repair_month_all_pg.py",
            env,
            "CORE races/results/odds repair",
        )
    else:
        print("CORE repair skipped.", flush=True)

    if DO_BEFOREINFO:
        env = os.environ.copy()
        env["HIST_START_DATE"] = START_DATE
        env["HIST_END_DATE"] = END_DATE
        env["HIST_SNAPSHOT_LABEL"] = "historical"
        env.setdefault("HIST_WORKERS", "6")
        env.setdefault("HIST_REQUIRE_SIX_EXHIBITION", "1")

        run_script(
            base / "backfill_historical_beforeinfo_pg.py",
            env,
            "HISTORICAL beforeinfo repair",
        )
    else:
        print("Historical beforeinfo repair skipped.", flush=True)

    print("\n" + "=" * 88, flush=True)
    print("=== JUL-AUG GAP REPAIR COMPLETED ===", flush=True)
    print(f"RANGE={START_DATE}..{END_DATE}", flush=True)
    print("=" * 88, flush=True)


if __name__ == "__main__":
    main()