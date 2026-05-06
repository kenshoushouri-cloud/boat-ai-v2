# boat_ai_v2/tools/backfill_titles.py

import requests
import time
from datetime import datetime

# =========================
# 設定
# =========================

SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_SERVICE_ROLE_OR_ANON_KEY"

BASE_URL = "https://boatraceopenapi.github.io"

# 最初は True のまま確認
DRY_RUN = True

LIMIT = 1000
SLEEP_SEC = 0.2


HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


# =========================
# Supabase REST
# =========================

def supabase_get(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
    if r.status_code >= 300:
        raise Exception(f"GET error {r.status_code}: {r.text}")
    return r.json()


def supabase_patch(table, query, payload):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    r = requests.patch(url, headers=HEADERS, json=payload, timeout=30)
    if r.status_code >= 300:
        raise Exception(f"PATCH error {r.status_code}: {r.text}")
    return True


# =========================
# Open API取得
# =========================

def yyyymmdd(date_str):
    return date_str.replace("-", "")


def fetch_program(date_str):
    year = date_str[:4]
    ymd = yyyymmdd(date_str)
    url = f"{BASE_URL}/programs/v2/{year}/{ymd}.json"

    print(f"[fetch] {url}")
    r = requests.get(url, timeout=30)

    if r.status_code == 404:
        print(f"[warn] not found: {date_str}")
        return None

    if r.status_code >= 300:
        print(f"[warn] fetch failed {r.status_code}: {date_str}")
        return None

    return r.json()


# =========================
# JSONから race_title を抽出
# 構造差異に強めにしてあります
# =========================

VENUE_KEYS = [
    "venue_id", "jcd", "jyo", "jyo_cd", "stadium_code",
    "stadiumCode", "place_code", "placeCode"
]

RACE_NO_KEYS = [
    "race_no", "rno", "raceNo", "race_number",
    "raceNumber", "race_num", "raceNum"
]

TITLE_KEYS = [
    "race_title", "raceTitle", "title",
    "race_name", "raceName", "name"
]


def normalize_venue(v):
    if v is None:
        return None
    try:
        return str(v).zfill(2)
    except Exception:
        return None


def normalize_race_no(v):
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def get_first(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in [None, ""]:
            return d[k]
    return None


def walk_json(obj, current_venue=None, current_race_no=None, out=None):
    if out is None:
        out = {}

    if isinstance(obj, dict):
        venue = normalize_venue(get_first(obj, VENUE_KEYS)) or current_venue
        race_no = normalize_race_no(get_first(obj, RACE_NO_KEYS)) or current_race_no
        title = get_first(obj, TITLE_KEYS)

        if venue and race_no and title:
            title_text = str(title).strip()
            if title_text:
                out[(venue, race_no)] = title_text

        for v in obj.values():
            walk_json(v, venue, race_no, out)

    elif isinstance(obj, list):
        for item in obj:
            walk_json(item, current_venue, current_race_no, out)

    return out


def build_title_map(date_str):
    data = fetch_program(date_str)
    if data is None:
        return {}

    title_map = walk_json(data)

    print(f"[map] {date_str}: {len(title_map)} titles found")
    return title_map


# =========================
# 補完対象取得
# =========================

def load_targets():
    rows = supabase_get(
        "v2_backfill_title_missing_targets",
        {
            "select": "venue_id,race_date,race_nos",
            "limit": str(LIMIT),
            "order": "race_date.asc,venue_id.asc",
        },
    )
    return rows


def parse_race_nos(race_nos):
    if race_nos is None:
        return []
    return [int(x.strip()) for x in str(race_nos).split(",") if x.strip()]


# =========================
# メイン処理
# =========================

def main():
    print("======================================")
    print("race_title backfill start")
    print("DRY_RUN =", DRY_RUN)
    print("======================================")

    targets = load_targets()

    if not targets:
        print("[done] 補完対象なし")
        return

    print(f"[targets] {len(targets)} venue-date rows")

    cache = {}
    updated = 0
    missing = 0
    errors = 0

    for i, row in enumerate(targets, 1):
        venue_id = str(row["venue_id"]).zfill(2)
        race_date = row["race_date"]
        race_nos = parse_race_nos(row.get("race_nos"))

        print(f"\n[{i}/{len(targets)}] {race_date} venue={venue_id} races={race_nos}")

        if race_date not in cache:
            cache[race_date] = build_title_map(race_date)
            time.sleep(SLEEP_SEC)

        title_map = cache[race_date]

        for race_no in race_nos:
            title = title_map.get((venue_id, race_no))

            race_id = f"{yyyymmdd(race_date)}_{venue_id}_{str(race_no).zfill(2)}"

            if not title:
                print(f"  [missing] {race_id} title not found")
                missing += 1
                continue

            print(f"  [update] {race_id} -> {title}")

            if not DRY_RUN:
                try:
                    supabase_patch(
                        "v2_races",
                        f"race_id=eq.{race_id}",
                        {
                            "race_title": title,
                            "updated_at": datetime.utcnow().isoformat(),
                        },
                    )
                    updated += 1
                except Exception as e:
                    print(f"  [error] {race_id}: {e}")
                    errors += 1
            else:
                updated += 1

    print("\n======================================")
    print("race_title backfill finished")
    print(f"updated_or_dryrun: {updated}")
    print(f"missing:           {missing}")
    print(f"errors:            {errors}")
    print("======================================")


if __name__ == "__main__":
    main()