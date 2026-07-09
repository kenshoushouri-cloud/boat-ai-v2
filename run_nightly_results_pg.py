# -*- coding: utf-8 -*-
"""
run_nightly_results_pg.py

Railway Postgres版：当日結果取得。
repair_month_all_pg.py を安全に探索して実行する診断対応版です。

Start Command:
    python -u run_nightly_results_pg.py
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def _find_repair_script() -> Path:
    """
    Railwayコンテナ内で repair_month_all_pg.py を探す。
    通常は /app/repair_month_all_pg.py にある想定。
    見つからない場合は .venv を除外した診断ログを出す。
    """
    base_dir = Path(__file__).resolve().parent
    cwd = Path.cwd()

    print(f"__file__={__file__}", flush=True)
    print(f"BASE_DIR={base_dir}", flush=True)
    print(f"CWD={cwd}", flush=True)

    candidates = [
        base_dir / "repair_month_all_pg.py",
        cwd / "repair_month_all_pg.py",
        Path("/app/repair_month_all_pg.py"),
        Path("/app/app/repair_month_all_pg.py"),
        Path("/app/boat-ai-v2/repair_month_all_pg.py"),
        base_dir.parent / "repair_month_all_pg.py",
    ]

    print("=== repair candidates ===", flush=True)
    for p in candidates:
        print(f"{p} exists={p.exists()}", flush=True)
        if p.exists():
            return p

    print("=== /app top-level ===", flush=True)
    app_root = Path("/app")
    if app_root.exists():
        for p in sorted(app_root.iterdir()):
            print(str(p), flush=True)

    print("=== /app python files top-level ===", flush=True)
    if app_root.exists():
        for p in sorted(app_root.glob("*.py")):
            print(str(p), flush=True)

    print("=== search repair_month_all_pg.py excluding .venv ===", flush=True)
    found = []
    if app_root.exists():
        for p in sorted(app_root.rglob("repair_month_all_pg.py")):
            if ".venv" not in p.parts:
                print(str(p), flush=True)
                found.append(p)

    if found:
        return found[0]

    raise FileNotFoundError("repair_month_all_pg.py がRailwayコンテナ内に存在しません")


def main() -> None:
    print("✅ run_nightly_results_pg.py", flush=True)

    target_date = os.getenv("TARGET_DATE")
    if not target_date:
        target_date = datetime.now(JST).strftime("%Y-%m-%d")
        os.environ["TARGET_DATE"] = target_date

    os.environ["REPAIR_START_DATE"] = target_date
    os.environ["REPAIR_END_DATE"] = target_date

    # 夜間結果取得：結果のみ。レース・出走表・オッズは触らない。
    os.environ["REPAIR_DO_RACES"] = "0"
    os.environ["REPAIR_DO_RESULTS"] = "1"
    os.environ["REPAIR_DO_ODDS"] = "0"

    # 未設定時の安全なデフォルト。
    os.environ.setdefault("REPAIR_WORKERS", os.getenv("WORKERS", "4"))
    os.environ.setdefault("REPAIR_ODDS_WORKERS", os.getenv("ODDS_WORKERS", "1"))
    os.environ.setdefault("REPAIR_SLEEP_SEC", os.getenv("SLEEP_SEC", "0.1"))

    print(f"TARGET_DATE={target_date}", flush=True)
    print("Railway Postgres版：当日結果取得を開始します。", flush=True)

    repair_path = _find_repair_script()
    print(f"✅ repair script found: {repair_path}", flush=True)

    runpy.run_path(str(repair_path), run_name="__main__")


if __name__ == "__main__":
    main()