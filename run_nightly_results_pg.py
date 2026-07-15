# -*- coding: utf-8 -*-
"""
run_nightly_results_pg.py

Railway Postgres版：当日結果取得。
同じ階層の repair_month_all_pg.py を実行し、
結果取得完了後に展示shadow成績を評価します。

Start Command:
    python -u run_nightly_results_pg.py

任意Variables:
    RUN_EXHIBITION_SHADOW_EVAL=1
    SHADOW_EVAL_STRICT=0
    SNAPSHOT_LABEL=final_ab
    SELECTOR_MODE=ab

SHADOW_EVAL_STRICT:
- 0: shadow評価だけ失敗しても、結果取得Service全体は成功扱い
- 1: shadow評価エラーでServiceを停止
"""

from __future__ import annotations

import os
import runpy
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

RUN_EXHIBITION_SHADOW_EVAL = os.getenv(
    "RUN_EXHIBITION_SHADOW_EVAL", "1"
).strip() not in ("0", "false", "False", "no", "NO")

SHADOW_EVAL_STRICT = os.getenv(
    "SHADOW_EVAL_STRICT", "0"
).strip() in ("1", "true", "True", "yes", "YES")


def main() -> None:
    print(
        "✅ run_nightly_results_pg.py "
        "VERSION 2026-07-15 exhibition-shadow-eval",
        flush=True,
    )

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

    os.environ.setdefault("REPAIR_WORKERS", os.getenv("WORKERS", "4"))
    os.environ.setdefault(
        "REPAIR_ODDS_WORKERS",
        os.getenv("ODDS_WORKERS", "1"),
    )
    os.environ.setdefault(
        "REPAIR_SLEEP_SEC",
        os.getenv("SLEEP_SEC", "0.1"),
    )

    print(f"TARGET_DATE={target_date}", flush=True)
    print(
        f"RUN_EXHIBITION_SHADOW_EVAL={RUN_EXHIBITION_SHADOW_EVAL} "
        f"SHADOW_EVAL_STRICT={SHADOW_EVAL_STRICT}",
        flush=True,
    )
    print("Railway Postgres版：当日結果取得を開始します。", flush=True)

    base_dir = Path(__file__).resolve().parent
    repair_path = base_dir / "repair_month_all_pg.py"

    if not repair_path.exists():
        raise FileNotFoundError(
            f"repair_month_all_pg.py が見つかりません: {repair_path}"
        )

    # 先に確定結果を保存する。
    runpy.run_path(str(repair_path), run_name="__main__")

    if not RUN_EXHIBITION_SHADOW_EVAL:
        print(
            "展示shadow結果評価はRUN_EXHIBITION_SHADOW_EVAL=0のためスキップします。",
            flush=True,
        )
        print("=== nightly results + shadow evaluation 終了 ===", flush=True)
        return

    eval_path = base_dir / "evaluate_exhibition_shadow_results_pg.py"
    if not eval_path.exists():
        message = (
            "evaluate_exhibition_shadow_results_pg.py "
            f"が見つかりません: {eval_path}"
        )
        if SHADOW_EVAL_STRICT:
            raise FileNotFoundError(message)
        print(f"⚠️ {message}", flush=True)
        print(
            "結果取得は完了済みです。shadow評価だけをスキップします。",
            flush=True,
        )
        print("=== nightly results + shadow evaluation 終了 ===", flush=True)
        return

    print(
        "\n=== 展示shadow結果評価開始 ===",
        flush=True,
    )
    try:
        runpy.run_path(str(eval_path), run_name="__main__")
    except Exception as exc:
        print(
            f"⚠️ 展示shadow結果評価エラー: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        traceback.print_exc()

        if SHADOW_EVAL_STRICT:
            raise

        print(
            "結果取得は正常完了しています。"
            "shadow評価エラーは次回再実行で補修できます。",
            flush=True,
        )

    print("=== nightly results + shadow evaluation 終了 ===", flush=True)


if __name__ == "__main__":
    main()