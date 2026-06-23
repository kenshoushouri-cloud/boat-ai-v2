# -*- coding: utf-8 -*-
"""
repair_race_title_backfill_v16.py

競艇AI v2用・v2_races.race_title 補修スクリプト。

v16 probeで確認したこと:
- v2_races には race_title と session_type が存在する
- ただし 2025年〜2026年5月の多くは race_title がNULL
- グレード/女子/一般カテゴリ診断には race_title が必要

目的:
- v2_races から race_title 欠落レースを抽出
- 日付×場ごとに公式racelistを1ページ取得して開催タイトルを抽出
- 同じ日付×場の欠落レースへ race_title を一括補修

Railway Start Command:
    python repair_race_title_backfill_v16.py

任意Variables:
    START_DATE=2025-03-13
    END_DATE=2026-05-31
    TITLE_SLEEP_SEC=0.15
    TITLE_MAX_GROUPS=0  # 0なら無制限
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

START_DATE = os.getenv("START_DATE", "2025-03-13")
END_DATE = os.getenv("END_DATE", "2026-05-31")
TITLE_SLEEP_SEC = float(os.getenv("TITLE_SLEEP_SEC", "0.15"))
TITLE_MAX_GROUPS = int(os.getenv("TITLE_MAX_GROUPS", "0"))

HTTP_TIMEOUT = 25
MAX_RETRIES = 2
PAGE_SIZE = 1000

OFFICIAL_VENUES = [f"{i:02d}" for i in range(1, 25)]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; boatrace-title-backfill/1.0)",
})

def _require_settings() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY が必要です。")


def _now_iso() -> str:
    return datetime.now(JST).isoformat()


def _yyyymmdd(date_str: str) -> str:
    return date_str.replace("-", "")


def _daterange(start_str: str, end_str: str) -> Iterable[str]:
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    cur = start
    while cur <= end:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)


def _race_id(date_str: str, venue_id: str, race_no: int) -> str:
    return f"{date_str.replace('-', '')}_{venue_id.zfill(2)}_{int(race_no):02d}"


def _official_url(kind: str, date_str: str, venue_id: str, race_no: int) -> str:
    return (
        f"https://www.boatrace.jp/owpc/pc/race/{kind}"
        f"?rno={int(race_no)}&jcd={venue_id.zfill(2)}&hd={_yyyymmdd(date_str)}"
    )


def _clean_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _looks_no_race(html: Optional[str]) -> bool:
    if not html:
        return True
    t = re.sub(r"\s+", " ", html)
    return (
        "データがありません" in t
        or "開催はありません" in t
        or "該当するデータはありません" in t
        or "404 Not Found" in t
    )


def _fetch(url: str) -> Optional[str]:
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            res = SESSION.get(url, timeout=HTTP_TIMEOUT)
            if res.status_code == 404:
                return None
            if not res.ok:
                last_err = f"HTTP {res.status_code}: {res.text[:120]}"
                time.sleep(0.5 + attempt * 0.5)
                continue
            res.encoding = res.apparent_encoding or "utf-8"
            return res.text
        except Exception as e:
            last_err = repr(e)
            time.sleep(0.5 + attempt * 0.5)
    print(f"⚠️ fetch failed: {url} / {last_err}", flush=True)
    return None


def parse_event_title(html: str) -> Optional[str]:
    """公式racelistページから開催タイトルを抽出する。

    BOATRACE公式ページでは開催タイトルが h2/h3/title系class に入ることが多い。
    取れない場合はテキストからSG/G1/G2/G3/杯/カップ/レディース等を含む短い候補を拾う。
    """
    if not html:
        return None

    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")

        # まず既存補修スクリプトと同系統のセレクタ
        for selector in ["h2", "h3", ".title", ".heading2", ".is-title", ".heading1"]:
            node = soup.select_one(selector)
            if not node:
                continue
            txt = _clean_text(node.get_text(" ", strip=True))
            if txt and "BOAT" not in txt.upper() and len(txt) >= 3:
                return txt[:120]

        # class名にtitleを含む要素
        for node in soup.find_all(class_=re.compile("title|heading|ttl", re.I)):
            txt = _clean_text(node.get_text(" ", strip=True))
            if txt and "BOAT" not in txt.upper() and len(txt) >= 3:
                return txt[:120]

        text = _clean_text(soup.get_text(" ", strip=True))
    else:
        text = _clean_text(re.sub(r"<[^>]+>", " ", html))

    # fallback: 開催タイトルっぽい語を含む文節を探す
    patterns = [
        r"([^\s　]{2,40}(?:SG|G1|G2|G3|ＧⅠ|ＧⅡ|ＧⅢ)[^\s　]{0,40})",
        r"([^\s　]{2,50}(?:杯|カップ|CUP|記念|周年|レディース|ヴィーナス|モーターボート大賞|ボートレース甲子園)[^\s　]{0,50})",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return _clean_text(m.group(1))[:120]

    return None


def _rest_get_range(table: str, params: Dict[str, str], page_size: int = PAGE_SIZE) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    offset = 0
    while True:
        p = dict(params)
        p["limit"] = str(page_size)
        p["offset"] = str(offset)
        query = urllib.parse.urlencode(p, safe=",.*()")
        url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
        res = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
        if res.status_code >= 400:
            raise RuntimeError(f"GET {table} failed {res.status_code}: {res.text[:500]}")
        rows = res.json()
        if not rows:
            break
        out.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def _rest_post(table: str, rows: List[Dict[str, Any]], on_conflict: str) -> int:
    if not rows:
        return 0
    query = urllib.parse.urlencode({"on_conflict": on_conflict})
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    res = requests.post(
        url,
        headers=HEADERS,
        data=json.dumps(rows, ensure_ascii=False),
        timeout=HTTP_TIMEOUT,
    )
    if res.status_code >= 400:
        raise RuntimeError(f"UPSERT {table} failed {res.status_code}: {res.text[:800]}")
    return len(rows)


def upsert_rows(table: str, rows: List[Dict[str, Any]], on_conflict: str, chunk_size: int = 500) -> int:
    total = 0
    for i in range(0, len(rows), chunk_size):
        total += _rest_post(table, rows[i:i + chunk_size], on_conflict)
    return total


def fetch_missing_title_races() -> List[Dict[str, Any]]:
    rows = _rest_get_range(
        "v2_races",
        {
            "select": "race_id,race_date,venue_id,race_no,race_title,session_type",
            "race_date": f"gte.{START_DATE}",
            "race_date": f"gte.{START_DATE}",
            "order": "race_date.asc,venue_id.asc,race_no.asc",
        },
    )
    # 上のdictでは同名key不可のため、END条件はRESTのand表現ではなくローカルで絞る
    filtered = []
    for r in rows:
        d = str(r.get("race_date", ""))
        if d < START_DATE or d > END_DATE:
            continue
        title = _clean_text(r.get("race_title"))
        if not title:
            filtered.append(r)
    return filtered


def fetch_all_races_in_range() -> List[Dict[str, Any]]:
    # PostgRESTのgte/lte同時指定を簡単にするため月単位ではなく全件取得後ローカルfilter。
    rows = _rest_get_range(
        "v2_races",
        {
            "select": "race_id,race_date,venue_id,race_no,race_title,session_type",
            "race_date": f"gte.{START_DATE}",
            "order": "race_date.asc,venue_id.asc,race_no.asc",
        },
    )
    out = []
    for r in rows:
        d = str(r.get("race_date", ""))
        if START_DATE <= d <= END_DATE:
            out.append(r)
    return out


def main() -> None:
    _require_settings()
    print("✅ repair_race_title_backfill_v16.py VERSION 2026-06-23 race-title-backfill", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)

    all_rows = fetch_all_races_in_range()
    missing = [r for r in all_rows if not _clean_text(r.get("race_title"))]
    existing = len(all_rows) - len(missing)

    print(f"v2_races rows in range: {len(all_rows)}", flush=True)
    print(f"race_title existing: {existing}", flush=True)
    print(f"race_title missing: {len(missing)}", flush=True)

    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in missing:
        groups[(str(r.get("race_date")), str(r.get("venue_id")).zfill(2))].append(r)

    group_items = sorted(groups.items(), key=lambda x: (x[0][0], x[0][1]))
    if TITLE_MAX_GROUPS > 0:
        group_items = group_items[:TITLE_MAX_GROUPS]

    print(f"target date×venue groups: {len(group_items)}", flush=True)

    success_groups = 0
    no_title_groups = 0
    saved_rows = 0
    samples: List[str] = []

    for idx, ((date_str, venue_id), rows) in enumerate(group_items, start=1):
        # その日その場で欠落している最小race_noを使う。no_raceなら1〜12で探す。
        race_nos = sorted({int(r.get("race_no") or 0) for r in rows if r.get("race_no") is not None})
        title = None
        used_rno = None

        for rno in race_nos + [i for i in range(1, 13) if i not in race_nos]:
            url = _official_url("racelist", date_str, venue_id, rno)
            html = _fetch(url)
            if _looks_no_race(html):
                continue
            title = parse_event_title(html or "")
            used_rno = rno
            if title:
                break

        if title:
            upserts = []
            for r in rows:
                upserts.append({
                    "race_id": r["race_id"],
                    "race_date": date_str,
                    "venue_id": venue_id,
                    "race_no": int(r["race_no"]),
                    "race_title": title,
                    "updated_at": _now_iso(),
                })
            saved_rows += upsert_rows("v2_races", upserts, "race_id", chunk_size=300)
            success_groups += 1
            if len(samples) < 12:
                samples.append(f"{date_str} {venue_id} r{used_rno}: {title}")
        else:
            no_title_groups += 1

        if idx == 1 or idx % 50 == 0 or idx == len(group_items):
            print(
                f"[{idx}/{len(group_items)}] ok_groups={success_groups} no_title={no_title_groups} saved_rows={saved_rows}",
                flush=True,
            )

        if TITLE_SLEEP_SEC > 0:
            time.sleep(TITLE_SLEEP_SEC)

    print("\n=== race_title補修終了 ===", flush=True)
    print(f"success_groups: {success_groups}", flush=True)
    print(f"no_title_groups: {no_title_groups}", flush=True)
    print(f"saved_rows: {saved_rows}", flush=True)
    print("samples:", flush=True)
    for s in samples:
        print(f"  {s}", flush=True)


if __name__ == "__main__":
    main()