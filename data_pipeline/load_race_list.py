# -*- coding: utf-8 -*-
from db.client import select_where


def load_race_list(race_date, session_type=None, venue_ids=None):
    rows = select_where(
        "v2_races",
        {
            "race_date": race_date,
            "status": "scheduled"
        },
        order_by="venue_id.asc,race_no.asc"
    )

    print("load_race_list raw_count:", len(rows))

    results = []

    for row in rows:
        venue_id = str(row.get("venue_id", "")).zfill(2)
        row_session_type = (row.get("session_type") or "").strip()

        if venue_ids and venue_id not in venue_ids:
            continue

        if session_type and row_session_type != session_type:
            continue

        results.append({
            "race_id": row.get("race_id"),
            "race_date": row.get("race_date"),
            "venue_id": venue_id,
            "race_no": int(row.get("race_no", 0)),
            "session_type": row_session_type,
            "status": row.get("status")
        })

    print("load_race_list filtered_count:", len(results))
    return results
