# -*- coding: utf-8 -*-
from data_pipeline.fetch_results import fetch_results_api, parse_result_row
from db.client import upsert, select_where


TARGET_VENUES = {"01", "06", "12", "18", "24"}


def run_result_fetch_job(target_date):
    print("=== 結果取得ジョブ開始 ===")
    print("対象日:", target_date)

    rows = fetch_results_api(target_date)
    print("API件数:", len(rows))

    saved = 0
    skipped = 0

    for row in rows:
        venue_id = str(row.get("race_stadium_number", "")).zfill(2)
        if venue_id not in TARGET_VENUES:
            skipped += 1
            continue

        parsed = parse_result_row(row, target_date)

        # v2_races に存在するものだけ保存
        races = select_where("v2_races", {"race_id": parsed["race_id"]}, limit=1)
        if not races:
            print("skip(no race):", parsed["race_id"])
            skipped += 1
            continue

        upsert("v2_results", parsed, on_conflict=["race_id"])
        saved += 1
        print("saved:", parsed["race_id"], parsed["trifecta_ticket"], parsed["trifecta_payout_yen"])

    print("保存件数:", saved)
    print("skip件数:", skipped)
