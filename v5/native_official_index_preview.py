"""Direct official next-day race discovery + one-race V5 core PREVIEW.

No PostgreSQL, no service/timer changes, no BUY, no stage writes.
One official day index request, at most 3 race-specific official requests.
Requires V5 native core module for parsers, but never calls its apply_one.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit, parse_qs

JST = timezone(timedelta(hours=9))
HOST = "www.boatrace.jp"
BASE = "https://" + HOST
INDEX_PATH = "/owpc/pc/race/index"
VENUE_PATH = "/owpc/pc/race/raceindex"
VENUE_RE = re.compile(r"0[1-9]|1\d|2[0-4]\Z")
DATE_RE = re.compile(r"20\d{6}\Z")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if isinstance(href, str):
                self.links.append(href)


def official_venues(index_html: str, target_day: str) -> list[str]:
    """Accept only exact date-bound official venue-day raceindex links."""
    if not DATE_RE.fullmatch(target_day):
        raise ValueError("HOLD_INVALID_DATE")
    parser = Links()
    parser.feed(index_html)
    selected = set()
    for href in parser.links:
        url = urlsplit(urljoin(BASE, href))
        if (url.scheme != "https" or url.netloc != HOST
                or url.path != VENUE_PATH or url.fragment):
            continue
        params = parse_qs(url.query)
        if set(params) != {"hd", "jcd"}:
            continue
        days, venues = params.get("hd", []), params.get("jcd", [])
        if len(days) != 1 or days[0] != target_day or len(venues) != 1:
            continue
        if VENUE_RE.fullmatch(venues[0]):
            selected.add(venues[0])
    return sorted(selected)


def choose_day(now: datetime, target: str | None = None) -> str:
    today = now.astimezone(JST).date()
    tomorrow = today + timedelta(days=1)
    if target is None:
        return tomorrow.strftime("%Y%m%d")
    if (not DATE_RE.fullmatch(target)
            or target not in (today.strftime("%Y%m%d"),
                              tomorrow.strftime("%Y%m%d"))):
        raise ValueError("HOLD_DATE_ONLY_TODAY_OR_TOMORROW")
    return target


def fetch_official_index(target_day: str) -> str:
    import requests
    url = f"{BASE}{INDEX_PATH}?hd={target_day}"
    with requests.Session() as client:
        response = client.get(url, timeout=(8, 18), headers={
            "User-Agent": "Mozilla/5.0 (compatible; V5-official-preview/1.0)"
        })
        response.raise_for_status()
        landed = urlsplit(response.url)
        if (landed.scheme != "https" or landed.netloc != HOST
                or landed.path != INDEX_PATH):
            raise RuntimeError("HOLD_UNEXPECTED_INDEX_REDIRECT")
        if len(response.content) > 2_000_000:
            raise RuntimeError("HOLD_OFFICIAL_INDEX_OVERSIZE")
        return response.text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--day", default=None, help="YYYYMMDD today/tomorrow JST only")
    ap.add_argument("--max-venues", type=int, default=3)
    args = ap.parse_args(argv)
    if not 1 <= args.max_venues <= 3:
        ap.error("max-venues must be 1..3")
    day = choose_day(datetime.now(JST), args.day)
    print("V5_OFFICIAL_INDEX_DISCOVERY_PREVIEW_ONLY", flush=True)
    print("V5_OFFICIAL_INDEX_DAY=" + day, flush=True)
    index = fetch_official_index(day)
    venues = official_venues(index, day)
    print("V5_OFFICIAL_INDEX_EXACT_VENUE_LINKS=" + str(len(venues)), flush=True)
    if not venues:
        print("HOLD_OFFICIAL_INDEX_NO_MATCHING_VENUE_LINKS_NO_DB_NO_WRITES",
              flush=True)
        return 0
    from v5.native_stage_race_entries_pg import official_fetch, official_payload
    for venue in venues[:args.max_venues]:
        race_id = f"{day}_{venue}_01"
        try:
            html, observed = official_fetch(race_id)
            race, entries = official_payload(race_id, html, observed)
        except Exception as exc:
            print(f"V5_OFFICIAL_PREVIEW_HOLD race={race_id} "
                  f"reason={type(exc).__name__}:"
                  f"{str(exc).splitlines()[0][:90]}", flush=True)
            continue
        print(f"V5_OFFICIAL_NATIVE_CORE_PREVIEW_SUCCESS race={race['race_id']} "
              f"entries={len(entries)} captured={observed.isoformat()} "
              f"deadline={race['deadline_at']}", flush=True)
        print("V5_OFFICIAL_INDEX_PREVIEW_COMPLETE_NO_DB_NO_WRITES_NO_BUY",
              flush=True)
        return 0
    print("HOLD_OFFICIAL_RACELIST_NOT_READY_IN_BOUNDED_SAMPLE_NO_DB_NO_WRITES",
          flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("V5_OFFICIAL_INDEX_PREVIEW_HOLD "
              + type(exc).__name__ + ":"
              + str(exc).splitlines()[0][:120], flush=True)
        raise SystemExit(2)
