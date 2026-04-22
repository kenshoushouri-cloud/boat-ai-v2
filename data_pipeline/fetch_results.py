# -*- coding: utf-8 -*-
import json
import requests

RESULT_API_BASE = "https://boatraceopenapi.github.io/results/v2"


def fetch_result_rows(target_date):
    hd = str(target_date).replace("-", "")
    year = hd[:4]
    url = f"{RESULT_API_BASE}/{year}/{hd}.json"

    print("RESULT API:", url)

    res = requests.get(url, timeout=20)
    res.raise_for_status()

    data = res.json()

    print("ROOT TYPE:", type(data).__name__)

    if isinstance(data, dict):
        print("ROOT KEYS:", list(data.keys()))
        rows = data.get("results", [])
        print("USING KEY: results LEN:", len(rows))
        return rows, url

    if isinstance(data, list):
        return data, url

    return [], url


def debug_print_row(row, idx=None):
    print("=== RESULT ROW DEBUG START ===")
    if idx is not None:
        print("ROW INDEX:", idx)
    print(json.dumps(row, ensure_ascii=False, indent=2))
    print("=== RESULT ROW DEBUG END ===")


def _safe_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _norm_ticket(v):
    if v is None:
        return None
    s = str(v).strip().replace(" ", "")
    return s if s else None


def _pick_payout(payouts, key):
    """
    payouts["exacta"] のような配列から1件目を拾う
    """
    rows = payouts.get(key, [])
    if not rows:
        return None, 0

    row = rows[0]
    ticket = _norm_ticket(row.get("combination"))
    payout = _safe_int(row.get("payout"), 0)
    return ticket, payout


def _extract_places(boats):
    """
    boats から着順順に艇番を並べる
    """
    pairs = []

    for b in boats:
        place_no = b.get("racer_place_number")
        boat_no = b.get("racer_boat_number")

        if place_no in (None, "") or boat_no in (None, ""):
            continue

        try:
            place_no = int(place_no)
            boat_no = int(boat_no)
        except Exception:
            continue

        pairs.append((place_no, boat_no))

    pairs.sort(key=lambda x: x[0])
    ordered = [boat_no for _, boat_no in pairs]

    # 1〜6着を埋める
    lanes = ordered + [None] * (6 - len(ordered))
    return lanes[:6]


def parse_result_row(row):
    race_date = row.get("race_date")
    stadium_no = row.get("race_stadium_number")
    race_no = row.get("race_number")

    if not race_date or stadium_no is None or race_no is None:
        return None

    hd = str(race_date).replace("-", "")
    venue_id = str(stadium_no).zfill(2)
    race_no = int(race_no)
    race_id = f"{hd}_{venue_id}_{race_no:02d}"

    payouts = row.get("payouts", {}) or {}

    trifecta_ticket, trifecta_payout_yen = _pick_payout(payouts, "trifecta")
    exacta_ticket, exacta_payout_yen = _pick_payout(payouts, "exacta")

    boats = row.get("boats", []) or []
    first_lane, second_lane, third_lane, fourth_lane, fifth_lane, sixth_lane = _extract_places(boats)

    return {
        "race_id": race_id,
        "first_lane": first_lane,
        "second_lane": second_lane,
        "third_lane": third_lane,
        "fourth_lane": fourth_lane,
        "fifth_lane": fifth_lane,
        "sixth_lane": sixth_lane,
        "trifecta_ticket": trifecta_ticket,
        "trifecta_payout_yen": trifecta_payout_yen,
        "exacta_ticket": exacta_ticket,
        "exacta_payout_yen": exacta_payout_yen,
        "result_status": "official",
        "source": "boatrace_openapi",
    }
