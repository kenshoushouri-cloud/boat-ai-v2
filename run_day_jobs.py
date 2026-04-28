# -*- coding: utf-8 -*-
from data_pipeline.load_race_list import load_race_list
from data_pipeline.load_race import load_race_context
from app.jobs.day_prediction_job import run_day_prediction_job


def main():
    target_date = "2026-04-20"
    print("DAY TARGET DATE:", target_date)

    # 当日の昼レース一覧を取得
    race_list = load_race_list(target_date, session_type="day")
    print("対象レース数:", len(race_list))

    if not race_list:
        print("対象レースなし → 終了")
        return

    # 各レースのコンテキストを取得
    race_contexts = []
    for race in race_list:
        try:
            context = load_race_context(
                race["venue_id"],
                race["race_no"],
                race["race_date"].replace("-", "")
            )
            if context:
                race_contexts.append(context)
        except Exception as e:
            print(f"context load error: {race['race_id']} {e}")

    print("コンテキスト取得数:", len(race_contexts))

    if not race_contexts:
        print("コンテキストなし → 終了")
        return

    run_day_prediction_job(target_date, race_contexts)


if __name__ == "__main__":
    main()