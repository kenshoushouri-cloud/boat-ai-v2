# -*- coding: utf-8 -*-
"""
v21_realtime_collector_fix2.py

競艇AI v2 リアルタイム情報収集スクリプト。

収集対象:
- 直前情報ページ beforeinfo:
  - 展示タイム
  - 展示ST/スタート展示
  - 展示進入
  - チルト候補
  - 天候/気温/水温/風速/風向/波高
- 3連単オッズ odds3t:
  - 直前3連単オッズ
  - 人気順位
  - 前回スナップショットとの差分

保存先:
- v2_realtime_exhibition_snapshots
- v2_realtime_weather_snapshots
- v2_realtime_entry_snapshots
- v2_realtime_odds_snapshots

Railway Start Command:
    python v21_realtime_collector_fix2.py

任意Variables:
    TARGET_DATE=YYYY-MM-DD
    TARGET_RACE_ID=20260625_24_01
    SNAPSHOT_LABEL=pre10|pre5|final|manual
    COLLECT_SCOPE=candidates|all
    SELECTOR_MODE=balanced
    TARGET_VENUES=01,02,...,24
    REALTIME_SLEEP_SEC=0.15
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

JST = timezone(timedelta(hours=9))

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
TARGET_RACE_ID = os.getenv("TARGET_RACE_ID", "").strip()
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "manual").strip() or "manual"
COLLECT_SCOPE = os.getenv("COLLECT_SCOPE", "candidates").strip().lower()
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "balanced").strip().lower()
TARGET_VENUES = [
    v.zfill(2)
    for v in os.getenv("TARGET_VENUES", ",".join(f"{i:02d}" for i in range(1, 25))).split(",")
    if v.strip()
]
REALTIME_SLEEP_SEC = float(os.getenv("REALTIME_SLEEP_SEC", "0.15"))
PARSE_ALLOW_PARTIAL = os.getenv("PARSE_ALLOW_PARTIAL", "0").strip() in ("1", "true", "True", "yes", "YES")

HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "35"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "2"))
RETRY_SLEEP = float(os.getenv("RETRY_SLEEP", "2.0"))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "1000"))
ODDS_PAGE_SIZE = int(os.getenv("ODDS_PAGE_SIZE", "1000"))

UNIT_YEN = 100
DAILY_BUDGET_YEN = int(os.getenv("DAILY_BUDGET_YEN", "1000"))

BAD5_VENUES = {"01", "04", "05", "06", "23"}
IN_STRONG_VENUES = {"12", "15", "18", "21", "24"}
ROUGH_VENUES = {"02", "03", "04", "05", "06"}

OFFICIAL = "https://www.boatrace.jp/owpc/pc/race"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; boatrace-realtime-collector/1.0)"
})


# ============================================================
# basic utils
# ============================================================

def _require_settings() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY が必要です。")


def _now_iso() -> str:
    return datetime.now(JST).isoformat()


def _yyyymmdd(date_str: str) -> str:
    return date_str.replace("-", "")


def _rid_prefix(date_str: str) -> str:
    return date_str.replace("-", "")


def _next_day(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _shift_day(date_str: str, days: int) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)
    return d.strftime("%Y-%m-%d")


def _norm_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _norm_ticket(s: Any) -> str:
    t = str(s or "").strip()
    nums = re.findall(r"[1-6]", t)
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    return ""


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(str(v).replace(",", "")))
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        s = str(v).replace(",", "").replace("F", "").replace("L", "").strip()
        if s.startswith("."):
            s = "0" + s
        if s.startswith("-."):
            s = s.replace("-.", "-0.", 1)
        return float(s)
    except Exception:
        return default


def _official_url(kind: str, date_str: str, venue_id: str, race_no: int) -> str:
    return f"{OFFICIAL}/{kind}?rno={int(race_no)}&jcd={venue_id.zfill(2)}&hd={_yyyymmdd(date_str)}"


def _fetch(url: str) -> Optional[str]:
    last = None
    for attempt in range(RETRY_MAX + 1):
        try:
            r = SESSION.get(url, timeout=HTTP_TIMEOUT)
            if r.status_code == 404:
                return None
            if not r.ok:
                last = f"HTTP {r.status_code}: {r.text[:120]}"
                time.sleep(RETRY_SLEEP)
                continue
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception as e:
            last = repr(e)
            time.sleep(RETRY_SLEEP)
    print(f"⚠️ fetch failed: {url} / {last}", flush=True)
    return None


def _looks_no_data(html: Optional[str]) -> bool:
    if not html:
        return True
    t = _norm_text(re.sub(r"<[^>]+>", " ", html))
    return (
        "データがありません" in t
        or "開催はありません" in t
        or "該当するデータはありません" in t
        or "オッズの更新" in t and len(t) < 500
    )


# ============================================================
# REST helpers
# ============================================================

def _rest_get(table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
    query = urllib.parse.urlencode(params, safe=",.*()")
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    last = None
    for attempt in range(RETRY_MAX + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")
            return r.json()
        except Exception as e:
            last = e
            if attempt < RETRY_MAX:
                time.sleep(RETRY_SLEEP)
    raise RuntimeError(f"GET {table} failed: {last}")


def _rest_get_range(table: str, select: str, col: str, gte: str, lt: str, page_size: int = PAGE_SIZE) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    offset = 0
    while True:
        rows = _rest_get(table, {
            "select": select,
            col: f"gte.{gte}",
            "order": f"{col}.asc",
            "limit": str(page_size),
            "offset": str(offset),
        })
        # PostgRESTでltを同時指定しにくいためローカルでも絞る
        rows = [r for r in rows if str(r.get(col, "")) < lt]
        out.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def _upsert(table: str, rows: List[Dict[str, Any]], on_conflict: str, chunk_size: int = 500) -> int:
    if not rows:
        return 0
    total = 0
    for i in range(0, len(rows), chunk_size):
        part = rows[i:i + chunk_size]
        query = urllib.parse.urlencode({"on_conflict": on_conflict})
        url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
        r = requests.post(
            url,
            headers=HEADERS,
            data=json.dumps(part, ensure_ascii=False),
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"UPSERT {table} failed {r.status_code}: {r.text[:800]}")
        total += len(part)
    return total


# ============================================================
# parse official pages
# ============================================================

def _soup_text(html: str) -> str:
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        return _norm_text(soup.get_text(" ", strip=True))
    return _norm_text(re.sub(r"<[^>]+>", " ", html))


def parse_weather(html: str) -> Dict[str, Any]:
    text = _soup_text(html)
    weather = None
    for w in ["晴", "曇り", "くもり", "雨", "雪", "霧"]:
        if w in text:
            weather = w
            break

    def rx(pattern: str) -> Optional[float]:
        m = re.search(pattern, text)
        if not m:
            return None
        return _safe_float(m.group(1), None)

    wind_direction = None
    m = re.search(r"(北|北東|東|南東|南|南西|西|北西|向い風|追い風|右横風|左横風)", text)
    if m:
        wind_direction = m.group(1)

    return {
        "weather": weather,
        "temperature_c": rx(r"気温\s*([0-9.]+)\s*℃"),
        "water_temperature_c": rx(r"水温\s*([0-9.]+)\s*℃"),
        "wind_speed_m": rx(r"風速\s*([0-9.]+)\s*m"),
        "wind_direction": wind_direction,
        "wave_height_cm": rx(r"波高\s*([0-9.]+)\s*cm"),
        "raw_text": text[:2000],
    }


def _extract_table_rows(html: str) -> List[List[str]]:
    rows: List[List[str]] = []
    if BeautifulSoup is None:
        return rows
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        cells = [_norm_text(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return rows


def _find_lane_in_cells(cells: List[str]) -> Optional[int]:
    for c in cells[:3]:
        if re.fullmatch(r"[1-6]", c):
            return int(c)
    return None


def _find_exhibition_course(cells: List[str], lane: int) -> int:
    # 進入はテーブル上だと 1 2 3 4 5 6 の単独セルで表れることが多い。
    # lane以外の単独1-6があれば優先。なければlane。
    nums = []
    for c in cells:
        if re.fullmatch(r"[1-6]", c):
            nums.append(int(c))
    for n in nums:
        if n != lane:
            return n
    return lane


def _find_exhibition_time(cells: List[str]) -> Optional[float]:
    # 展示タイムは6.xxが中心
    for c in cells:
        for m in re.findall(r"(?<!\d)(6\.\d{2}|7\.\d{2})(?!\d)", c):
            v = _safe_float(m, 0.0)
            if 6.0 <= v <= 8.5:
                return v
    return None


def _find_start_timing(cells: List[str]) -> Optional[float]:
    # STは .12 / F.05 / L.12 / 0.12 等
    for c in cells:
        m = re.search(r"([FL]?\.?\d{2,3})", c)
        if not m:
            continue
        raw = m.group(1)
        # 6.75等の展示タイムを誤検出しない
        if re.match(r"^[67]\.", raw):
            continue
        v = _safe_float(raw, 999.0)
        if 0.0 <= v <= 1.0:
            return v
    return None


def _find_tilt(cells: List[str]) -> Optional[float]:
    joined = " ".join(cells)
    # チルト候補。展示タイム/STとの混同を避けるため「チルト」周辺を優先
    m = re.search(r"チルト\s*(-?[0-3](?:\.\d)?)", joined)
    if m:
        return _safe_float(m.group(1), None)
    # 最後のほうに -0.5 / 0.0 / 0.5 / 1.0 等があれば候補
    vals = []
    for c in cells:
        if re.fullmatch(r"-?0(?:\.0|\.5)?|[123](?:\.0)?", c):
            vals.append(_safe_float(c, None))
    if vals:
        return vals[-1]
    return None


def _extract_exhibition_time_values(cells: List[str]) -> List[float]:
    vals: List[float] = []
    for c in cells:
        # 展示タイムは通常 6.xx / 7.xx
        for m in re.findall(r"(?<!\d)([67]\.\d{2})(?!\d)", c):
            v = _safe_float(m, 0.0)
            if 6.0 <= v <= 8.5:
                vals.append(v)
    return vals


def _extract_start_values(cells: List[str]) -> List[float]:
    vals: List[float] = []
    joined = " ".join(cells)

    # ST/スタート展示行を優先。F/Lは数値化では一旦絶対値として保存し、rawに残す。
    if ("ST" not in joined.upper()) and ("スタート" not in joined) and ("S展示" not in joined):
        # 行名が無い場合でも .xx が6個以上あれば候補。ただし展示タイム行は除外。
        if len(_extract_exhibition_time_values(cells)) >= 4:
            return vals

    for c in cells:
        for m in re.findall(r"(?<!\d)([FL]?\.\d{2}|[FL]?0\.\d{2})(?!\d)", c, flags=re.IGNORECASE):
            v = _safe_float(m, 999.0)
            if 0.0 <= v <= 1.0:
                vals.append(v)
    return vals


def _extract_tilt_values(cells: List[str]) -> List[float]:
    joined = " ".join(cells)
    if "チルト" not in joined and "tilt" not in joined.lower():
        return []
    vals: List[float] = []
    # チルトは -0.5 / 0 / 0.0 / 0.5 / 1.0 / 1.5 / 2.0 / 3.0 など
    for c in cells:
        for m in re.findall(r"(?<!\d)(-?0(?:\.[05])?|[123](?:\.[05])?)(?!\d)", c):
            v = _safe_float(m, 999.0)
            if -1.0 <= v <= 3.0:
                vals.append(v)
    # 先頭に行名/艇番由来の0や1が混ざることがあるため、7個以上なら後ろ6個を採用
    if len(vals) >= 6:
        return vals[-6:]
    return vals


def _extract_course_values(cells: List[str]) -> List[int]:
    joined = " ".join(cells)
    if "進入" not in joined and "コース" not in joined:
        return []
    vals: List[int] = []
    for c in cells:
        if re.fullmatch(r"[1-6]", c):
            vals.append(int(c))
    if len(vals) >= 6:
        return vals[-6:]
    return vals


def _rank_and_diff(rows: List[Dict[str, Any]], value_key: str, rank_key: str, diff_key: str, lower_is_better: bool = True) -> None:
    vals = [(r["lane"], r.get(value_key)) for r in rows if r.get(value_key) is not None]
    if not vals:
        return
    vals = sorted(vals, key=lambda x: x[1], reverse=not lower_is_better)
    best = vals[0][1]
    ranks = {lane: i + 1 for i, (lane, _) in enumerate(vals)}
    for r in rows:
        if r.get(value_key) is not None:
            r[rank_key] = ranks.get(r["lane"])
            r[diff_key] = round(float(r[value_key]) - float(best), 3)


def parse_exhibition(html: str) -> List[Dict[str, Any]]:
    """beforeinfoのHTMLから6艇分の展示情報をできるだけ復元する。

    旧版は「1レース1行」しか拾えないケースがあったため、
    公式ページでよくある「行名 + 6艇分の横並び値」の形を優先して解析する。
    """
    rows = _extract_table_rows(html)

    by_lane: Dict[int, Dict[str, Any]] = {
        lane: {
            "lane": lane,
            "exhibition_course": lane,
            "raw_cells": [],
        }
        for lane in range(1, 7)
    }

    found_times = False
    found_st = False
    found_tilt = False
    found_course = False

    for cells in rows:
        joined = " ".join(cells)

        times = _extract_exhibition_time_values(cells)
        if len(times) >= 6 and (not found_times or "展示" in joined):
            for lane, val in enumerate(times[:6], start=1):
                by_lane[lane]["exhibition_time"] = val
                by_lane[lane].setdefault("raw_cells", []).append(cells)
            found_times = True
            continue

        sts = _extract_start_values(cells)
        if len(sts) >= 6 and (not found_st or "ST" in joined.upper() or "スタート" in joined):
            for lane, val in enumerate(sts[:6], start=1):
                by_lane[lane]["start_timing"] = val
                by_lane[lane].setdefault("raw_cells", []).append(cells)
            found_st = True
            continue

        tilts = _extract_tilt_values(cells)
        if len(tilts) >= 6:
            for lane, val in enumerate(tilts[:6], start=1):
                by_lane[lane]["tilt"] = val
                by_lane[lane].setdefault("raw_cells", []).append(cells)
            found_tilt = True
            continue

        courses = _extract_course_values(cells)
        if len(courses) >= 6:
            for lane, val in enumerate(courses[:6], start=1):
                if 1 <= val <= 6:
                    by_lane[lane]["exhibition_course"] = val
                    by_lane[lane].setdefault("raw_cells", []).append(cells)
            found_course = True
            continue

        # 縦持ちテーブル用の保険。1行に lane + 展示タイム/ST がある場合。
        lane = _find_lane_in_cells(cells)
        if lane:
            ex_time = _find_exhibition_time(cells)
            st = _find_start_timing(cells)
            tilt = _find_tilt(cells)
            if ex_time is not None:
                by_lane[lane]["exhibition_time"] = ex_time
            if st is not None:
                by_lane[lane]["start_timing"] = st
            if tilt is not None:
                by_lane[lane]["tilt"] = tilt
            if ex_time is not None or st is not None or tilt is not None:
                by_lane[lane]["exhibition_course"] = _find_exhibition_course(cells, lane)
                by_lane[lane].setdefault("raw_cells", []).append(cells)

    out: List[Dict[str, Any]] = []
    for lane in range(1, 7):
        r = by_lane[lane]
        # 展示タイム/ST/チルト/進入のいずれかがあれば保存。
        if (
            r.get("exhibition_time") is not None
            or r.get("start_timing") is not None
            or r.get("tilt") is not None
            or r.get("exhibition_course") != lane
        ):
            out.append(r)

    # 公式beforeinfoは展示前でも別表の数字を拾ってしまうことがある。
    # 3艇だけ等の半端な解析は誤検出の可能性が高いので、デフォルトでは保存しない。
    # 欠場等で5艇保存したい場合のみ PARSE_ALLOW_PARTIAL=1 を使う。
    if len(out) < 6 and not PARSE_ALLOW_PARTIAL:
        return []

    _rank_and_diff(out, "exhibition_time", "exhibition_time_rank", "exhibition_time_diff", lower_is_better=True)
    _rank_and_diff(out, "start_timing", "start_timing_rank", "start_timing_diff", lower_is_better=True)

    return out



def parse_odds3t(html: str) -> Dict[str, float]:
    if not html:
        return {}
    text = _soup_text(html)
    odds: Dict[str, float] = {}

    # pattern 1: 1-2-3 4.5
    for m in re.finditer(r"([1-6])\s*[-－]\s*([1-6])\s*[-－]\s*([1-6])\s+([0-9]{1,4}(?:\.[0-9])?)", text):
        a, b, c, o = m.groups()
        t = f"{a}-{b}-{c}"
        v = _safe_float(o, 0.0)
        if v > 0:
            odds[t] = v

    # pattern 2: HTML内の投票組番とオッズが近接している場合
    if len(odds) < 80 and BeautifulSoup is not None:
        rows = _extract_table_rows(html)
        for cells in rows:
            joined = " ".join(cells)
            nums = re.findall(r"[1-6]", joined)
            if len(nums) < 3:
                continue
            ticket = f"{nums[0]}-{nums[1]}-{nums[2]}"
            # オッズ候補
            vals = []
            for c in cells:
                for x in re.findall(r"(?<!\d)([0-9]{1,4}\.[0-9])(?!\d)", c):
                    vals.append(_safe_float(x, 0.0))
            if vals:
                v = vals[-1]
                if v > 0:
                    odds[ticket] = v

    return odds


# ============================================================
# DB data helpers
# ============================================================

def fetch_day_base(date_str: str) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, float]]]:
    day_prefix = _rid_prefix(date_str)
    next_prefix = _rid_prefix(_next_day(date_str))

    races = _rest_get(
        "v2_races",
        {
            "select": "*",
            "race_date": f"eq.{date_str}",
            "order": "venue_id.asc,race_no.asc",
        },
    )
    races = [r for r in races if str(r.get("venue_id", "")).zfill(2) in TARGET_VENUES]
    if TARGET_RACE_ID:
        races = [r for r in races if str(r.get("race_id")) == TARGET_RACE_ID]

    entries_rows = _rest_get_range(
        "v2_race_entries",
        select="race_id,lane,racer_number,racer_name,racer_class,motor_no,boat_no,tilt",
        col="race_id",
        gte=day_prefix,
        lt=next_prefix,
    )
    entries_by_race: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in entries_rows:
        entries_by_race[str(e.get("race_id"))].append(e)

    odds_rows = _rest_get_range(
        "v2_odds_trifecta",
        select="race_id,ticket,odds",
        col="race_id",
        gte=day_prefix,
        lt=next_prefix,
        page_size=ODDS_PAGE_SIZE,
    )
    odds_by_race: Dict[str, Dict[str, float]] = defaultdict(dict)
    for o in odds_rows:
        rid = str(o.get("race_id"))
        t = _norm_ticket(o.get("ticket"))
        v = _safe_float(o.get("odds"), 0.0)
        if rid and t and v > 0:
            odds_by_race[rid][t] = v

    return races, entries_by_race, odds_by_race


def _fetch_previous_odds(race_id: str, snapshot_label: str) -> Dict[str, Dict[str, Any]]:
    rows = _rest_get(
        "v2_realtime_odds_snapshots",
        {
            "select": "ticket,odds,market_rank,snapshot_at",
            "race_id": f"eq.{race_id}",
            "order": "snapshot_at.desc",
            "limit": "240",
        },
    )
    out = {}
    for r in rows:
        t = _norm_ticket(r.get("ticket"))
        if t and t not in out:
            out[t] = r
    return out


# ============================================================
# candidate scope helpers
# ============================================================

def _infer_venue_style(venue_id: str) -> str:
    v = str(venue_id).zfill(2)
    if v in BAD5_VENUES:
        return "bad5"
    if v in ROUGH_VENUES:
        return "rough"
    if v in IN_STRONG_VENUES:
        return "in_strong"
    return "standard"


def _event_day_by_venue(date_str: str) -> Dict[str, int]:
    start = _shift_day(date_str, -10)
    rows = _rest_get(
        "v2_races",
        {
            "select": "race_id,race_date,venue_id,race_no",
            "race_date": f"gte.{start}",
            "order": "race_date.asc,venue_id.asc,race_no.asc",
        },
    )
    dates_by_venue: Dict[str, List[str]] = defaultdict(list)
    for r in rows:
        d = str(r.get("race_date", ""))
        if d > date_str:
            continue
        v = str(r.get("venue_id", "")).zfill(2)
        if d and d not in dates_by_venue[v]:
            dates_by_venue[v].append(d)

    out = {}
    for v, ds in dates_by_venue.items():
        cur = 0
        prev = ""
        for d in sorted(ds):
            if prev and d == _shift_day(prev, 1):
                cur += 1
            else:
                cur = 1
            prev = d
            if d == date_str:
                out[v] = cur
    return out


def _race_group(race_no: int) -> str:
    if 1 <= race_no <= 3:
        return "R01_03"
    if 4 <= race_no <= 6:
        return "R04_06"
    if 7 <= race_no <= 9:
        return "R07_09"
    return "R10_12"


def _is_candidate_race(venue_id: str, race_no: int, event_day_no: int) -> bool:
    """v19/v18通常モード候補に近いレースだけを収集するための軽量フィルター。"""
    style = _infer_venue_style(venue_id)

    # mode_balanced_venue_best
    venue_best = (
        (style == "bad5" and 4 <= race_no <= 9)
        or (style == "in_strong" and (1 <= race_no <= 3 or 7 <= race_no <= 9))
    )

    # mode_intersection/day best寄り
    day_best = (
        (event_day_no in (2, 3) and 4 <= race_no <= 9)
        or (event_day_no >= 6 and (1 <= race_no <= 3 or 7 <= race_no <= 9))
    )

    return venue_best or day_best


# ============================================================
# save snapshots
# ============================================================

def save_weather(race: Dict[str, Any], weather: Dict[str, Any]) -> int:
    rid = str(race.get("race_id"))
    row = {
        "race_id": rid,
        "race_date": race.get("race_date"),
        "venue_id": str(race.get("venue_id", "")).zfill(2),
        "race_no": _safe_int(race.get("race_no"), 0),
        "snapshot_label": SNAPSHOT_LABEL,
        "snapshot_at": _now_iso(),
        "source": "official_beforeinfo",
        "weather": weather.get("weather"),
        "temperature_c": weather.get("temperature_c"),
        "water_temperature_c": weather.get("water_temperature_c"),
        "wind_speed_m": weather.get("wind_speed_m"),
        "wind_direction": weather.get("wind_direction"),
        "wave_height_cm": weather.get("wave_height_cm"),
        "raw": {"text": weather.get("raw_text", "")},
        "updated_at": _now_iso(),
    }
    return _upsert("v2_realtime_weather_snapshots", [row], "race_id,snapshot_label")


def save_exhibition_and_entries(race: Dict[str, Any], entries: List[Dict[str, Any]], exh: List[Dict[str, Any]]) -> Tuple[int, int]:
    """展示snapshotとentry snapshotを保存する。

    fix2:
    - entry snapshotは展示がまだ無くても6艇分保存する。
    - exhibition snapshotは展示解析が6艇分揃った時だけ保存する。
      これにより「展示前に3艇だけ誤検出」のようなノイズを避ける。
    """
    rid = str(race.get("race_id"))
    by_lane = {_safe_int(e.get("lane"), 0): e for e in entries}
    parsed_by_lane = {_safe_int(r.get("lane"), 0): r for r in exh}
    venue_id = str(race.get("venue_id", "")).zfill(2)
    race_no = _safe_int(race.get("race_no"), 0)

    exh_rows = []
    entry_rows = []

    for lane in range(1, 7):
        e = by_lane.get(lane, {})
        r = parsed_by_lane.get(lane, {})
        original_tilt = _safe_float(e.get("tilt"), None)
        tilt = r.get("tilt")
        tilt_change = None
        if tilt is not None and original_tilt is not None:
            tilt_change = round(_safe_float(tilt, 0.0) - _safe_float(original_tilt, 0.0), 2)

        course = r.get("exhibition_course")
        raw = {"cells": r.get("raw_cells", [])}

        # entry snapshot は常に保存
        entry_rows.append({
            "race_id": rid,
            "race_date": race.get("race_date"),
            "venue_id": venue_id,
            "race_no": race_no,
            "snapshot_label": SNAPSHOT_LABEL,
            "snapshot_at": _now_iso(),
            "source": "official_beforeinfo",
            "lane": lane,
            "racer_number": e.get("racer_number"),
            "racer_name": e.get("racer_name"),
            "racer_class": str(e.get("racer_class")) if e.get("racer_class") is not None else None,
            "original_course": lane,
            "exhibition_course": course,
            "is_course_changed": bool(course and course != lane),
            "motor_no": e.get("motor_no"),
            "boat_no": e.get("boat_no"),
            "tilt": tilt,
            "raw": raw,
            "updated_at": _now_iso(),
        })

        # exhibition snapshot は解析値がある艇だけ保存
        if r:
            exh_rows.append({
                "race_id": rid,
                "race_date": race.get("race_date"),
                "venue_id": venue_id,
                "race_no": race_no,
                "snapshot_label": SNAPSHOT_LABEL,
                "snapshot_at": _now_iso(),
                "source": "official_beforeinfo",
                "lane": lane,
                "exhibition_course": course or lane,
                "exhibition_time": r.get("exhibition_time"),
                "exhibition_time_rank": r.get("exhibition_time_rank"),
                "exhibition_time_diff": r.get("exhibition_time_diff"),
                "start_timing": r.get("start_timing"),
                "start_timing_rank": r.get("start_timing_rank"),
                "start_timing_diff": r.get("start_timing_diff"),
                "tilt": tilt,
                "original_tilt": original_tilt,
                "tilt_change": tilt_change,
                "raw": raw,
                "updated_at": _now_iso(),
            })

    c1 = _upsert("v2_realtime_exhibition_snapshots", exh_rows, "race_id,snapshot_label,lane")
    c2 = _upsert("v2_realtime_entry_snapshots", entry_rows, "race_id,snapshot_label,lane")
    return c1, c2



def save_odds(race: Dict[str, Any], odds: Dict[str, float], source: str) -> int:
    rid = str(race.get("race_id"))
    venue_id = str(race.get("venue_id", "")).zfill(2)
    race_no = _safe_int(race.get("race_no"), 0)

    prev = _fetch_previous_odds(rid, SNAPSHOT_LABEL)

    ranked = sorted(odds.items(), key=lambda x: x[1])
    rank = {t: i + 1 for i, (t, _) in enumerate(ranked)}

    rows = []
    for t, o in ranked:
        p = prev.get(t, {})
        prev_o = _safe_float(p.get("odds"), None) if p else None
        prev_rank = _safe_int(p.get("market_rank"), None) if p else None
        delta = None
        delta_pct = None
        rank_delta = None
        if prev_o is not None and prev_o > 0:
            delta = round(float(o) - float(prev_o), 2)
            delta_pct = round((float(o) - float(prev_o)) / float(prev_o), 4)
        if prev_rank is not None:
            rank_delta = rank[t] - prev_rank

        rows.append({
            "race_id": rid,
            "race_date": race.get("race_date"),
            "venue_id": venue_id,
            "race_no": race_no,
            "snapshot_label": SNAPSHOT_LABEL,
            "snapshot_at": _now_iso(),
            "source": source,
            "ticket": t,
            "odds": o,
            "market_rank": rank[t],
            "prev_odds": prev_o,
            "odds_delta": delta,
            "odds_delta_pct": delta_pct,
            "prev_market_rank": prev_rank,
            "market_rank_delta": rank_delta,
            "is_favorite": rank[t] == 1,
            "is_odds_too_low": o < 3.0,
            "is_odds_drift": bool(delta_pct is not None and delta_pct >= 0.15),
            "is_odds_steam": bool(delta_pct is not None and delta_pct <= -0.15),
            "raw": {},
            "updated_at": _now_iso(),
        })

    return _upsert("v2_realtime_odds_snapshots", rows, "race_id,snapshot_label,ticket", chunk_size=500)


# ============================================================
# main
# ============================================================

def main() -> None:
    _require_settings()
    print("✅ v21_realtime_collector_fix2.py VERSION 2026-06-23 realtime-collector-fix2", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} SCOPE={COLLECT_SCOPE} TARGET_RACE_ID={TARGET_RACE_ID or '-'} PARSE_ALLOW_PARTIAL={PARSE_ALLOW_PARTIAL}", flush=True)

    races, entries_by_race, base_odds_by_race = fetch_day_base(TARGET_DATE)
    event_days = _event_day_by_venue(TARGET_DATE)

    target_races = []
    for race in races:
        rid = str(race.get("race_id"))
        venue_id = str(race.get("venue_id", "")).zfill(2)
        race_no = _safe_int(race.get("race_no"), 0)
        if TARGET_RACE_ID and rid != TARGET_RACE_ID:
            continue
        if COLLECT_SCOPE == "candidates":
            if not _is_candidate_race(venue_id, race_no, event_days.get(venue_id, 1)):
                continue
        target_races.append(race)

    print(f"races={len(races)} target_races={len(target_races)}", flush=True)

    saved_weather = 0
    saved_exh = 0
    saved_entry = 0
    saved_odds = 0
    no_beforeinfo = 0
    no_exhibition = 0
    no_odds = 0

    for idx, race in enumerate(target_races, start=1):
        rid = str(race.get("race_id"))
        venue_id = str(race.get("venue_id", "")).zfill(2)
        race_no = _safe_int(race.get("race_no"), 0)

        before_url = _official_url("beforeinfo", TARGET_DATE, venue_id, race_no)
        before_html = _fetch(before_url)

        if _looks_no_data(before_html):
            no_beforeinfo += 1
            c1, c2 = save_exhibition_and_entries(race, entries_by_race.get(rid, []), [])
            saved_exh += c1
            saved_entry += c2
        else:
            weather = parse_weather(before_html or "")
            saved_weather += save_weather(race, weather)

            exh = parse_exhibition(before_html or "")
            if not exh:
                no_exhibition += 1
            c1, c2 = save_exhibition_and_entries(race, entries_by_race.get(rid, []), exh)
            saved_exh += c1
            saved_entry += c2

        odds_url = _official_url("odds3t", TARGET_DATE, venue_id, race_no)
        odds_html = _fetch(odds_url)
        odds = parse_odds3t(odds_html or "") if odds_html else {}
        source = "official_odds3t"

        if len(odds) < 80:
            # fallback: 既存v2_odds_trifecta。リアルタイムではないがsnapshotテーブルの動作確認に使える。
            fallback = base_odds_by_race.get(rid, {})
            if fallback:
                odds = fallback
                source = "v2_odds_trifecta_fallback"

        if odds:
            saved_odds += save_odds(race, odds, source)
        else:
            no_odds += 1

        print(
            f"[{idx}/{len(target_races)}] {rid} before={'ok' if before_html else 'ng'} "
            f"exh_rows={len(exh) if before_html and not _looks_no_data(before_html) else 0} "
            f"odds={len(odds)} source={source if odds else '-'}",
            flush=True,
        )

        if REALTIME_SLEEP_SEC > 0:
            time.sleep(REALTIME_SLEEP_SEC)

    print("\n=== v21 realtime collection summary ===", flush=True)
    print(f"target_races: {len(target_races)}", flush=True)
    print(f"saved_weather: {saved_weather}", flush=True)
    print(f"saved_exhibition_rows: {saved_exh}", flush=True)
    print(f"saved_entry_rows: {saved_entry}", flush=True)
    print(f"saved_odds_rows: {saved_odds}", flush=True)
    print(f"no_beforeinfo: {no_beforeinfo}", flush=True)
    print(f"no_exhibition_complete: {no_exhibition}", flush=True)
    print(f"no_odds: {no_odds}", flush=True)
    print("=== v21 リアルタイム収集終了 ===", flush=True)


if __name__ == "__main__":
    main()