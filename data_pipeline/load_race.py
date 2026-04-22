# -*- coding: utf-8 -*-
from db.client import select_where


def _build_odds_map(odds_rows):
    odds_map = {}

    for row in odds_rows:
        ticket = (
            row.get("ticket")
            or row.get("trifecta_ticket")
            or row.get("combination")
        )
        odds = row.get("odds")

        if ticket and odds is not None:
            try:
                odds_map[ticket] = float(odds)
            except Exception:
                pass

    return odds_map


def _build_exhibition_map(exhibition_rows):
    exhibition_map = {}

    for row in exhibition_rows:
        lane = row.get("lane")
        if lane is None:
            continue

        exhibition_map[str(lane)] = {
            "lane": lane,
            "exhibition_time": row.get("exhibition_time"),
            "tilt": row.get("tilt"),
            "course": row.get("course"),
            "start_position": row.get("start_position"),
            "start_timing": row.get("start_timing"),
            "exhibition_rank": row.get("exhibition_rank"),
        }

    return exhibition_map


def _extract_result_ticket(result_row):
    if not result_row:
        return None

    return (
        result_row.get("trifecta_ticket")
        or result_row.get("trifecta")
        or result_row.get("winning_ticket")
        or result_row.get("ticket")
    )


def load_race_context(venue_id, race_no, race_date):
    venue_id = str(venue_id).zfill(2)
    race_no = int(race_no)
    race_id = f"{str(race_date).replace('-', '')}_{venue_id}_{race_no:02d}"

    races = select_where("v2_races", {"race_id": race_id}, limit=1)
    if not races:
        print("race not found:", race_id)
        return None

    race = races[0]

    entries = select_where(
        "v2_race_entries",
        {"race_id": race_id},
        order_by="lane.asc"
    )
    print("entries count:", race_id, len(entries))

    odds_rows = select_where(
        "v2_odds_trifecta",
        {"race_id": race_id}
    )
    print("odds count:", race_id, len(odds_rows))

    exhibition_rows = select_where(
        "v2_exhibition",
        {"race_id": race_id},
        order_by="lane.asc"
    )
    print("exhibition count:", race_id, len(exhibition_rows))

    weather_rows = select_where(
        "v2_race_weather",
        {"race_id": race_id},
        limit=1
    )
    weather = weather_rows[0] if weather_rows else {}

    result_rows = select_where(
        "v2_results",
        {"race_id": race_id},
        limit=1
    )
    result_row = result_rows[0] if result_rows else {}

    odds_map = _build_odds_map(odds_rows)
    exhibition_map = _build_exhibition_map(exhibition_rows)

    return {
        "race_id": race_id,
        "race": race,
        "venue_id": venue_id,
        "race_no": race_no,
        "entries": entries,
        "odds": odds_map,
        "weather": weather,
        "exhibition": exhibition_map,
        "result": _extract_result_ticket(result_row),
        "result_row": result_row,
    }
