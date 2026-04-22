# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup

BEFOREINFO_URL = "https://www.boatrace.jp/owpc/pc/race/beforeinfo"


def fetch_exhibition_page(target_date, venue_id, race_no):
    hd = str(target_date).replace("-", "")
    jcd = str(venue_id).zfill(2)
    rno = int(race_no)

    url = f"{BEFOREINFO_URL}?hd={hd}&jcd={jcd}&rno={rno}"
    print("EXHIBITION URL:", url)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.boatrace.jp/",
    }

    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()
    res.encoding = res.apparent_encoding or "utf-8"

    return res.text, url


def _to_float(text):
    try:
        return float(str(text).strip())
    except Exception:
        return None


def parse_exhibition_times(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    result = {}

    # ── 1) 展示タイム・チルト ──────────────────────────────────────────
    for tr in soup.find_all("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not tds:
            continue
        if not re.match(r"^[1-6]$", tds[0]):
            continue

        lane = int(tds[0])
        ex_time = None
        tilt = None

        for cell in tds[1:]:
            if re.match(r"^[67]\.\d{2}$", cell):
                ex_time = _to_float(cell)
            elif re.match(r"^-?\d+\.\d+$", cell) and "kg" not in cell:
                if ex_time is not None and tilt is None:
                    tilt = _to_float(cell)

        if ex_time is not None:
            result[lane] = {
                "lane": lane,
                "exhibition_time": ex_time,
                "tilt": tilt,
                "course": None,
                "start_position": None,
                "start_display_st": None,
            }

    # ── 2) スタート展示 ────────────────────────────────────────────────
    in_start_section = False

    for tag in soup.find_all(["th", "td", "tr"]):
        text = tag.get_text(strip=True)
        if "スタート展示" in text:
            in_start_section = True
            continue
        if not in_start_section:
            continue
        if tag.name == "tr":
            tds = [td.get_text(strip=True) for td in tag.find_all("td")]
            if len(tds) < 2:
                continue
            if not re.match(r"^[1-6]$", tds[0]):
                continue
            st_match = re.match(r"^\.?(\d{2,3})$", tds[1])
            if st_match:
                course = int(tds[0])
                st = _to_float(f"0.{st_match.group(1)}")
                if course not in result:
                    result[course] = {
                        "lane": course,
                        "exhibition_time": None,
                        "tilt": None,
                        "course": None,
                        "start_position": None,
                        "start_display_st": st,
                    }
                else:
                    result[course]["start_display_st"] = st

    print("exhibition parsed count:", len(result))
    for lane, row in sorted(result.items()):
        print(f"  lane{lane}: time={row['exhibition_time']} tilt={row['tilt']} st={row['start_display_st']}")

    return result


def fetch_exhibition_for_race(target_date, venue_id, race_no):
    raw_html, source_url = fetch_exhibition_page(target_date, venue_id, race_no)
    rows = parse_exhibition_times(raw_html)
    return rows, source_url
