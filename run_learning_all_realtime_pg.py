# -*- coding: utf-8 -*-
"""
run_learning_all_realtime_pg.py

学習データ蓄積専用ラッパー。

目的:
- 本番の候補判定・LINE通知を一切変更せず、
  締切前ウィンドウに入った「全レース」の直前情報を保存する。
- v21_realtime_collector_pg.py を再利用する。
- 本番判定用 TARGET_RACE_IDS_FILE を上書きしない。

保存される主な情報（v21側）:
- 展示タイム / 展示ST / 展示進入 / チルト
- 気象 / 気温 / 水温 / 風速 / 風向 / 波高
- 選手体重 / 調整体重 / 部品交換 / 前走ST / 前走着順等
- 直前三連単オッズ / 市場順位 / オッズ変化
- race condition / racer condition

重要:
- LINE通知なし
- 本番判定なし
- 購入処理なし
- 本番用 /tmp/v21_target_race_ids.txt は変更しない

Start Command:
    python -u run_learning_all_realtime_pg.py

推奨Variables:
    LEARNING_SNAPSHOT_LABEL=learning_all
    LEARNING_WINDOW_BEFORE_MIN=30
    LEARNING_WINDOW_AFTER_MIN=0
    LEARNING_REALTIME_SLEEP_SEC=0.10

既存:
    DATABASE_URL
    TARGET_DATE  # 未指定ならv21側でJST当日
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

VERSION = "2026-08-15 learning-all-realtime-v1"


def _bool(v: str, default: bool = True) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    base_dir = Path(__file__).resolve().parent
    collector = base_dir / "v21_realtime_collector_pg.py"

    if not collector.exists():
        raise FileNotFoundError(
            f"v21_realtime_collector_pg.py が見つかりません: {collector}"
        )

    enabled = _bool(os.getenv("LEARNING_ALL_ENABLED", "1"), True)
    if not enabled:
        print("LEARNING_ALL_ENABLED=0: skip", flush=True)
        return

    env = os.environ.copy()

    # 本番判定とは完全に分離する。
    env["COLLECT_SCOPE"] = "all"
    env["SNAPSHOT_LABEL"] = (
        os.getenv("LEARNING_SNAPSHOT_LABEL", "learning_all").strip()
        or "learning_all"
    )

    # 全日一括ではなく、締切前ウィンドウだけを収集。
    # final-checkと同等の頻度で実行すれば全レースを順次拾える。
    env["FINAL_DEADLINE_FILTER"] = "1"
    env["FINAL_WINDOW_BEFORE_MIN"] = os.getenv(
        "LEARNING_WINDOW_BEFORE_MIN", "30"
    ).strip() or "30"
    env["FINAL_WINDOW_AFTER_MIN"] = os.getenv(
        "LEARNING_WINDOW_AFTER_MIN", "0"
    ).strip() or "0"

    # 本番の判定対象race_idファイルを絶対に上書きしない。
    env["TARGET_RACE_IDS_FILE"] = os.getenv(
        "LEARNING_TARGET_RACE_IDS_FILE",
        "/tmp/v21_learning_all_target_race_ids.txt",
    ).strip() or "/tmp/v21_learning_all_target_race_ids.txt"

    env["REALTIME_SLEEP_SEC"] = os.getenv(
        "LEARNING_REALTIME_SLEEP_SEC", "0.10"
    ).strip() or "0.10"

    # 明示的な単一race指定が本番Serviceから残っていても引き継がない。
    env.pop("TARGET_RACE_ID", None)

    print(
        f"✅ run_learning_all_realtime_pg.py VERSION {VERSION}",
        flush=True,
    )
    print("学習用全レース直前収集。LINE通知・本番判定・購入処理なし。", flush=True)
    print(
        "ENV "
        f"TARGET_DATE={env.get('TARGET_DATE', '(JST today)')} "
        f"COLLECT_SCOPE={env['COLLECT_SCOPE']} "
        f"SNAPSHOT_LABEL={env['SNAPSHOT_LABEL']} "
        f"FINAL_WINDOW_BEFORE_MIN={env['FINAL_WINDOW_BEFORE_MIN']} "
        f"FINAL_WINDOW_AFTER_MIN={env['FINAL_WINDOW_AFTER_MIN']} "
        f"TARGET_RACE_IDS_FILE={env['TARGET_RACE_IDS_FILE']}",
        flush=True,
    )

    p = subprocess.run(
        [sys.executable, "-u", str(collector)],
        env=env,
        cwd=str(base_dir),
    )
    if p.returncode != 0:
        raise SystemExit(p.returncode)

    print("=== learning all realtime collection finished ===", flush=True)


if __name__ == "__main__":
    main()