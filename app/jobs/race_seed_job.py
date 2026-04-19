# -*- coding: utf-8 -*-
from data_pipeline.fetch_programs import (
    fetch_programs_api,
    parse_race_row,
    parse_entry_rows,
    TARGET_VENUES,
)
from db.client import upsert


def _detect_session_type(venue_id):
    """
    最小版:
    住之江・下関・大村は night 寄り、
    桐生・常滑は day 寄りで仮置き
    """
    venue_id = str(venue_id).zfill(2)
    if venue_id in {"12", "18", "24"}:
        return "night"
    return "day"


def run_race_seed_job(target_date):
    print("=== 当日レース投入ジョブ開始 ===")
    print("対象日:", target_date)

    rows = fetch_programs_api(target_date)
    print("API件数:", len(rows))

    saved_races = 0
    saved_entries = 0
    skipped = 0

    for row in rows:
        venue_id = str(row.get("race_stadium_number", "")).zfill(2)
        if venue_id not in TARGET_VENUES:
            skipped += 1
            continue

        race_data = parse_race_row(row, target_date)
        race_data["session_type"] = _detect_session_type(venue_id)

        upsert("v2_races", race_data, on_conflict=["race_id"])
        saved_races += 1

        entry_rows = parse_entry_rows(row, target_date)
        for entry in entry_rows:
            upsert("v2_race_entries", entry, on_conflict=["race_id", "lane"])
            saved_entries += 1

    print("保存レース件数:", saved_races)
    print("保存出走表件数:", saved_entries)
    print("skip件数:", skipped)