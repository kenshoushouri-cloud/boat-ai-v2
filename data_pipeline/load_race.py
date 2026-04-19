# -*- coding: utf-8 -*-
from db.client import select_where


def build_race_id(race_date, venue_id, race_no):
    return f"{race_date}_{venue_id}_{int(race_no):02d}"


def load_race_context(venue_id, race_no, race_date):
    race_id = build_race_id(race_date, venue_id, race_no)

    races = select_where("v2_races", {"race_id": race_id}, limit=1)
    entries = select_where("v2_race_entries", {"race_id": race_id}, order_by="lane.asc")
    exhibition = select_where("v2_exhibition", {"race_id": race_id}, order_by="lane.asc")
    weather_rows = select_where("v2_race_weather", {"race_id": race_id}, limit=1)
    odds_rows = select_where("v2_odds_trifecta", {"race_id": race_id})

    race = races[0] if races else None
    weather = weather_rows[0] if weather_rows else {}

    ex_by_lane = {int(x["lane"]): x for x in exhibition if x.get("lane") is not None}
    odds = {}
    for row in odds_rows:
        ticket = row.get("ticket")
        odd = row.get("odds")
        if ticket and odd is not None:
            odds[ticket] = float(odd)

    merged_entries = []
    for e in entries:
        lane = int(e["lane"])
        ex = ex_by_lane.get(lane, {})
        merged = dict(e)
        merged["exhibition_time"] = ex.get("exhibition_time")
        merged["start_timing"] = ex.get("start_timing")
        merged["exhibition_rank"] = ex.get("exhibition_rank")
        merged["course"] = ex.get("course", lane)
        merged_entries.append(merged)

    return {
        "race_id": race_id,
        "race": race,
        "entries": merged_entries,
        "weather": weather,
        "odds": odds
    }
