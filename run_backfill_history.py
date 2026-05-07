# -*- coding: utf-8 -*-
import os
import sys
import time
import inspect
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(__file__))

from db.client import select_where
from app.jobs.race_seed_job import run_race_seed_job
from app.jobs.result_fetch_job import run_result_fetch_job

try:
    from app.jobs.odds_seed_job import run_odds_seed_job
    HAS_ODDS = True
except ImportError:
    HAS_ODDS = False
    print("⚠️ odds_seed_job なし → スキップ")

try:
    from app.jobs.exhibition_seed_job import run_exhibition_seed_job_backfill
    HAS_EXHIBITION = True
    print("✅ exhibition_seed_job ロード成功")
except ImportError:
    HAS_EXHIBITION = False
    print("⚠️ exhibition_seed_job なし → スキップ")


def daterange(start_date, end_date):
    cur = start_date
    while cur <= end_date:
        yield cur
        cur += timedelta(days=1)


def _call_job(func, target_date, venue_ids=None, **kwargs):
    """
    job側が venue_ids 引数に対応していれば渡す。
    未対応なら従来通り target_date だけで呼ぶ。
    """
    sig = inspect.signature(func)
    params = sig.parameters

    call_kwargs = {}

    if "venue_ids" in params:
        call_kwargs["venue_ids"] = venue_ids

    for k, v in kwargs.items():
        if k in params:
            call_kwargs[k] = v

    if call_kwargs:
        return func(target_date, **call_kwargs)

    return func(target_date)


def _date_has_any_data_for_venues(target_date_hyphen, venue_ids):
    """
    指定日の指定場に race が入っているかだけを見る。
    odds有無ではスキップ判定しない。
    """
    if not venue_ids:
        return False

    for venue_id in venue_ids:
        races = select_where(
            "v2_races",
            {
                "race_date": target_date_hyphen,
                "venue_id": str(venue_id).zfill(2),
            },
            limit=1,
        )
        if races:
            return True

    return False


def _process_one_day(
    target_date_hyphen,
    target_date_plain,
    venue_ids,
    sleep_sec,
    do_race,
    do_exhibition,
    do_odds,
    do_results,
    skip_existing,
):
    if skip_existing and _date_has_any_data_for_venues(target_date_hyphen, venue_ids):
        print(f"⏭️  {target_date_hyphen} スキップ(指定場データあり)")
        return target_date_hyphen, True

    print(f"\n=== {target_date_hyphen} 開始 ===")
    print("対象場:", ",".join(venue_ids) if venue_ids else "job default")

    day_ok = True
    step_results = []

    # job側が環境変数を読む実装の場合の保険
    if venue_ids:
        os.environ["BACKFILL_VENUES"] = ",".join(venue_ids)
        os.environ["TARGET_VENUES"] = ",".join(venue_ids)

    if do_race:
        try:
            _call_job(run_race_seed_job, target_date_hyphen, venue_ids=venue_ids)
            step_results.append("  [✅ race]")
        except Exception as e:
            day_ok = False
            step_results.append(f"  [❌ race] {e}")
        time.sleep(sleep_sec)

    if do_exhibition and HAS_EXHIBITION:
        try:
            _call_job(run_exhibition_seed_job_backfill, target_date_hyphen, venue_ids=venue_ids)
            step_results.append("  [✅ exhibition]")
        except Exception as e:
            day_ok = False
            step_results.append(f"  [❌ exhibition] {e}")
        time.sleep(sleep_sec)
    elif do_exhibition and not HAS_EXHIBITION:
        step_results.append("  [⚠️ exhibition スキップ]")

    if do_odds and HAS_ODDS:
        try:
            _call_job(run_odds_seed_job, target_date_hyphen, venue_ids=venue_ids)
            step_results.append("  [✅ odds]")
        except Exception as e:
            day_ok = False
            step_results.append(f"  [❌ odds] {e}")
        time.sleep(sleep_sec)
    elif do_odds and not HAS_ODDS:
        step_results.append("  [⚠️ odds スキップ]")

    if do_results:
        try:
            _call_job(
                run_result_fetch_job,
                target_date_plain,
                venue_ids=venue_ids,
                debug_first_n=0,
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
    venue_ids,
    sleep_sec,
    max_workers,
    do_race,
    do_exhibition,
    do_odds,
    do_results,
    skip_existing,
):
    ok_list = []
    ng_list = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _process_one_day,
                hyphen,
                plain,
                venue_ids,
                sleep_sec,
                do_race,
                do_exhibition,
                do_odds,
                do_results,
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
    venue_ids=None,
    sleep_sec=0.7,
    max_workers=2,
    max_retry=3,
    retry_wait_sec=15.0,
    do_race=True,
    do_exhibition=False,
    do_odds=False,
    do_results=True,
    skip_existing=False,
):
    print("=== 履歴バックフィル開始 ===")
    print("期間:", start_date_str, "→", end_date_str)
    print("対象場:", ",".join(venue_ids) if venue_ids else "job default")
    print("並列数:", max_workers)
    print("リトライ上限:", max_retry)
    print("do_race:", do_race)
    print("do_exhibition:", do_exhibition)
    print("do_odds:", do_odds)
    print("do_results:", do_results)
    print("skip_existing:", skip_existing)

    if do_odds:
        print("⚠️ 注意: do_odds=True は非常に重いです。検証初回では非推奨です。")

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    date_list = [
        (d.strftime("%Y-%m-%d"), d.strftime("%Y%m%d"))
        for d in daterange(start_date, end_date)
    ]

    print("対象日数:", len(date_list))

    ok_list, ng_list = _run_batch(
        date_list,
        venue_ids,
        sleep_sec,
        max_workers,
        do_race,
        do_exhibition,
        do_odds,
        do_results,
        skip_existing,
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

        retry_date_list = [(d, d.replace("-", "")) for d in sorted(ng_list)]

        retry_ok, ng_list = _run_batch(
            retry_date_list,
            venue_ids,
            sleep_sec,
            max_workers,
            do_race,
            do_exhibition,
            do_odds,
            do_results,
            skip_existing,
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
    run_history_backfill(
        start_date_str=os.environ.get("BACKFILL_START_DATE", "2025-03-13"),
        end_date_str=os.environ.get("BACKFILL_END_DATE", "2026-04-30"),
        venue_ids=[
            "02", "03", "04", "05",
            "07", "08", "09", "10", "11",
            "13", "14", "15", "16", "17",
            "19", "20", "21", "22", "23",
        ],
        sleep_sec=0.5,
        max_workers=4,
        max_retry=3,
        retry_wait_sec=15.0,
        do_race=True,
        do_exhibition=False,
        do_odds=False,
        do_results=True,
        skip_existing=False,
    )


if __name__ == "__main__":
    main()
    print("✅ バックフィル完了 → 待機モード")
    while True:
        time.sleep(3600)