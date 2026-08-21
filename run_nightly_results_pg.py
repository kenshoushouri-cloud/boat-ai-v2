# -*- coding: utf-8 -*-
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
VERSION = "2026-08-21 nightly-observability-v8-candidate-robustness"


def flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() not in {"0", "false", "no", "off"}


RUN_CANDIDATE_SHADOW_EVAL = flag("RUN_CANDIDATE_SHADOW_EVAL", "1")
RUN_CANDIDATE_SHADOW_REPORT = flag("RUN_CANDIDATE_SHADOW_REPORT", "1")
RUN_CANDIDATE_ROBUSTNESS_REPORT = flag("RUN_CANDIDATE_ROBUSTNESS_REPORT", "1")
RUN_N02_FORWARD_REPORT = flag("RUN_N02_FORWARD_REPORT", "1")
RUN_N02_VARIANT_FORWARD_REPORT = flag("RUN_N02_VARIANT_FORWARD_REPORT", "1")
RUN_EXHIBITION_SHADOW_EVAL = flag("RUN_EXHIBITION_SHADOW_EVAL", "1")
RUN_EXHIBITION_SHADOW_REPORT = flag("RUN_EXHIBITION_SHADOW_REPORT", "1")
RUN_MOTOR2_FORWARD_EVAL = flag("RUN_MOTOR2_FORWARD_EVAL", "1")
RUN_MOTOR2_FORWARD_REPORT = flag("RUN_MOTOR2_FORWARD_REPORT", "1")
RUN_MOTOR2_ROBUSTNESS_REPORT = flag("RUN_MOTOR2_ROBUSTNESS_REPORT", "1")
RUN_N02_ROBUSTNESS_REPORT = flag("RUN_N02_ROBUSTNESS_REPORT", "1")
RUN_EXHIBITION_ROBUSTNESS_REPORT = flag("RUN_EXHIBITION_ROBUSTNESS_REPORT", "1")
SHADOW_EVAL_STRICT = flag("SHADOW_EVAL_STRICT", "0")


def now() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def run_stage(
    stage_no: int,
    stage_name: str,
    script_path: Path,
    env: Dict[str, str],
    strict: bool = True,
) -> bool:
    print("\n" + "=" * 80, flush=True)
    print(f"STAGE {stage_no} START: {stage_name} at {now()}", flush=True)
    print(f"SCRIPT: {script_path.name}", flush=True)
    print("=" * 80, flush=True)

    if not script_path.exists():
        msg = f"{script_path.name} が見つかりません: {script_path}"
        if strict:
            raise FileNotFoundError(msg)
        print(f"WARNING: {msg}", flush=True)
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

    print(f"--- STAGE {stage_no} OUTPUT: {stage_name} ---", flush=True)
    if result.stdout:
        print(result.stdout.rstrip(), flush=True)
    if result.stderr:
        print(f"--- STAGE {stage_no} STDERR: {stage_name} ---", flush=True)
        print(result.stderr.rstrip(), flush=True)

    print(
        f"STAGE {stage_no} END: {stage_name} "
        f"returncode={result.returncode} elapsed={elapsed:.1f}s at {now()}",
        flush=True,
    )
    print("=" * 80, flush=True)

    if result.returncode != 0:
        msg = f"{stage_name} が失敗しました。returncode={result.returncode}"
        if strict:
            raise RuntimeError(msg)
        print(f"WARNING: {msg}", flush=True)
        return False

    return True


def targets(target_date: str) -> list[str]:
    return [
        str(row.get("race_id"))
        for row in fetch_all(
            """
            select race_id
            from v2_races
            where race_date=%s
            order by venue_id,race_no
            """,
            (target_date,),
        )
        if row.get("race_id")
    ]


def main() -> None:
    print(f"OK run_nightly_results_pg.py VERSION {VERSION}", flush=True)

    target_date = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
    print(f"TARGET_DATE={target_date}", flush=True)
    print(
        f"RUN_MOTOR2_FORWARD_EVAL={RUN_MOTOR2_FORWARD_EVAL} "
        f"RUN_MOTOR2_FORWARD_REPORT={RUN_MOTOR2_FORWARD_REPORT}",
        flush=True,
    )
    print("本番判定・LINE通知・購入処理には影響しません。", flush=True)

    base_dir = Path(__file__).resolve().parent
    common = {
        "TARGET_DATE": target_date,
        "SNAPSHOT_LABEL": os.getenv("SNAPSHOT_LABEL", "final_ab"),
        "SELECTOR_MODE": os.getenv("SELECTOR_MODE", "ab"),
        "UNIT_YEN": os.getenv("UNIT_YEN", "100"),
    }

    race_ids = targets(target_date)
    print(
        f"nightly_target_races={len(race_ids)} "
        "(v2_races 当日開催分のみ)",
        flush=True,
    )

    repair_env = {
        **common,
        "REPAIR_START_DATE": target_date,
        "REPAIR_END_DATE": target_date,
        "REPAIR_RACE_IDS": ",".join(race_ids),
        "REPAIR_DO_RACES": "0",
        "REPAIR_DO_RESULTS": "1",
        "REPAIR_DO_ODDS": "0",
        "REPAIR_WORKERS": os.getenv("REPAIR_WORKERS", os.getenv("WORKERS", "4")),
        "REPAIR_ODDS_WORKERS": os.getenv(
            "REPAIR_ODDS_WORKERS", os.getenv("ODDS_WORKERS", "1")
        ),
        "REPAIR_SLEEP_SEC": os.getenv(
            "REPAIR_SLEEP_SEC", os.getenv("SLEEP_SEC", "0.1")
        ),
    }

    if race_ids:
        run_stage(
            1,
            "当日結果取得",
            base_dir / "repair_month_all_pg.py",
            repair_env,
            True,
        )

    if RUN_CANDIDATE_SHADOW_EVAL:
        run_stage(
            2,
            "候補フィルターShadow当日結果評価",
            base_dir / "evaluate_candidate_filter_shadow_results_pg.py",
            {
                **common,
                "CANDIDATE_SHADOW_EVAL_ENABLED": os.getenv(
                    "CANDIDATE_SHADOW_EVAL_ENABLED", "1"
                ),
                "CANDIDATE_SHADOW_EVAL_REEVALUATE": os.getenv(
                    "CANDIDATE_SHADOW_EVAL_REEVALUATE", "0"
                ),
            },
            False,
        )

    if RUN_CANDIDATE_SHADOW_REPORT:
        run_stage(
            3,
            "候補フィルターShadow累積レポート",
            base_dir / "report_candidate_filter_shadow_performance_pg.py",
            {
                **common,
                "CANDIDATE_SHADOW_REPORT_DAYS": os.getenv(
                    "CANDIDATE_SHADOW_REPORT_DAYS", "30"
                ),
                "CANDIDATE_SHADOW_READY_MIN_EVALUATED": os.getenv(
                    "CANDIDATE_SHADOW_READY_MIN_EVALUATED", "30"
                ),
                "CANDIDATE_SHADOW_READY_MIN_RULE_EVALUATED": os.getenv(
                    "CANDIDATE_SHADOW_READY_MIN_RULE_EVALUATED", "20"
                ),
                "CANDIDATE_SHADOW_READY_MIN_ROI": os.getenv(
                    "CANDIDATE_SHADOW_READY_MIN_ROI", "100"
                ),
                "CANDIDATE_SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT": os.getenv(
                    "CANDIDATE_SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT", "60"
                ),
            },
            False,
        )

    if RUN_N02_FORWARD_REPORT:
        run_stage(
            4,
            "N02 Forward専用レポート",
            base_dir / "report_n02_forward_performance_pg.py",
            {
                **common,
                "N02_FORWARD_START_DATE": os.getenv(
                    "N02_FORWARD_START_DATE", "2026-08-18"
                ),
                "N02_FORWARD_UNIT_YEN": os.getenv(
                    "N02_FORWARD_UNIT_YEN", os.getenv("UNIT_YEN", "100")
                ),
            },
            False,
        )

    if RUN_EXHIBITION_SHADOW_EVAL:
        run_stage(
            5,
            "展示Shadow当日結果評価",
            base_dir / "evaluate_exhibition_shadow_results_pg.py",
            common,
            SHADOW_EVAL_STRICT,
        )

    if RUN_EXHIBITION_SHADOW_REPORT:
        run_stage(
            6,
            "展示Shadow累積レポート",
            base_dir / "report_exhibition_shadow_performance_pg.py",
            {
                **common,
                "SHADOW_REPORT_DAYS": os.getenv("SHADOW_REPORT_DAYS", "30"),
                "SHADOW_READY_MIN_ROWS": os.getenv("SHADOW_READY_MIN_ROWS", "300"),
                "SHADOW_READY_MIN_BASE_CANDIDATES": os.getenv(
                    "SHADOW_READY_MIN_BASE_CANDIDATES", "20"
                ),
                "SHADOW_READY_MIN_SHADOW_CANDIDATES": os.getenv(
                    "SHADOW_READY_MIN_SHADOW_CANDIDATES", "20"
                ),
                "SHADOW_READY_MIN_ADDED": os.getenv("SHADOW_READY_MIN_ADDED", "10"),
                "SHADOW_READY_MIN_REMOVED": os.getenv(
                    "SHADOW_READY_MIN_REMOVED", "10"
                ),
                "SHADOW_READY_MAX_ROI_DROP_PT": os.getenv(
                    "SHADOW_READY_MAX_ROI_DROP_PT", "0"
                ),
                "SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT": os.getenv(
                    "SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT", "60"
                ),
            },
            SHADOW_EVAL_STRICT,
        )

    if RUN_N02_VARIANT_FORWARD_REPORT:
        run_stage(
            7,
            "N02_WIND_LT4 Variant Forward比較レポート",
            base_dir / "report_n02_windlt4_variants_forward_pg.py",
            {
                **common,
                "N02_VARIANT_FORWARD_START_DATE": os.getenv(
                    "N02_VARIANT_FORWARD_START_DATE", "2026-08-19"
                ),
                "N02_VARIANT_UNIT_YEN": os.getenv(
                    "N02_VARIANT_UNIT_YEN", os.getenv("UNIT_YEN", "100")
                ),
                "N02_VARIANT_REVIEW_TARGETS": os.getenv(
                    "N02_VARIANT_REVIEW_TARGETS", "10,30,50,100"
                ),
            },
            False,
        )

    if RUN_MOTOR2_FORWARD_EVAL:
        run_stage(
            8,
            "Motor2 Forward Shadow当日結果評価",
            base_dir / "evaluate_v24_motor2_forward_shadow_pg.py",
            {
                **common,
                "MOTOR2_EVAL_UNIT_YEN": os.getenv(
                    "MOTOR2_EVAL_UNIT_YEN", os.getenv("UNIT_YEN", "100")
                ),
                "RUN_CLASS": "",
                "WINDOW_NAME": "",
                "SNAPSHOT_KEY": "",
            },
            False,
        )

    if RUN_MOTOR2_FORWARD_REPORT:
        run_stage(
            9,
            "Motor2 Forward PRE/FINAL累積比較レポート",
            base_dir / "report_v24_motor2_forward_performance_pg.py",
            {
                **common,
                "MOTOR2_FORWARD_REPORT_START_DATE": os.getenv(
                    "MOTOR2_FORWARD_REPORT_START_DATE", "2026-08-20"
                ),
                "MOTOR2_FORWARD_UNIT_YEN": os.getenv(
                    "MOTOR2_FORWARD_UNIT_YEN", os.getenv("UNIT_YEN", "100")
                ),
                "MOTOR2_FORWARD_REVIEW_TARGETS": os.getenv(
                    "MOTOR2_FORWARD_REVIEW_TARGETS", "10,30,50,100"
                ),
                "MOTOR2_MID_VETO_REVIEW_TARGETS": os.getenv(
                    "MOTOR2_MID_VETO_REVIEW_TARGETS", "10,30,50,100"
                ),
            },
            False,
        )

    if RUN_MOTOR2_ROBUSTNESS_REPORT:
        run_stage(
            10,
            "Motor2 Forward分布robustnessレポート",
            base_dir / "report_v24_motor2_forward_robustness_pg.py",
            {
                **common,
                "MOTOR2_FORWARD_REPORT_START_DATE": os.getenv(
                    "MOTOR2_FORWARD_REPORT_START_DATE", "2026-08-20"
                ),
                "MOTOR2_FORWARD_UNIT_YEN": os.getenv(
                    "MOTOR2_FORWARD_UNIT_YEN", os.getenv("UNIT_YEN", "100")
                ),
            },
            False,
        )

    if RUN_N02_ROBUSTNESS_REPORT:
        run_stage(
            11,
            "N02 Forward分布robustnessレポート",
            base_dir / "report_n02_forward_robustness_pg.py",
            {
                **common,
                "N02_FORWARD_START_DATE": os.getenv(
                    "N02_FORWARD_START_DATE", "2026-08-18"
                ),
                "N02_FORWARD_UNIT_YEN": os.getenv(
                    "N02_FORWARD_UNIT_YEN", os.getenv("UNIT_YEN", "100")
                ),
            },
            False,
        )

    if RUN_EXHIBITION_ROBUSTNESS_REPORT:
        run_stage(
            12,
            "展示Shadow分布robustnessレポート",
            base_dir / "report_exhibition_shadow_robustness_pg.py",
            {
                **common,
                "SHADOW_REPORT_DAYS": os.getenv("SHADOW_REPORT_DAYS", "30"),
            },
            False,
        )

    if RUN_CANDIDATE_ROBUSTNESS_REPORT:
        run_stage(
            13,
            "S01-S05候補フィルターShadow分布robustnessレポート",
            base_dir / "report_candidate_filter_shadow_robustness_pg.py",
            {
                **common,
                "CANDIDATE_SHADOW_REPORT_DAYS": os.getenv(
                    "CANDIDATE_SHADOW_REPORT_DAYS", "30"
                ),
            },
            False,
        )

    print(
        "\n=== nightly results + Candidate/N02/N02-Variant/Exhibition/Motor2 "
        "shadow evaluation/report 完了 ===",
        flush=True,
    )


if __name__ == "__main__":
    main()
