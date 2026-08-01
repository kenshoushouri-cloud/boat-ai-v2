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


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() not in {
        "0", "false", "no", "off"
    }


RUN_CANDIDATE_SHADOW_EVAL = _env_flag("RUN_CANDIDATE_SHADOW_EVAL", "1")
RUN_CANDIDATE_SHADOW_REPORT = _env_flag("RUN_CANDIDATE_SHADOW_REPORT", "1")
RUN_EXHIBITION_SHADOW_EVAL = _env_flag("RUN_EXHIBITION_SHADOW_EVAL", "1")
RUN_EXHIBITION_SHADOW_REPORT = _env_flag("RUN_EXHIBITION_SHADOW_REPORT", "1")

SHADOW_EVAL_STRICT = os.getenv("SHADOW_EVAL_STRICT", "0").strip().lower() in {
    "1", "true", "yes", "on"
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
    print("", flush=True)
    print("=" * 80, flush=True)
    print(f"STAGE {stage_no} START: {stage_name} at {_now_jst()}", flush=True)
    print(f"SCRIPT: {script_path.name}", flush=True)
    print("=" * 80, flush=True)

    if not script_path.exists():
        message = f"{script_path.name} ãè¦ã¤ããã¾ãã: {script_path}"
        if strict:
            raise FileNotFoundError(message)
        print(f"â ï¸ {message}", flush=True)
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
        f"returncode={result.returncode} elapsed={elapsed:.1f}s at {_now_jst()}",
        flush=True,
    )
    print("=" * 80, flush=True)

    if result.returncode != 0:
        message = f"{stage_name} ãå¤±æãã¾ãããreturncode={result.returncode}"
        if strict:
            raise RuntimeError(message)
        print(f"â ï¸ {message}", flush=True)
        return False

    return True


def _fetch_target_race_ids(target_date: str) -> list[str]:
    rows = fetch_all(
        '''
        select race_id
        from v2_races
        where race_date = %s
        order by venue_id, race_no;
        ''',
        (target_date,),
    )
    return [str(row.get("race_id")) for row in rows if row.get("race_id")]


def main() -> None:
    print(
        "â run_nightly_results_pg.py VERSION "
        "2026-08-02 candidate-shadow-report-stage-v1",
        flush=True,
    )

    target_date = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")

    print(f"TARGET_DATE={target_date}", flush=True)
    print(
        f"RUN_CANDIDATE_SHADOW_EVAL={RUN_CANDIDATE_SHADOW_EVAL} "
        f"RUN_CANDIDATE_SHADOW_REPORT={RUN_CANDIDATE_SHADOW_REPORT} "
        f"RUN_EXHIBITION_SHADOW_EVAL={RUN_EXHIBITION_SHADOW_EVAL} "
        f"RUN_EXHIBITION_SHADOW_REPORT={RUN_EXHIBITION_SHADOW_REPORT} "
        f"SHADOW_EVAL_STRICT={SHADOW_EVAL_STRICT}",
        flush=True,
    )
    print("æ¬çªå¤å®ã»LINEéç¥ã»è³¼å¥å¦çã«ã¯å½±é¿ãã¾ããã", flush=True)

    base_dir = Path(__file__).resolve().parent

    common_env = {
        "TARGET_DATE": target_date,
        "SNAPSHOT_LABEL": os.getenv("SNAPSHOT_LABEL", "final_ab"),
        "SELECTOR_MODE": os.getenv("SELECTOR_MODE", "ab"),
        "UNIT_YEN": os.getenv("UNIT_YEN", "100"),
    }

    target_race_ids = _fetch_target_race_ids(target_date)
    print(
        f"nightly_target_races={len(target_race_ids)} "
        "(v2_raceså½æ¥éå¬åã®ã¿)",
        flush=True,
    )

    if target_race_ids:
        print("nightly target sample: " + ", ".join(target_race_ids[:12]), flush=True)
    else:
        print("å½æ¥ã®v2_racesã0ä»¶ã®ãããçµæåå¾ãã¹ã­ãããã¾ãã", flush=True)

    repair_env = {
        **common_env,
        "REPAIR_START_DATE": target_date,
        "REPAIR_END_DATE": target_date,
        "REPAIR_RACE_IDS": ",".join(target_race_ids),
        "REPAIR_DO_RACES": "0",
        "REPAIR_DO_RESULTS": "1",
        "REPAIR_DO_ODDS": "0",
        "REPAIR_WORKERS": os.getenv("REPAIR_WORKERS", os.getenv("WORKERS", "4")),
        "REPAIR_ODDS_WORKERS": os.getenv(
            "REPAIR_ODDS_WORKERS",
            os.getenv("ODDS_WORKERS", "1"),
        ),
        "REPAIR_SLEEP_SEC": os.getenv(
            "REPAIR_SLEEP_SEC",
            os.getenv("SLEEP_SEC", "0.1"),
        ),
    }

    if target_race_ids:
        _run_stage(
            stage_no=1,
            stage_name="å½æ¥çµæåå¾",
            script_path=base_dir / "repair_month_all_pg.py",
            env=repair_env,
            strict=True,
        )
    else:
        print("STAGE 1 SKIPPED: å½æ¥éå¬ã¬ã¼ã¹ãªã", flush=True)

    if RUN_CANDIDATE_SHADOW_EVAL:
        _run_stage(
            stage_no=2,
            stage_name="åè£ãã£ã«ã¿ã¼Shadowå½æ¥çµæè©ä¾¡",
            script_path=base_dir / "evaluate_candidate_filter_shadow_results_pg.py",
            env={
                **common_env,
                "CANDIDATE_SHADOW_EVAL_ENABLED": os.getenv(
                    "CANDIDATE_SHADOW_EVAL_ENABLED", "1"
                ),
                "CANDIDATE_SHADOW_EVAL_REEVALUATE": os.getenv(
                    "CANDIDATE_SHADOW_EVAL_REEVALUATE", "0"
                ),
            },
            strict=False,
        )
    else:
        print("STAGE 2 SKIPPED: RUN_CANDIDATE_SHADOW_EVAL=0", flush=True)

    if RUN_CANDIDATE_SHADOW_REPORT:
        _run_stage(
            stage_no=3,
            stage_name="åè£ãã£ã«ã¿ã¼Shadowç´¯ç©ã¬ãã¼ã",
            script_path=base_dir / "report_candidate_filter_shadow_performance_pg.py",
            env={
                **common_env,
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
            strict=False,
        )
    else:
        print("STAGE 3 SKIPPED: RUN_CANDIDATE_SHADOW_REPORT=0", flush=True)

    if RUN_EXHIBITION_SHADOW_EVAL:
        _run_stage(
            stage_no=4,
            stage_name="å±ç¤ºShadowå½æ¥çµæè©ä¾¡",
            script_path=base_dir / "evaluate_exhibition_shadow_results_pg.py",
            env=common_env,
            strict=SHADOW_EVAL_STRICT,
        )
    else:
        print("STAGE 4 SKIPPED: RUN_EXHIBITION_SHADOW_EVAL=0", flush=True)

    if RUN_EXHIBITION_SHADOW_REPORT:
        _run_stage(
            stage_no=5,
            stage_name="å±ç¤ºShadowç´¯ç©ã¬ãã¼ã",
            script_path=base_dir / "report_exhibition_shadow_performance_pg.py",
            env={
                **common_env,
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
            },
            strict=SHADOW_EVAL_STRICT,
        )
    else:
        print("STAGE 5 SKIPPED: RUN_EXHIBITION_SHADOW_REPORT=0", flush=True)

    print("", flush=True)
    print(
        "=== nightly results + candidate/exhibition shadow "
        "evaluation/report å®äº ===",
        flush=True,
    )


if __name__ == "__main__":
    main()