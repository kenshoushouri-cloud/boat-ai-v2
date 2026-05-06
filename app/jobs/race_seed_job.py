# -*- coding: utf-8 -*-
from data_pipeline.fetch_programs import (
    fetch_programs_api,
    parse_race_row,
    parse_entry_rows,
    TARGET_VENUES as DEFAULT_TARGET_VENUES,
)
from db.client import upsert


# ナイター場の簡易判定
# 01 桐生 / 07 蒲郡 / 12 住之江 / 15 丸亀 / 18 下関 / 20 若松 / 24 大村
NIGHT_VENUES = {"01", "07", "12", "15", "18", "20", "24"}


def _normalize_venues(venue_ids=None):
    if venue_ids is None:
        venue_ids = DEFAULT_TARGET_VENUES

    return {str(v).zfill(2) for v in venue_ids}


def _detect_session_type(venue_id):
    venue_id = str(venue_id).zfill(2)
    if venue_id in NIGHT_VENUES:
        return "night"
    return "day"


def run_race_seed_job(target_date, venue_ids=None):
    print("=== レース投入ジョブ開始 ===")
    print("対象日:", target_date)

    target_venues = _normalize_venues(venue_ids)
    print("対象場:", ",".join(sorted(target_venues)))

    rows = fetch_programs_api(target_date)
    print("API件数:", len(rows))

    saved_races = 0
    saved_entries = 0
    skipped = 0

    for i, row in enumerate(rows):
        venue_id = str(row.get("race_stadium_number", "")).zfill(2)

        if venue_id not in target_venues:
            skipped += 1
            continue

        race_data = parse_race_row(row, target_date)
        race_data["session_type"] = _detect_session_type(venue_id)

        print("race upsert start:", i, race_data["race_id"])
        race_res = upsert("v2_races", race_data, on_conflict=["race_id"])
        print(
            "race upsert ok:",
            race_data["race_id"],
            race_res[:1] if isinstance(race_res, list) else race_res
        )
        saved_races += 1

        entry_rows = parse_entry_rows(row, target_date)
        print("entry count:", len(entry_rows))

        for j, entry in enumerate(entry_rows):
            print(
                "entry upsert start:",
                j,
                entry["race_id"],
                entry["lane"],
                entry.get("racer_name")
            )
            entry_res = upsert(
                "v2_race_entries",
                entry,
                on_conflict=["race_id", "lane"]
            )
            print(
                "entry upsert ok:",
                entry["race_id"],
                entry["lane"],
                entry_res[:1] if isinstance(entry_res, list) else entry_res
            )
            saved_entries += 1

    print("保存レース件数:", saved_races)
    print("保存出走表件数:", saved_entries)
    print("skip件数:", skipped)