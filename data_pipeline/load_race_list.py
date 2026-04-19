# -*- coding: utf-8 -*-
from db.client import select_where


def load_race_list(race_date, session_type=None, venue_ids=None):
    filters = {
        "race_date": race_date,
        "status": "scheduled"
    }

    races = select_where("v2_races", filters, order_by="venue_id.asc,race_no.asc")

    if session_type:
        races = [r for r in races if r.get("session_type") == session_type]

    if venue_ids:
        venue_ids = set(str(v) for v in venue_ids)
        races = [r for r in races if str(r.get("venue_id")) in venue_ids]

    return races
