# -*- coding: utf-8 -*-
from db.client import select_where, upsert
from data_pipeline.fetch_results import (
    fetch_result_rows,
    parse_result_row,
    debug_print_row,
)


def run_result_fetch_job(target_date, debug_first_n=3):
    print("=== 結果取得ジョブ開始 ===")
    print("対象日:", target_date)

    rows, source_url = fetch_result_rows(target_date)
    print("API件数:", len(rows))

    for i, row in enumerate(rows[:debug_first_n]):
        debug_print_row(row, idx=i)

    saved_count = 0
    skip_count = 0

    for row in rows:
        parsed = parse_result_row(row)
        if not parsed:
            skip_count += 1
            continue

        race_id = parsed["race_id"]

        races = select_where("v2_races", {"race_id": race_id}, limit=1)
        if not races:
            skip_count += 1
            continue

        data = {
            "race_id": parsed["race_id"],
            "first_lane": parsed["first_lane"],
            "second_lane": parsed["second_lane"],
            "third_lane": parsed["third_lane"],
            "fourth_lane": parsed["fourth_lane"],
            "fifth_lane": parsed["fifth_lane"],
            "sixth_lane": parsed["sixth_lane"],
            "trifecta_ticket": parsed["trifecta_ticket"],
            "trifecta_payout_yen": parsed["trifecta_payout_yen"],
            "exacta_ticket": parsed["exacta_ticket"],
            "exacta_payout_yen": parsed["exacta_payout_yen"],
            "result_status": parsed["result_status"],
            "source": parsed["source"],
        }

        upsert("v2_results", data, on_conflict=["race_id"])
        saved_count += 1

        print(
            "saved:",
            race_id,
            "3連単=", parsed["trifecta_ticket"], parsed["trifecta_payout_yen"],
            "2連単=", parsed["exacta_ticket"], parsed["exacta_payout_yen"]
        )

    print("保存件数:", saved_count)
    print("skip件数:", skip_count)
