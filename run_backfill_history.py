# -*- coding: utf-8 -*-
import os
import sys
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(__file__))

from db.client import select_where
from app.jobs.race_seed_job import run_race_seed_job
from app.jobs.result_fetch_job import run_result_fetch_job

try:
    from app.jobs.exhibition_seed_job import run_exhibition_seed_job_backfill
    HAS_EXHIBITION = True
    print("✅ exhibition_seed_job ロード成功")
except ImportError:
    HAS_EXHIBITION = False
    print("⚠️ exhibition_seed_job なし → スキップ")


DEFAULT_OTHER_VENUES = [
    "02", "03", "04", "05",
    "07", "08", "09", "10", "11",
    "13", "14", "15", "16", "17",
    "19", "20", "21", "22", "23",
]


def _normalize_venues(venue_ids=None):
    """
    優先順位:
    1. 引数 venue_ids
    2. BACKFILL_VENUES
    3. TARGET_VENUES
    4. DEFAULT_OTHER_VENUES
    """
    if venue_ids is None:
        env = (
            os.environ.get("BACKFILL_VENUES")
            or os.environ.get("TARGET_VENUES")
            or ""
        ).strip()

        if env:
            venue_ids = [
                v.strip()
                for v in env.split(",")
                if v.strip()
            ]
        else:
            venue_ids = DEFAULT_OTHER_VENUES

    if isinstance(venue_ids, str):
        venue_ids = [
            v.strip()
            for v in venue_ids.split(",")
            if v.strip()
        ]

    return [str(v).zfill(2) for v in venue_ids]


def daterange(start_date, end_date):
    cur = start_date
    while cur <= end_date:
        yield cur
        cur += timedelta(days=1)


def _is_venue_day_saved(target_date_hyphen, venue_id):
    races = select_where(
        "v2_races",
        {
            "race_date": target_date_hyphen,
            "venue_id": venue_id,
        },
        limit=1,
    )

    return bool(races)


def _is_already_saved(target_date_hyphen, venue_ids):
    """
    skip_existing=True 用。
    対象場すべてに最低1件レースが入っていれば取得済み扱い。
    ただし通常の補修では skip_existing=False 推奨。
    """
    target_venues = _normalize_venues(venue_ids)

    for venue_id in target_venues:
        if not _is_venue_day_saved(target_date_hyphen, venue_id):
            return False

    return True


def _process_one_day(
    target_date_hyphen,
    target_date_plain,
    sleep_sec,
    do_race,
    do_exhibition,
    do_odds,
    do_results,
    venue_ids,
    skip_existing,
):
    target_venues = _normalize_venues(venue_ids)

    if skip_existing and _is_already_saved(target_date_hyphen, target_venues):
        print(f"⏭️  {target_date_hyphen} スキップ(対象場取得済み)")
        return target_date_hyphen, True

    print(f"\n=== {target_date_hyphen} 開始 ===")
    print("対象場:", ",".join(target_venues))

    day_ok = True
    step_results = []

    if do_race:
        try:
            run_race_seed_job(
                target_date_hyphen,
                venue_ids=target_venues,
            )
            step_results.append("  [✅ race]")
        except Exception as e:
            day_ok = False
            step_results.append(f"  [❌ race] {e}")

        time.sleep(sleep_sec)

    if do_exhibition and HAS_EXHIBITION:
        try:
            # exhibition側が venue_ids 未対応ならここは必要に応じて後で拡張
            run_exhibition_seed_job_backfill(target_date_hyphen)
            step_results.append("  [✅ exhibition]")
        except Exception as e:
            day_ok = False
            step_results.append(f"  [❌ exhibition] {e}")

        time.sleep(sleep_sec)

    elif do_exhibition and not HAS_EXHIBITION:
        step_results.append("  [⚠️ exhibition スキップ]")

    if do_odds:
        try:
            # odds側は今回は使わない想定。
            # 必要になったら venue_ids 対応版にする。
            from app.jobs.odds_seed_job import run_odds_seed_job
            run_odds_seed_job(target_date_hyphen)
            step_results.append("  [✅ odds]")
        except Exception as e:
            day_ok = False
            step_results.append(f"  [❌ odds] {e}")

        time.sleep(sleep_sec)

    if do_results:
        try:
            run_result_fetch_job(
                target_date_plain,
                debug_first_n=0,
                venue_ids=target_venues,
            )
            step_results.append("  [✅ results]")
        except Exception as e:
            day_ok = False
            step_results.append(f"  [❌ results] {e}")

        time.sleep(sleep_sec)

    status = "✅ OK" if day_ok else "❌ NG"
    print(f"=== {target_date_hyphen} 終了 {status} ===")

    for msg in step_results:
        print(msg)

    return target_date_hyphen, day_ok


def _run_batch(
    date_list,
    sleep_sec,
    max_workers,
    do_race,
    do_exhibition,
    do_odds,
    do_results,
    venue_ids,
    skip_existing,
):
    ok_list = []
    ng_list = []

    target_venues = _normalize_venues(venue_ids)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _process_one_day,
                hyphen,
                plain,
                sleep_sec,
                do_race,
                do_exhibition,
                do_odds,
                do_results,
                target_venues,
                skip_existing,
            ): hyphen
            for hyphen, plain in date_list
        }

        for future in as_completed(futures):
            try:
                date_str, day_ok = future.result()
                if day_ok:
                    ok_list.append(date_str)
                else:
                    ng_list.append(date_str)

            except Exception as e:
                print("予期しないエラー:", e)
                ng_list.append(futures[future])

    return ok_list, ng_list


def run_history_backfill(
    start_date_str,
    end_date_str,
    sleep_sec=0.5,
    max_workers=3,
    max_retry=3,
    retry_wait_sec=10.0,
    do_race=True,
    do_exhibition=True,
    do_odds=True,
    do_results=True,
    venue_ids=None,
    skip_existing=False,
):
    target_venues = _normalize_venues(venue_ids)

    print("=== 履歴バックフィル開始 ===")
    print("期間:", start_date_str, "→", end_date_str)
    print("対象場:", ",".join(target_venues))
    print("並列数:", max_workers)
    print("リトライ上限:", max_retry)
    print("do_race:", do_race)
    print("do_exhibition:", do_exhibition)
    print("do_odds:", do_odds)
    print("do_results:", do_results)
    print("skip_existing:", skip_existing)
    print("ENV BACKFILL_VENUES:", os.environ.get("BACKFILL_VENUES"))
    print("ENV TARGET_VENUES:", os.environ.get("TARGET_VENUES"))

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    date_list = [
        (d.strftime("%Y-%m-%d"), d.strftime("%Y%m%d"))
        for d in daterange(start_date, end_date)
    ]

    print("対象日数:", len(date_list))

    ok_list, ng_list = _run_batch(
        date_list=date_list,
        sleep_sec=sleep_sec,
        max_workers=max_workers,
        do_race=do_race,
        do_exhibition=do_exhibition,
        do_odds=do_odds,
        do_results=do_results,
        venue_ids=target_venues,
        skip_existing=skip_existing,
    )

    retry_count = 0

    while ng_list and retry_count < max_retry:
        retry_count += 1

        print(f"\n{'=' * 40}")
        print(f"🔁 リトライ {retry_count}/{max_retry} 対象: {len(ng_list)}日")
        print("失敗日:", sorted(ng_list))
        print(f"{retry_wait_sec}秒待機...")
        print(f"{'=' * 40}")

        time.sleep(retry_wait_sec)

        retry_date_list = [
            (d, d.replace("-", ""))
            for d in sorted(ng_list)
        ]

        retry_ok, ng_list = _run_batch(
            date_list=retry_date_list,
            sleep_sec=sleep_sec,
            max_workers=max_workers,
            do_race=do_race,
            do_exhibition=do_exhibition,
            do_odds=do_odds,
            do_results=do_results,
            venue_ids=target_venues,
            skip_existing=skip_existing,
        )

        ok_list.extend(retry_ok)

    print("\n=== 履歴バックフィル終了 ===")
    print("対象日数:", len(date_list))
    print("成功日数:", len(ok_list))
    print("失敗日数:", len(ng_list))

    if ng_list:
        print("\n⚠️ 最終的に失敗した日:")
        for d in sorted(ng_list):
            print(" ", d)
    else:
        print("\n🎉 全日成功!")


def main():
    start_date = os.environ.get("BACKFILL_START_DATE", "2025-05-01")
    end_date = os.environ.get("BACKFILL_END_DATE", "2025-05-31")
    venues = _normalize_venues(None)

    run_history_backfill(
        start_date_str=start_date,
        end_date_str=end_date,
        sleep_sec=0.5,
        max_workers=4,
        max_retry=3,
        retry_wait_sec=10.0,
        do_race=True,
        do_exhibition=False,
        do_odds=False,
        do_results=True,
        venue_ids=venues,
        skip_existing=False,
    )


if __name__ == "__main__":
    main()

    if os.environ.get("KEEP_ALIVE_AFTER_JOB", "").lower() in {"1", "true", "yes", "on"}:
        print("✅ バックフィル完了 → 待機モード")
        while True:
            time.sleep(3600)