# -*- coding: utf-8 -*-
from app.jobs.exhibition_seed_job
import run_exhibition_seed_job_backfill 
as run_exhibition_seed_job

def _calc_exhibition_rank(ex_rows):
    pairs = []

    for lane, row in ex_rows.items():
        ex_time = row.get("exhibition_time")
        if ex_time is not None:
            pairs.append((lane, float(ex_time)))

    pairs.sort(key=lambda x: x[1])

    rank_map = {}
    rank = 1
    for lane, _ in pairs:
        rank_map[lane] = rank
        rank += 1

    return rank_map


def run_exhibition_seed_job(target_date, limit_races=None):
    print("=== 展示投入ジョブ開始 ===")
    print("対象日:", target_date)

    races = select_where(
        "v2_races",
        {
            "race_date": target_date,
            "status": "scheduled"
        },
        order_by="venue_id.asc,race_no.asc"
    )

    print("対象レース数:", len(races))

    if limit_races:
        races = races[:limit_races]
        print("制限レース数:", len(races))

    saved_count = 0
    saved_races = 0
    empty_races = 0
    error_races = 0

    for race in races:
        race_id = race.get("race_id")
        race_no = race.get("race_no")

        raw_venue_id = race.get("venue_id")
        venue_id = int(str(raw_venue_id).lstrip("0") or "0")

        print(f"exhibition fetch start: {race_id} venue={venue_id} race_no={race_no}")

        try:
            ex_rows, source_url = fetch_exhibition_for_race(
                target_date,
                venue_id,
                race_no
            )
        except Exception as e:
            error_races += 1
            print("exhibition fetch error:", race_id, e)
            continue

        if not ex_rows:
            empty_races += 1
            print("exhibition empty:", race_id)
            continue

        rank_map = _calc_exhibition_rank(ex_rows)

        race_saved = 0

        for lane, row in ex_rows.items():
            data = {
                "race_id": race_id,
                "lane": lane,
                "exhibition_time": row.get("exhibition_time"),
                "start_timing": row.get("start_display_st"),
                "exhibition_rank": rank_map.get(lane),
                "course": row.get("course"),
                "start_position": row.get("start_position"),
                "tilt": row.get("tilt"),
            }

            upsert(
                "v2_exhibition",
                data,
                on_conflict=["race_id", "lane"]
            )
            race_saved += 1
            saved_count += 1

        if race_saved > 0:
            saved_races += 1

        print("exhibition saved:", race_id, race_saved)

    print("保存レース件数:", saved_races)
    print("保存展示件数:", saved_count)
    print("emptyレース件数:", empty_races)
    print("errorレース件数:", error_races)
    
    def run_exhibition_seed_job_backfill(target_date, limit_races=None):
    """バックフィル用:statusフィルターなし"""
    print("=== 展示投入ジョブ開始(バックフィル) ===")
    print("対象日:", target_date)

    # statusフィルターを外す
    races = select_where(
        "v2_races",
        {"race_date": target_date},
        order_by="venue_id.asc,race_no.asc"
    )

    print("対象レース数:", len(races))

    if limit_races:
        races = races[:limit_races]

    saved_count = 0
    saved_races = 0
    empty_races = 0
    error_races = 0

    for race in races:
        race_id = race.get("race_id")
        race_no = race.get("race_no")
        raw_venue_id = race.get("venue_id")
        venue_id = int(str(raw_venue_id).lstrip("0") or "0")

        print(f"exhibition fetch start: {race_id} venue={venue_id} race_no={race_no}")

        try:
            ex_rows, source_url = fetch_exhibition_for_race(
                target_date, venue_id, race_no
            )
        except Exception as e:
            error_races += 1
            print("exhibition fetch error:", race_id, e)
            continue

        if not ex_rows:
            empty_races += 1
            print("exhibition empty:", race_id)
            continue

        rank_map = _calc_exhibition_rank(ex_rows)
        race_saved = 0

        for lane, row in ex_rows.items():
            data = {
                "race_id": race_id,
                "lane": lane,
                "exhibition_time": row.get("exhibition_time"),
                "start_timing": row.get("start_display_st"),
                "exhibition_rank": rank_map.get(lane),
                "course": row.get("course"),
                "start_position": row.get("start_position"),
                "tilt": row.get("tilt"),
            }
            upsert("v2_exhibition", data, on_conflict=["race_id", "lane"])
            race_saved += 1
            saved_count += 1

        if race_saved > 0:
            saved_races += 1

        print("exhibition saved:", race_id, race_saved)

    print("保存レース件数:", saved_races)
    print("保存展示件数:", saved_count)
    print("emptyレース件数:", empty_races)
    print("errorレース件数:", error_races)
