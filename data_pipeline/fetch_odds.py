# -*- coding: utf-8 -*-
from db.client import select_where

def get_odds(venue_id, race_no, race_date):
    race_id = f"{race_date}_{venue_id}_{int(race_no):02d}"
    rows = select_where("v2_odds_trifecta", {"race_id": race_id})

    odds = {}
    for r in rows:
        ticket = r.get("ticket")
        odd = r.get("odds")
        if ticket and odd is not None:
            odds[ticket] = float(odd)

    return odds
