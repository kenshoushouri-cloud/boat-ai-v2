# -*- coding: utf-8 -*-
import json
import requests

BASE_URL = "https://boatraceopenapi.github.io/results/v2"


def fetch_results_api(target_date):
    compact = target_date.replace("-", "")
    year = compact[:4]
    url = f"{BASE_URL}/{year}/{compact}.json"

    print("RESULT API:", url)

    res = requests.get(url, timeout=20)
    res.raise_for_status()

    data = res.json()
    return data.get("results", [])


def build_race_id_from_result(row, target_date):
    venue_id = str(row.get("race_stadium_number", "")).zfill(2)
    race_no = int(row.get("race_number", 0))
    compact = target_date.replace("-", "")
    return f"{compact}_{venue_id}_{race_no:02d}"


def _extract_trifecta_payout(row):
    payouts = row.get("payouts") or {}
    trifecta = payouts.get("trifecta") or []

    if trifecta and isinstance(trifecta, list):
        first = trifecta[0] or {}
        payout = first.get("payout") or 0
        try:
            return int(payout)
        except Exception:
            return 0

    return 0


def _extract_trifecta_ticket(row):
    payouts = row.get("payouts") or {}
    trifecta = payouts.get("trifecta") or []

    if trifecta and isinstance(trifecta, list):
        first = trifecta[0] or {}
        combo = first.get("combination")
        if combo:
            return str(combo)

    boats = row.get("boats", [])
    ranking = sorted(boats, key=lambda x: x.get("racer_place_number") or 99)

    def get_lane(place):
        for b in ranking:
            if b.get("racer_place_number") == place:
                return b.get("racer_boat_number")
        return None

    first = get_lane(1)
    second = get_lane(2)
    third = get_lane(3)

    if first and second and third:
        return f"{first}-{second}-{third}"

    return None


def parse_result_row(row, target_date):
    race_id = build_race_id_from_result(row, target_date)

    boats = row.get("boats", [])
    ranking = sorted(boats, key=lambda x: x.get("racer_place_number") or 99)

    def get_lane(place):
        for b in ranking:
            if b.get("racer_place_number") == place:
                return b.get("racer_boat_number")
        return None

    first = get_lane(1)
    second = get_lane(2)
    third = get_lane(3)
    fourth = get_lane(4)
    fifth = get_lane(5)
    sixth = get_lane(6)

    trifecta_ticket = _extract_trifecta_ticket(row)
    trifecta_payout_yen = _extract_trifecta_payout(row)

    return {
        "race_id": race_id,
        "first_lane": first,
        "second_lane": second,
        "third_lane": third,
        "fourth_lane": fourth,
        "fifth_lane": fifth,
        "sixth_lane": sixth,
        "trifecta_ticket": trifecta_ticket,
        "trifecta_payout_yen": trifecta_payout_yen,
        "result_status": "official"
    }


def debug_print_one_result(target_date, target_race_id):
    rows = fetch_results_api(target_date)
    for row in rows:
        race_id = build_race_id_from_result(row, target_date)
        if race_id == target_race_id:
            print("=== RAW RESULT ROW ===")
            print(json.dumps(row, ensure_ascii=False, indent=2))
            return
    print("not found:", target_race_id)
