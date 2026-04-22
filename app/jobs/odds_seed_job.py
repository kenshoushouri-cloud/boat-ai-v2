# -*- coding: utf-8 -*-
from db.client import select_where, upsert
from data_pipeline.fetch_odds import fetch_odds_for_race


def run_odds_seed_job(target_date, limit_races=None):
    print("=== 当日オッズ投入ジョブ開始 ===")
    print("対象日:", target_date)

    races = select_where(
        "v2_races",
        {"race_date": target_date, "status": "scheduled"},
        order_by="venue_id.asc,race_no.asc"
    )

    print("対象レース数:", len(races))

    saved_races = 0
    saved_odds = 0

    for idx, race in enumerate(races):
        if limit_races is not None and idx >= limit_races:
            break

        venue_id = str(race["venue_id"]).zfill(2)
        race_no = int(race["race_no"])
        race_id = race["race_id"]

        print("odds fetch start:", race_id)

        try:
            odds_map, source_url = fetch_odds_for_race(target_date, venue_id, race_no)
            print("odds count:", race_id, len(odds_map))

            if not odds_map:
                continue

            for ticket, odd in odds_map.items():
                upsert("v2_odds_trifecta", {
                    "race_id": race_id,
                    "ticket": ticket,
                    "odds": odd,
                    "source_url": source_url
                }, on_conflict=["race_id", "ticket"])
                saved_odds += 1

            saved_races += 1

        except Exception as e:
            print("odds fetch error:", race_id, repr(e))
            continue

    print("保存レース件数:", saved_races)
    print("保存オッズ件数:", saved_odds)
