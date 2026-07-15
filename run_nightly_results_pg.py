# -*- coding: utf-8 -*-
"""
run_nightly_results_pg.py

Railway Postgres版：当日結果取得。
各処理を子プロセスとして順番に実行し、ログを処理単位でまとめて表示します。

処理順:
1. repair_month_all_pg.py       当日結果取得
2. evaluate_exhibition_shadow_results_pg.py
3. report_exhibition_shadow_performance_pg.py

Start Command:
    python -u run_nightly_results_pg.py

任意Variables:
    RUN_EXHIBITION_SHADOW_EVAL=1
    RUN_EXHIBITION_SHADOW_REPORT=1
    SHADOW_EVAL_STRICT=0
    SNAPSHOT_LABEL=final_ab
    SELECTOR_MODE=ab
    UNIT_YEN=100
    SHADOW_REPORT_DAYS=30
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

JST = timezone(timedelta(hours=9))

RUN_EXHIBITION_SHADOW_EVAL = os.getenv(
    "RUN_EXHIBITION_SHADOW_EVAL", "1"
).strip() not in ("0", "false", "False", "no", "NO")

RUN_EXHIBITION_SHADOW_REPORT = os.getenv(
    "RUN_EXHIBITION_SHADOW_REPORT", "1"
).strip() not in ("0", "false", "False", "no", "NO")

SHADOW_EVAL_STRICT = os.getenv(
    "SHADOW_EVAL_STRICT", "0"
).strip() in ("1", "true", "True", "yes", "YES")


def _now_jst() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def _run_stage(
    *,
    stage_no: int,
    stage_name: str,
    script_path: Path,
    env: Dict[str, str],
    strict: bool = True,
) -> bool:
    """
    子プロセスのstdout/stderrを完了後にまとめて表示する。
    Railway上で別ステージのログが前後して見える問題を軽減する。
    """
    print("", flush=True)
    print("=" * 80, flush=True)
    print(
        f"STAGE {stage_no} START: {stage_name} "
        f"at {_now_jst()}",
        flush=True,
    )
    print(f"SCRIPT: {script_path.name}", flush=True)
    print("=" * 80, flush=True)

    if not script_path.exists():
        message = f"{script_path.name} が見つかりません: {script_path}"
        if strict:
            raise FileNotFoundError(message)
        print(f"⚠️ {message}", flush=True)
        print(f"STAGE {stage_no} SKIPPED: {stage_name}", flush=True)
        return False

    child_env = os.environ.copy()
    child_env.update(env)
    child_env["PYTHONUNBUFFERED"] = "1"

    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-u", str(script_path)],
        cwd=str(script_path.parent),
        env=child_env,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = time.monotonic() - started

    print(
        f"--- STAGE {stage_no} OUTPUT: {stage_name} ---",
        flush=True,
    )
    if result.stdout:
        print(result.stdout.rstrip(), flush=True)
    if result.stderr:
        print(
            f"--- STAGE {stage_no} STDERR: {stage_name} ---",
            flush=True,
        )
        print(result.stderr.rstrip(), flush=True)

    print(
        f"STAGE {stage_no} END: {stage_name} "
        f"returncode={result.returncode} elapsed={elapsed:.1f}s "
        f"at {_now_jst()}",
        flush=True,
    )
    print("=" * 80, flush=True)

    if result.returncode != 0:
        message = (
            f"{stage_name} が失敗しました。"
            f"returncode={result.returncode}"
        )
        if strict:
            raise RuntimeError(message)
        print(f"⚠️ {message}", flush=True)
        return False

    return True


def main() -> None:
    print(
        "✅ run_nightly_results_pg.py "
        "VERSION 2026-07-15 grouped-stage-logs",
        flush=True,
    )

    target_date = os.getenv("TARGET_DATE")
    if not target_date:
        target_date = datetime.now(JST).strftime("%Y-%m-%d")

    print(f"TARGET_DATE={target_date}", flush=True)
    print(
        f"RUN_EXHIBITION_SHADOW_EVAL={RUN_EXHIBITION_SHADOW_EVAL} "
        f"RUN_EXHIBITION_SHADOW_REPORT={RUN_EXHIBITION_SHADOW_REPORT} "
        f"SHADOW_EVAL_STRICT={SHADOW_EVAL_STRICT}",
        flush=True,
    )
    print(
        "本番判定・LINE通知・購入処理には影響しません。",
        flush=True,
    )

    base_dir = Path(__file__).resolve().parent

    common_env = {
        "TARGET_DATE": target_date,
        "SNAPSHOT_LABEL": os.getenv("SNAPSHOT_LABEL", "final_ab"),
        "SELECTOR_MODE": os.getenv("SELECTOR_MODE", "ab"),
        "UNIT_YEN": os.getenv("UNIT_YEN", "100"),
    }

    repair_env = {
        **common_env,
        "REPAIR_START_DATE": target_date,
        "REPAIR_END_DATE": target_date,
        "REPAIR_DO_RACES": "0",
        "REPAIR_DO_RESULTS": "1",
        "REPAIR_DO_ODDS": "0",
        "REPAIR_WORKERS": os.getenv(
            "REPAIR_WORKERS",
            os.getenv("WORKERS", "4"),
        ),
        "REPAIR_ODDS_WORKERS": os.getenv(
            "REPAIR_ODDS_WORKERS",
            os.getenv("ODDS_WORKERS", "1"),
        ),
        "REPAIR_SLEEP_SEC": os.getenv(
            "REPAIR_SLEEP_SEC",
            os.getenv("SLEEP_SEC", "0.1"),
        ),
    }

    _run_stage(
        stage_no=1,
        stage_name="当日結果取得",
        script_path=base_dir / "repair_month_all_pg.py",
        env=repair_env,
        strict=True,
    )

    if RUN_EXHIBITION_SHADOW_EVAL:
        _run_stage(
            stage_no=2,
            stage_name="展示shadow当日結果評価",
            script_path=(
                base_dir
                / "evaluate_exhibition_shadow_results_pg.py"
            ),
            env=common_env,
            strict=SHADOW_EVAL_STRICT,
        )
    else:
        print(
            "STAGE 2 SKIPPED: "
            "RUN_EXHIBITION_SHADOW_EVAL=0",
            flush=True,
        )

    if RUN_EXHIBITION_SHADOW_REPORT:
        report_env = {
            **common_env,
            "SHADOW_REPORT_DAYS": os.getenv(
                "SHADOW_REPORT_DAYS",
                "30",
            ),
            "SHADOW_READY_MIN_ROWS": os.getenv(
                "SHADOW_READY_MIN_ROWS",
                "300",
            ),
            "SHADOW_READY_MIN_BASE_CANDIDATES": os.getenv(
                "SHADOW_READY_MIN_BASE_CANDIDATES",
                "20",
            ),
            "SHADOW_READY_MIN_SHADOW_CANDIDATES": os.getenv(
                "SHADOW_READY_MIN_SHADOW_CANDIDATES",
                "20",
            ),
            "SHADOW_READY_MIN_ADDED": os.getenv(
                "SHADOW_READY_MIN_ADDED",
                "10",
            ),
            "SHADOW_READY_MIN_REMOVED": os.getenv(
                "SHADOW_READY_MIN_REMOVED",
                "10",
            ),
            "SHADOW_READY_MAX_ROI_DROP_PT": os.getenv(
                "SHADOW_READY_MAX_ROI_DROP_PT",
                "0",
            ),
        }

        _run_stage(
            stage_no=3,
            stage_name="展示shadow累積レポート",
            script_path=(
                base_dir
                / "report_exhibition_shadow_performance_pg.py"
            ),
            env=report_env,
            strict=SHADOW_EVAL_STRICT,
        )
    else:
        print(
            "STAGE 3 SKIPPED: "
            "RUN_EXHIBITION_SHADOW_REPORT=0",
            flush=True,
        )

    print("", flush=True)
    print(
        "=== nightly results + shadow evaluation/report 完了 ===",
        flush=True,
    )


if __name__ == "__main__":
    main()