# -*- coding: utf-8 -*-
"""
v25_final_realtime_pipeline_pg.py

Railway Postgres版。
直前収集 → 直前判定 → LINE最終通知 を一括実行します。
購入処理はありません。TEST_MODE=1ならLINE本文にも「購入しない」と明記します。

Railway Start Command:
    python v25_final_realtime_pipeline_pg.py

任意Variables:
    TARGET_DATE=YYYY-MM-DD
    SNAPSHOT_LABEL=final_ab
    DECISION_LABEL=final_ab
    SELECTOR_MODE=ab
    REQUIRE_EXHIBITION=0
    TEST_MODE=1
    DRY_RUN=0
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
DECISION_LABEL = os.getenv("DECISION_LABEL", SNAPSHOT_LABEL).strip() or SNAPSHOT_LABEL
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip() or "ab"
REQUIRE_EXHIBITION = os.getenv("REQUIRE_EXHIBITION", "0").strip()
TEST_MODE = os.getenv("TEST_MODE", "1").strip()
DRY_RUN = os.getenv("DRY_RUN", "0").strip()


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

    print("✅ v25_final_realtime_pipeline_pg.py VERSION 2026-07-05 railway-postgres", flush=True)
    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"DECISION_LABEL={DECISION_LABEL} SELECTOR_MODE={SELECTOR_MODE}",
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

    _run([sys.executable, "v21_realtime_collector_pg.py"], common)
    _run([sys.executable, "v22_realtime_decision_engine_pg.py"], common)
    _run([sys.executable, "v23_line_notifier_batch_pg.py"], common)

    print("\n=== v25 PG final realtime pipeline 完了 ===", flush=True)


if __name__ == "__main__":
    main()