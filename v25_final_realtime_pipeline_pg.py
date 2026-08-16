# -*- coding: utf-8 -*-
"""
v25_final_realtime_pipeline_pg.py

直前収集 → 本番判定 → 展示shadow保存 → LINE最終通知を一括実行します。

展示shadowは本番BUY/WATCH/SKIPやLINE通知対象を変更しません。
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
DECISION_LABEL = os.getenv("DECISION_LABEL", SNAPSHOT_LABEL).strip() or SNAPSHOT_LABEL
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip() or "ab"
REQUIRE_EXHIBITION = os.getenv("REQUIRE_EXHIBITION", "0").strip()
TEST_MODE = os.getenv("TEST_MODE", "1").strip()
DRY_RUN = os.getenv("DRY_RUN", "0").strip()
RUN_EXHIBITION_SHADOW = os.getenv(
    "RUN_EXHIBITION_SHADOW", "1"
).strip() not in ("0", "false", "False", "no", "NO")
TARGET_RACE_IDS_FILE = os.getenv("TARGET_RACE_IDS_FILE", "/tmp/v21_target_race_ids.txt").strip() or "/tmp/v21_target_race_ids.txt"
COLLECTION_RACE_IDS_FILE = os.getenv("COLLECTION_RACE_IDS_FILE", "/tmp/v21_collection_race_ids.txt").strip() or "/tmp/v21_collection_race_ids.txt"
RUN_N02_WINDLT4_SHADOW = os.getenv("RUN_N02_WINDLT4_SHADOW", "1").strip() not in ("0","false","False","no","NO")


def _require_settings() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")


def _run(cmd: list[str], extra_env: dict[str, str]) -> None:
    env = os.environ.copy()
    env.update(extra_env)

    print("\n" + "=" * 80, flush=True)
    print("RUN:", " ".join(cmd), flush=True)
    print(
        "ENV:",
        {
            k: env.get(k)
            for k in [
                "TARGET_DATE",
                "SNAPSHOT_LABEL",
                "DECISION_LABEL",
                "SELECTOR_MODE",
                "REQUIRE_EXHIBITION",
                "TEST_MODE",
                "DRY_RUN",
                "RUN_EXHIBITION_SHADOW",
                "EXHIBITION_SHADOW_WEIGHT",
            ]
        },
        flush=True,
    )
    print("=" * 80, flush=True)

    p = subprocess.run(cmd, env=env)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def main() -> None:
    _require_settings()

    print(
        "✅ v25_final_realtime_pipeline_pg.py "
        "VERSION 2026-08-16 targeted-final-shadow+n02-windlt4",
        flush=True,
    )
    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"DECISION_LABEL={DECISION_LABEL} SELECTOR_MODE={SELECTOR_MODE} "
        f"RUN_EXHIBITION_SHADOW={RUN_EXHIBITION_SHADOW} "
        f"RUN_N02_WINDLT4_SHADOW={RUN_N02_WINDLT4_SHADOW}",
        flush=True,
    )
    print("購入処理はありません。LINE通知のみです。", flush=True)

    common = {
        "TARGET_DATE": TARGET_DATE,
        "SNAPSHOT_LABEL": SNAPSHOT_LABEL,
        "DECISION_LABEL": DECISION_LABEL,
        "SELECTOR_MODE": SELECTOR_MODE,
        "REQUIRE_EXHIBITION": REQUIRE_EXHIBITION,
        "TEST_MODE": TEST_MODE,
        "DRY_RUN": DRY_RUN,
    }

    target_file = Path(TARGET_RACE_IDS_FILE)
    collection_file = Path(COLLECTION_RACE_IDS_FILE)
    target_file.write_text("", encoding="utf-8")
    collection_file.write_text("", encoding="utf-8")

    _run(
        [sys.executable, "v21_realtime_collector_pg.py"],
        {
            **common,
            "TARGET_RACE_IDS_FILE": TARGET_RACE_IDS_FILE,
            "COLLECTION_RACE_IDS_FILE": COLLECTION_RACE_IDS_FILE,
        },
    )

    target_race_ids = target_file.read_text(encoding="utf-8").strip() if target_file.exists() else ""
    collection_race_ids = collection_file.read_text(encoding="utf-8").strip() if collection_file.exists() else ""

    target_count = len([x for x in target_race_ids.split(",") if x.strip()])
    collection_count = len([x for x in collection_race_ids.split(",") if x.strip()])
    print(
        f"TARGET_RACE_IDS loaded: {target_count} races / "
        f"COLLECTION_RACE_IDS loaded: {collection_count} races",
        flush=True,
    )

    if RUN_N02_WINDLT4_SHADOW:
        _run(
            [sys.executable, "collect_n02_windlt4_final_shadow_pg.py"],
            {**common, "COLLECTION_RACE_IDS": collection_race_ids},
        )
    else:
        print("N02_WIND_LT4 shadowはRUN_N02_WINDLT4_SHADOW=0のためスキップします。", flush=True)

    targeted_common = {**common, "TARGET_RACE_IDS": target_race_ids}

    _run([sys.executable, "run_v22_targeted_pg.py"], targeted_common)

    if RUN_EXHIBITION_SHADOW:
        _run(
            [sys.executable, "v22_exhibition_shadow_pg.py"],
            {
                **targeted_common,
                "EXHIBITION_SHADOW_WEIGHT": os.getenv(
                    "EXHIBITION_SHADOW_WEIGHT", "0.20"
                ),
            },
        )
    else:
        print("展示shadowはRUN_EXHIBITION_SHADOW=0のためスキップします。", flush=True)

    _run([sys.executable, "v23_line_notifier_batch_pg.py"], targeted_common)

    print("\n=== v25 PG final realtime pipeline 完了 ===", flush=True)


if __name__ == "__main__":
    main()