# -*- coding: utf-8 -*-
"""
run_nightly_results_pg.py

Railway Postgres版：当日結果取得。
各処理を子プロセスとして順番に実行し、ログを処理単位でまとめて表示します。

処理順:
1. repair_month_all_pg.py
   当日結果取得
2. evaluate_candidate_filter_shadow_results_pg.py
   候補フィルターShadow当日結果評価
3. report_candidate_filter_shadow_performance_pg.py
   候補フィルターShadow累積レポート
4. report_n02_forward_performance_pg.py
   N02 Forward専用レポート
5. evaluate_exhibition_shadow_results_pg.py
   展示Shadow当日結果評価
6. report_exhibition_shadow_performance_pg.py
   展示Shadow累積レポート
7. report_n02_windlt4_variants_forward_pg.py
   N02_WIND_LT4 Variant Forward比較レポート

Start Command:
    python -u run_nightly_results_pg.py

任意Variables:
    RUN_CANDIDATE_SHADOW_EVAL=1
    RUN_CANDIDATE_SHADOW_REPORT=1
    RUN_N02_FORWARD_REPORT=1
    RUN_N02_VARIANT_FORWARD_REPORT=1

    CANDIDATE_SHADOW_EVAL_ENABLED=1
    CANDIDATE_SHADOW_EVAL_REEVALUATE=0

    CANDIDATE_SHADOW_REPORT_DAYS=30
    CANDIDATE_SHADOW_READY_MIN_EVALUATED=30
    CANDIDATE_SHADOW_READY_MIN_RULE_EVALUATED=20
    CANDIDATE_SHADOW_READY_MIN_ROI=100
    CANDIDATE_SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT=60

    N02_FORWARD_START_DATE=2026-08-18
    N02_FORWARD_UNIT_YEN=100
    N02_VARIANT_FORWARD_START_DATE=2026-08-19
    N02_VARIANT_UNIT_YEN=100
    N02_VARIANT_REVIEW_TARGETS=10,30,50,100

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

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))

VERSION = "2026-08-19 n02-variant-forward-stage-v4"


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


RUN_CANDIDATE_SHADOW_EVAL = _env_flag(
    "RUN_CANDIDATE_SHADOW_EVAL",
    "1",
)

RUN_CANDIDATE_SHADOW_REPORT = _env_flag(
    "RUN_CANDIDATE_SHADOW_REPORT",
    "1",
)

RUN_N02_FORWARD_REPORT = _env_flag(
    "RUN_N02_FORWARD_REPORT",
    "1",
)

RUN_N02_VARIANT_FORWARD_REPORT = _env_flag(
    "RUN_N02_VARIANT_FORWARD_REPORT",
    "1",
)

RUN_EXHIBITION_SHADOW_EVAL = _env_flag(
    "RUN_EXHIBITION_SHADOW_EVAL",
    "1",
)

RUN_EXHIBITION_SHADOW_REPORT = _env_flag(
    "RUN_EXHIBITION_SHADOW_REPORT",
    "1",
)

SHADOW_EVAL_STRICT = os.getenv(
    "SHADOW_EVAL_STRICT",
    "0",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


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
        message = (
            f"{script_path.name} が見つかりません: "
            f"{script_path}"
        )
        if strict:
            raise FileNotFoundError(message)

        print(f"⚠️ {message}", flush=True)
        print(
            f"STAGE {stage_no} SKIPPED: {stage_name}",
            flush=True,
        )
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
            f"--- STAGE {stage_no} STDERR: "
            f"{stage_name} ---",
            flush=True,
        )
        print(result.stderr.rstrip(), flush=True)

    print(
        f"STAGE {stage_no} END: {stage_name} "
        f"returncode={result.returncode} "
        f"elapsed={elapsed:.1f}s "
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


def _fetch_target_race_ids(target_date: str) -> list[str]:
    """
    当日のv2_racesに存在する開催レースだけを取得する。
    """
    rows = fetch_all(
        """
        select race_id
        from v2_races
        where race_date = %s
        order by venue_id, race_no;
        """,
        (target_date,),
    )

    return [
        str(row.get("race_id"))
        for row in rows
        if row.get("race_id")
    ]


def main() -> None:
    print(
        f"✅ run_nightly_results_pg.py VERSION {VERSION}",
        flush=True,
    )

    target_date = os.getenv("TARGET_DATE")
    if not target_date:
        target_date = datetime.now(JST).strftime("%Y-%m-%d")

    print(f"TARGET_DATE={target_date}", flush=True)
    print(
        f"RUN_CANDIDATE_SHADOW_EVAL="
        f"{RUN_CANDIDATE_SHADOW_EVAL} "
        f"RUN_CANDIDATE_SHADOW_REPORT="
        f"{RUN_CANDIDATE_SHADOW_REPORT} "
        f"RUN_N02_FORWARD_REPORT="
        f"{RUN_N02_FORWARD_REPORT} "
        f"RUN_N02_VARIANT_FORWARD_REPORT="
        f"{RUN_N02_VARIANT_FORWARD_REPORT} "
        f"RUN_EXHIBITION_SHADOW_EVAL="
        f"{RUN_EXHIBITION_SHADOW_EVAL} "
        f"RUN_EXHIBITION_SHADOW_REPORT="
        f"{RUN_EXHIBITION_SHADOW_REPORT} "
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
        "SNAPSHOT_LABEL": os.getenv(
            "SNAPSHOT_LABEL",
            "final_ab",
        ),
        "SELECTOR_MODE": os.getenv(
            "SELECTOR_MODE",
            "ab",
        ),
        "UNIT_YEN": os.getenv(
            "UNIT_YEN",
            "100",
        ),
    }

    target_race_ids = _fetch_target_race_ids(target_date)

    print(
        f"nightly_target_races={len(target_race_ids)} "
        "(v2_races当日開催分のみ)",
        flush=True,
    )

    if target_race_ids:
        print(
            "nightly target sample: "
            + ", ".join(target_race_ids[:12]),
            flush=True,
        )
    else:
        print(
            "当日のv2_racesが0件のため、"
            "結果取得をスキップします。",
            flush=True,
        )

    repair_env = {
        **common_env,
        "REPAIR_START_DATE": target_date,
        "REPAIR_END_DATE": target_date,
        "REPAIR_RACE_IDS": ",".join(target_race_ids),
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

    # --------------------------------------------------------
    # STAGE 1: 当日結果取得
    # --------------------------------------------------------
    if target_race_ids:
        _run_stage(
            stage_no=1,
            stage_name="当日結果取得",
            script_path=(
                base_dir / "repair_month_all_pg.py"
            ),
            env=repair_env,
            strict=True,
        )
    else:
        print(
            "STAGE 1 SKIPPED: 当日開催レースなし",
            flush=True,
        )

    # --------------------------------------------------------
    # STAGE 2: 候補フィルターShadow当日結果評価
    # --------------------------------------------------------
    if RUN_CANDIDATE_SHADOW_EVAL:
        candidate_shadow_env = {
            **common_env,
            "CANDIDATE_SHADOW_EVAL_ENABLED": os.getenv(
                "CANDIDATE_SHADOW_EVAL_ENABLED",
                "1",
            ),
            "CANDIDATE_SHADOW_EVAL_REEVALUATE": os.getenv(
                "CANDIDATE_SHADOW_EVAL_REEVALUATE",
                "0",
            ),
        }

        _run_stage(
            stage_no=2,
            stage_name="候補フィルターShadow当日結果評価",
            script_path=(
                base_dir
                / "evaluate_candidate_filter_shadow_results_pg.py"
            ),
            env=candidate_shadow_env,
            strict=False,
        )
    else:
        print(
            "STAGE 2 SKIPPED: "
            "RUN_CANDIDATE_SHADOW_EVAL=0",
            flush=True,
        )

    # --------------------------------------------------------
    # STAGE 3: 候補フィルターShadow累積レポート
    # --------------------------------------------------------
    if RUN_CANDIDATE_SHADOW_REPORT:
        candidate_report_env = {
            **common_env,
            "CANDIDATE_SHADOW_REPORT_DAYS": os.getenv(
                "CANDIDATE_SHADOW_REPORT_DAYS",
                "30",
            ),
            "CANDIDATE_SHADOW_READY_MIN_EVALUATED": os.getenv(
                "CANDIDATE_SHADOW_READY_MIN_EVALUATED",
                "30",
            ),
            "CANDIDATE_SHADOW_READY_MIN_RULE_EVALUATED": os.getenv(
                "CANDIDATE_SHADOW_READY_MIN_RULE_EVALUATED",
                "20",
            ),
            "CANDIDATE_SHADOW_READY_MIN_ROI": os.getenv(
                "CANDIDATE_SHADOW_READY_MIN_ROI",
                "100",
            ),
            "CANDIDATE_SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT": os.getenv(
                "CANDIDATE_SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT",
                "60",
            ),
        }

        _run_stage(
            stage_no=3,
            stage_name="候補フィルターShadow累積レポート",
            script_path=(
                base_dir
                / "report_candidate_filter_shadow_performance_pg.py"
            ),
            env=candidate_report_env,
            strict=False,
        )
    else:
        print(
            "STAGE 3 SKIPPED: "
            "RUN_CANDIDATE_SHADOW_REPORT=0",
            flush=True,
        )

    # --------------------------------------------------------
    # STAGE 4: N02 Forward専用レポート
    # --------------------------------------------------------
    if RUN_N02_FORWARD_REPORT:
        n02_forward_env = {
            **common_env,
            "N02_FORWARD_START_DATE": os.getenv(
                "N02_FORWARD_START_DATE",
                "2026-08-18",
            ),
            "N02_FORWARD_UNIT_YEN": os.getenv(
                "N02_FORWARD_UNIT_YEN",
                os.getenv("UNIT_YEN", "100"),
            ),
        }

        _run_stage(
            stage_no=4,
            stage_name="N02 Forward専用レポート",
            script_path=(
                base_dir
                / "report_n02_forward_performance_pg.py"
            ),
            env=n02_forward_env,
            strict=False,
        )
    else:
        print(
            "STAGE 4 SKIPPED: "
            "RUN_N02_FORWARD_REPORT=0",
            flush=True,
        )

    # --------------------------------------------------------
    # STAGE 5: 展示Shadow当日結果評価
    # --------------------------------------------------------
    if RUN_EXHIBITION_SHADOW_EVAL:
        _run_stage(
            stage_no=5,
            stage_name="展示Shadow当日結果評価",
            script_path=(
                base_dir
                / "evaluate_exhibition_shadow_results_pg.py"
            ),
            env=common_env,
            strict=SHADOW_EVAL_STRICT,
        )
    else:
        print(
            "STAGE 5 SKIPPED: "
            "RUN_EXHIBITION_SHADOW_EVAL=0",
            flush=True,
        )

    # --------------------------------------------------------
    # STAGE 6: 展示Shadow累積レポート
    # --------------------------------------------------------
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
            stage_no=6,
            stage_name="展示Shadow累積レポート",
            script_path=(
                base_dir
                / "report_exhibition_shadow_performance_pg.py"
            ),
            env=report_env,
            strict=SHADOW_EVAL_STRICT,
        )
    else:
        print(
            "STAGE 6 SKIPPED: "
            "RUN_EXHIBITION_SHADOW_REPORT=0",
            flush=True,
        )

    # --------------------------------------------------------
    # STAGE 7: N02_WIND_LT4 Variant Forward比較レポート
    # --------------------------------------------------------
    if RUN_N02_VARIANT_FORWARD_REPORT:
        n02_variant_forward_env = {
            **common_env,
            "N02_VARIANT_FORWARD_START_DATE": os.getenv(
                "N02_VARIANT_FORWARD_START_DATE",
                "2026-08-19",
            ),
            "N02_VARIANT_UNIT_YEN": os.getenv(
                "N02_VARIANT_UNIT_YEN",
                os.getenv("UNIT_YEN", "100"),
            ),
            "N02_VARIANT_REVIEW_TARGETS": os.getenv(
                "N02_VARIANT_REVIEW_TARGETS",
                "10,30,50,100",
            ),
        }

        _run_stage(
            stage_no=7,
            stage_name="N02_WIND_LT4 Variant Forward比較レポート",
            script_path=(
                base_dir
                / "report_n02_windlt4_variants_forward_pg.py"
            ),
            env=n02_variant_forward_env,
            strict=False,
        )
    else:
        print(
            "STAGE 7 SKIPPED: "
            "RUN_N02_VARIANT_FORWARD_REPORT=0",
            flush=True,
        )

    print("", flush=True)
    print(
        "=== nightly results + candidate/N02/N02-variant/exhibition "
        "shadow evaluation/report 完了 ===",
        flush=True,
    )


if __name__ == "__main__":
    main()