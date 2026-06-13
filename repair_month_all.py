# -*- coding: utf-8 -*-
"""
repair_month_all.py

旧5場1R専用の repair_legacy_r1.py を全場・全R向けに広げた月次バックフィル用スクリプト。

Railway Start Command:
    python repair_month_all.py

主な環境変数:
    REPAIR_START_DATE=2026-05-01
    REPAIR_END_DATE=2026-05-31
    REPAIR_VENUES=01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
    REPAIR_RACE_NOS=1,2,3,4,5,6,7,8,9,10,11,12
    REPAIR_DO_RACES=1
    REPAIR_DO_RESULTS=1
    REPAIR_DO_ODDS=1
    REPAIR_SLEEP_SEC=0.1
    REPAIR_WORKERS=6
    REPAIR_ODDS_WORKERS=2

注意:
- v2_venues の全24場マスタを先に upsert します。
- BOATRACE公式HTMLの構造変更に備え、パーサは安全寄りです。
- entries の完全取得に失敗しても、race/result/odds は保存を続行します。
- odds は公式 odds3t ページから保存します。既存の odds_seed_job は使いません。
"""

from __future__ import annotations

import os
import re
import time
import json
import itertools
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


# ============================================================
# Settings
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)

START_DATE = os.getenv("REPAIR_START_DATE") or os.getenv("START_DATE") or "2026-05-01"
END_DATE = os.getenv("REPAIR_END_DATE") or os.getenv("END_DATE") or "2026-05-31"

ALL_VENUES = [f"{i:02d}" for i in range(1, 25)]
DEFAULT_RACE_NOS = [str(i) for i in range(1, 13)]

REPAIR_VENUES = [
    v.strip().zfill(2)
    for v in (os.getenv("REPAIR_VENUES") or os.getenv("TARGET_VENUES") or ",".join(ALL_VENUES)).split(",")
    if v.strip()
]
REPAIR_RACE_NOS = [
    int(x.strip())
    for x in (os.getenv("REPAIR_RACE_NOS") or os.getenv("RACE_NOS") or ",".join(DEFAULT_RACE_NOS)).split(",")
    if x.strip()
]

DO_RACES = (os.getenv("REPAIR_DO_RACES") or os.getenv("DO_RACES") or "1") == "1"
DO_RESULTS = (os.getenv("REPAIR_DO_RESULTS") or os.getenv("DO_RESULTS") or "1") == "1"
DO_ODDS = (os.getenv("REPAIR_DO_ODDS") or os.getenv("DO_ODDS") or "1") == "1"

SLEEP_SEC = float(os.getenv("REPAIR_SLEEP_SEC") or os.getenv("SLEEP_SEC") or "0.1")
WORKERS = int(os.getenv("REPAIR_WORKERS") or os.getenv("WORKERS") or "6")
ODDS_WORKERS = int(os.getenv("REPAIR_ODDS_WORKERS") or os.getenv("ODDS_WORKERS") or "2")

HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT") or "25")
MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES") or "2")

SOURCE = os.getenv("REPAIR_SOURCE") or "repair_month_all"

JST = timezone(timedelta(hours=9))

VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "常滑",
    "07": "蒲郡", "08": "津", "09": "三国", "10": "びわこ", "11": "住之江", "12": "尼崎",
    "13": "鳴門", "14": "丸亀", "15": "児島", "16": "宮島", "17": "徳山", "18": "下関",
    "19": "若松", "20": "芦屋", "21": "福岡", "22": "唐津", "23": "大村", "24": "大村",
}
# 以前のDBでは 24=大村 として扱っているため 23/24 のズレがある場合でも race_id 優先で運用します。
# BOATRACE公式の jcd は 24=大村です。23は存在しない/予備扱いの場合があります。
OFFICIAL_VENUES = [f"{i:02d}" for i in range(1, 25)]
VENUE_NAMES.update({"23": "唐津", "24": "大村"})

CLASS_MAP = {"B2": 1, "B1": 2, "A2": 3, "A1": 4}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2/1.0; +https://boatrace.jp)",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
})

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


# ============================================================
# Utility
# ============================================================

def _now_iso() -> str:
    return datetime.now(JST).isoformat()


def _race_id(date_str: str, venue_id: str, race_no: int) -> str:
    return f"{date_str.replace('-', '')}_{venue_id.zfill(2)}_{int(race_no):02d}"


def _yyyymmdd(date_str: str) -> str:
    return date_str.replace("-", "")


def _daterange(start_str: str, end_str: str) -> Iterable[str]:
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    cur = start
    while cur <= end:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)


def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s in ("-", "--", "欠", "欠場"):
        return None
    m = re.search(r"-?\d+", s)
    return int(m.group(0)) if m else None


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s in ("-", "--", "欠", "欠場"):
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def _clean_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(" ", strip=True)


def _official_url(kind: str, date_str: str, venue_id: str, race_no: int) -> str:
    # kind: racelist, raceresult, odds3t
    return (
        f"https://www.boatrace.jp/owpc/pc/race/{kind}"
        f"?rno={int(race_no)}&jcd={venue_id.zfill(2)}&hd={_yyyymmdd(date_str)}"
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
            last_err = str(e)
            time.sleep(0.5 + attempt * 0.5)
    print(f"fetch failed: {url} err={last_err}", flush=True)
    return None


def _looks_no_race(html: Optional[str]) -> bool:
    if not html:
        return True
    t = _html_text(html)
    ng_words = ["データがありません", "レース情報がありません", "該当するデータはありません", "発売しておりません"]
    return any(w in t for w in ng_words)


# ============================================================
# Supabase REST
# ============================================================

def _require_settings() -> None:
    print("✅ SETTINGS CHECK", flush=True)
    print(f"SUPABASE_URL: {SUPABASE_URL}", flush=True)
    print(f"SUPABASE_KEY: {'OK' if bool(SUPABASE_KEY) else 'MISSING'}", flush=True)
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY が未設定です")


def _rest_post(table: str, rows: List[Dict[str, Any]], on_conflict: str) -> int:
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    res = requests.post(url, headers=HEADERS, data=json.dumps(rows, ensure_ascii=False), timeout=40)
    if not res.ok:
        raise RuntimeError(f"upsert {table} failed {res.status_code}: {res.text[:800]}")
    return len(rows)


def upsert_rows(table: str, rows: List[Dict[str, Any]], on_conflict: str, chunk_size: int = 500) -> int:
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        total += _rest_post(table, chunk, on_conflict)
    return total


def ensure_venues() -> None:
    rows = []
    for vid in OFFICIAL_VENUES:
        rows.append({
            "venue_id": vid,
            "venue_name": VENUE_NAMES.get(vid, vid),
            "is_active": True,
            "priority": int(vid),
            "updated_at": _now_iso(),
        })
    upsert_rows("v2_venues", rows, "venue_id", chunk_size=100)
    print(f"✅ v2_venues upsert: {len(rows)}", flush=True)


# ============================================================
# Parsers
# ============================================================

def parse_race_name(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    for selector in ["h2", "h3", ".title", ".heading2", ".is-title"]:
        node = soup.select_one(selector)
        if node:
            txt = _clean_text(node.get_text(" ", strip=True))
            if txt and "BOAT" not in txt.upper():
                return txt[:100]
    t = _html_text(html)
    m = re.search(r"(第\d+R|\d+R)\s*([^\s]+)", t)
    return m.group(0)[:100] if m else None


def parse_entries(html: str, race_id: str) -> List[Dict[str, Any]]:
    """BOATRACE racelist HTMLから出走表をできる範囲で抽出する。"""
    soup = BeautifulSoup(html, "html.parser")
    entries: Dict[int, Dict[str, Any]] = {}

    # 1) tr/cell ベース。公式HTMLの揺れに強め。
    for tr in soup.find_all("tr"):
        cells = [_clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        row_text = " ".join(cells)
        lane = None
        # 最初の1〜2セルに枠番が入ることが多い
        for c in cells[:3]:
            if re.fullmatch(r"[1-6]", c):
                lane = int(c)
                break
        if lane is None:
            m_lane = re.match(r"^\s*([1-6])\b", row_text)
            if m_lane:
                lane = int(m_lane.group(1))
        if lane is None:
            continue

        m_no = re.search(r"\b(\d{4})\b", row_text)
        cls = re.search(r"\b(A1|A2|B1|B2)\b", row_text)
        if not m_no and not cls:
            continue

        racer_number = _to_int(m_no.group(1)) if m_no else None
        racer_class = CLASS_MAP.get(cls.group(1)) if cls else None

        # 選手名は4桁登録番号の直後付近からざっくり抽出
        racer_name = None
        if m_no:
            after = row_text[m_no.end():]
            # クラスや支部までを除外し、漢字/かな/カナ/英字の塊を拾う
            m_name = re.search(r"([一-龥ぁ-んァ-ヶーA-Za-z　 ]{2,20})", after)
            if m_name:
                racer_name = _clean_text(m_name.group(1))
                racer_name = re.sub(r"\b(A1|A2|B1|B2)\b.*$", "", racer_name).strip()

        nums_float = [_to_float(x) for x in re.findall(r"\d+\.\d+", row_text)]
        # 公式の並びが完全には固定できないため、勝率/2連率の候補だけ入れる
        national_win_rate = nums_float[0] if len(nums_float) > 0 else None
        national_place2_rate = nums_float[1] if len(nums_float) > 1 else None
        local_win_rate = nums_float[2] if len(nums_float) > 2 else None
        local_place2_rate = nums_float[3] if len(nums_float) > 3 else None

        # motor/boat番号は行末側の整数から推定。なければNone。
        ints = [_to_int(x) for x in re.findall(r"\b\d{1,3}\b", row_text)]
        ints = [x for x in ints if x is not None]
        motor_no = ints[-4] if len(ints) >= 4 else None
        boat_no = ints[-2] if len(ints) >= 2 else None

        entries[lane] = {
            "race_id": race_id,
            "lane": lane,
            "course": lane,
            "racer_number": racer_number,
            "racer_name": racer_name,
            "racer_class": racer_class,
            "national_win_rate": national_win_rate,
            "national_place2_rate": national_place2_rate,
            "local_win_rate": local_win_rate,
            "local_place2_rate": local_place2_rate,
            "motor_no": motor_no,
            "boat_no": boat_no,
            "recent_form": [],
            "updated_at": _now_iso(),
        }

    # 2) 最低限、枠番だけでも6艇分を作る。ただし実出走表が見えた場合のみ。
    if entries:
        for lane in range(1, 7):
            entries.setdefault(lane, {
                "race_id": race_id,
                "lane": lane,
                "course": lane,
                "recent_form": [],
                "updated_at": _now_iso(),
            })

    return [entries[k] for k in sorted(entries)]


def parse_result(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    text = _html_text(html)

    result: Dict[str, Any] = {
        "result_status": "official",
        "race_status": "official",
        "source": SOURCE,
        "fetched_at": _now_iso(),
    }

    # 着順テーブルから first〜sixth を取得
    finish: Dict[int, int] = {}
    for tr in soup.find_all("tr"):
        cells = [_clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        rank = _to_int(cells[0])
        lane = _to_int(cells[1])
        if rank and lane and 1 <= rank <= 6 and 1 <= lane <= 6:
            finish[rank] = lane

    # フォールバック: テキストから「1 4」「2 1」「3 2」的な並びを拾う
    if len(finish) < 3:
        for m in re.finditer(r"(?:^|\s)([1-6])\s+([1-6])\s+", text):
            rank = int(m.group(1)); lane = int(m.group(2))
            if rank not in finish and 1 <= lane <= 6:
                finish[rank] = lane
            if len(finish) >= 6:
                break

    keys = ["first_lane", "second_lane", "third_lane", "fourth_lane", "fifth_lane", "sixth_lane"]
    for rank, key in enumerate(keys, start=1):
        if rank in finish:
            result[key] = finish[rank]

    # 3連単払戻
    # 例: 3連単 1-2-4 470円 / 3連単 1 2 4 ¥470
    m_tri = re.search(r"3\s*連\s*単\s*([1-6])\s*[-－]?\s*([1-6])\s*[-－]?\s*([1-6])\s*[¥￥]?\s*([\d,]+)\s*円?", text)
    if m_tri:
        result["first_lane"] = int(m_tri.group(1))
        result["second_lane"] = int(m_tri.group(2))
        result["third_lane"] = int(m_tri.group(3))
        result["trifecta_payout_yen"] = int(m_tri.group(4).replace(",", ""))
    else:
        # 払戻だけ拾う補助
        m_pay = re.search(r"3\s*連\s*単.*?[¥￥]?\s*([\d,]{2,})\s*円", text)
        if m_pay:
            result["trifecta_payout_yen"] = int(m_pay.group(1).replace(",", ""))

    # 2連単払戻が列にあるDBなら保存される。なければSupabase側で列なしエラーになるため下のsafe_upsertで落ちる可能性あり。
    # このスクリプトでは列互換性を優先し、exacta系は保存しない。

    if "first_lane" not in result or "second_lane" not in result or "third_lane" not in result:
        # 結果ページは存在するが3連単が取れない場合
        result["result_status"] = "parse_incomplete"
        result["race_status"] = "parse_incomplete"
        result.setdefault("trifecta_payout_yen", 0)

    return result


def parse_odds3t(html: str, race_id: str) -> List[Dict[str, Any]]:
    text = _html_text(html)
    rows: Dict[str, Dict[str, Any]] = {}

    # 1) 直接 ticket odds パターン
    for m in re.finditer(r"([1-6])\s*[-－]\s*([1-6])\s*[-－]\s*([1-6])\s+([0-9]+(?:\.[0-9]+)?)", text):
        a, b, c = m.group(1), m.group(2), m.group(3)
        if len({a, b, c}) < 3:
            continue
        ticket = f"{a}-{b}-{c}"
        rows[ticket] = {
            "race_id": race_id,
            "ticket": ticket,
            "odds": float(m.group(4)),
            "source": "boatrace_web",
            "is_final": True,
            "fetched_at": _now_iso(),
        }

    # 2) 公式ページでハイフン無し表示の場合の補助。
    # 完全ではないが、数字3つ + odds を近接で拾う。
    if len(rows) < 100:
        compact = re.sub(r"\s+", " ", text)
        for m in re.finditer(r"\b([1-6])\s+([1-6])\s+([1-6])\s+([0-9]+(?:\.[0-9]+)?)\b", compact):
            a, b, c = m.group(1), m.group(2), m.group(3)
            if len({a, b, c}) < 3:
                continue
            ticket = f"{a}-{b}-{c}"
            odd = float(m.group(4))
            # 0.0 や異常値は除外
            if odd <= 0:
                continue
            rows[ticket] = {
                "race_id": race_id,
                "ticket": ticket,
                "odds": odd,
                "source": "boatrace_web",
                "is_final": True,
                "fetched_at": _now_iso(),
            }

    # 3) 過剰検出時は120通りの正規ticketだけに絞る
    valid_tickets = {
        f"{a}-{b}-{c}"
        for a, b, c in itertools.permutations([1, 2, 3, 4, 5, 6], 3)
    }
    filtered = [v for k, v in rows.items() if k in valid_tickets]
    return sorted(filtered, key=lambda r: tuple(map(int, r["ticket"].split("-"))))


# ============================================================
# Process one race
# ============================================================

@dataclass
class RaceResult:
    race_id: str
    ok: bool
    no_race: bool = False
    race_saved: int = 0
    entries_saved: int = 0
    result_saved: int = 0
    odds_saved: int = 0
    error: Optional[str] = None


def process_race(date_str: str, venue_id: str, race_no: int, do_odds: bool = False) -> RaceResult:
    rid = _race_id(date_str, venue_id, race_no)
    try:
        race_saved = 0
        entries_saved = 0
        result_saved = 0
        odds_saved = 0

        if DO_RACES:
            url = _official_url("racelist", date_str, venue_id, race_no)
            html = _fetch(url)
            if _looks_no_race(html):
                return RaceResult(race_id=rid, ok=False, no_race=True, error="no_race")

            race_row = {
                "race_id": rid,
                "race_date": date_str,
                "venue_id": venue_id,
                "venue_name": VENUE_NAMES.get(venue_id, venue_id),
                "race_no": int(race_no),
                "race_name": parse_race_name(html or ""),
                "status": "official" if DO_RESULTS else "scheduled",
                "data_quality_score": 0,
                "missing_count": 0,
                "updated_at": _now_iso(),
            }
            race_saved = upsert_rows("v2_races", [race_row], "race_id", chunk_size=1)

            entries = parse_entries(html or "", rid)
            if entries:
                entries_saved = upsert_rows("v2_race_entries", entries, "race_id,lane", chunk_size=20)

        if DO_RESULTS:
            url = _official_url("raceresult", date_str, venue_id, race_no)
            html = _fetch(url)
            if not _looks_no_race(html):
                res_row = parse_result(html or "")
                res_row["race_id"] = rid
                # trifecta_ticket は生成列の可能性が高いため入れない
                result_saved = upsert_rows("v2_results", [res_row], "race_id", chunk_size=1)

        if do_odds and DO_ODDS:
            url = _official_url("odds3t", date_str, venue_id, race_no)
            html = _fetch(url)
            if not _looks_no_race(html):
                odds = parse_odds3t(html or "", rid)
                if odds:
                    odds_saved = upsert_rows("v2_odds_trifecta", odds, "race_id,ticket,source", chunk_size=300)

        if SLEEP_SEC > 0:
            time.sleep(SLEEP_SEC)

        return RaceResult(
            race_id=rid,
            ok=True,
            race_saved=race_saved,
            entries_saved=entries_saved,
            result_saved=result_saved,
            odds_saved=odds_saved,
        )
    except Exception as e:
        return RaceResult(race_id=rid, ok=False, error=f"{type(e).__name__}: {e}")


# ============================================================
# Main
# ============================================================

def main() -> None:
    _require_settings()
    ensure_venues()

    dates = list(_daterange(START_DATE, END_DATE))
    venues = REPAIR_VENUES
    race_nos = REPAIR_RACE_NOS

    tasks = [(d, v, r) for d in dates for v in venues for r in race_nos]

    print("=== 全場・全R 月次補修開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"venues: {','.join(venues)}", flush=True)
    print(f"race_nos: {','.join(map(str, race_nos))}", flush=True)
    print(f"DO_RACES={DO_RACES} DO_RESULTS={DO_RESULTS} DO_ODDS={DO_ODDS}", flush=True)
    print(f"WORKERS={WORKERS} ODDS_WORKERS={ODDS_WORKERS} SLEEP_SEC={SLEEP_SEC}", flush=True)
    print(f"task_count: {len(tasks)}", flush=True)

    total_race_saved = 0
    total_entries_saved = 0
    total_result_saved = 0
    total_odds_saved = 0
    success = 0
    no_race = 0
    failed: List[RaceResult] = []

    # race / result は多めに並列
    with ThreadPoolExecutor(max_workers=max(1, WORKERS)) as ex:
        futures = {ex.submit(process_race, d, v, r, False): (d, v, r) for d, v, r in tasks}
        for idx, fut in enumerate(as_completed(futures), start=1):
            rr = fut.result()
            if rr.ok:
                success += 1
                total_race_saved += rr.race_saved
                total_entries_saved += rr.entries_saved
                total_result_saved += rr.result_saved
            elif rr.no_race:
                no_race += 1
            else:
                failed.append(rr)

            if idx % 100 == 0 or idx == len(tasks):
                print(
                    f"progress race/result: {idx}/{len(tasks)} success={success} no_race={no_race} failed={len(failed)}",
                    flush=True,
                )

    # odds は控えめに並列
    odds_success = 0
    odds_failed: List[RaceResult] = []
    if DO_ODDS:
        with ThreadPoolExecutor(max_workers=max(1, ODDS_WORKERS)) as ex:
            futures = {ex.submit(process_race, d, v, r, True): (d, v, r) for d, v, r in tasks}
            for idx, fut in enumerate(as_completed(futures), start=1):
                rr = fut.result()
                if rr.ok:
                    odds_success += 1
                    total_odds_saved += rr.odds_saved
                elif not rr.no_race:
                    odds_failed.append(rr)

                if idx % 100 == 0 or idx == len(tasks):
                    print(
                        f"progress odds: {idx}/{len(tasks)} odds_success={odds_success} odds_failed={len(odds_failed)} odds_rows={total_odds_saved}",
                        flush=True,
                    )

    print(f"保存レース件数: {total_race_saved}", flush=True)
    print(f"保存出走表件数: {total_entries_saved}", flush=True)
    print(f"保存結果件数: {total_result_saved}", flush=True)
    print(f"保存オッズ件数: {total_odds_saved}", flush=True)
    print("=== 全場・全R 月次補修終了 ===", flush=True)
    print(f"成功: {success}", flush=True)
    print(f"非開催/データなし: {no_race}", flush=True)
    print(f"失敗: {len(failed)}", flush=True)
    if failed:
        print("失敗 race_id sample:", flush=True)
        for rr in failed[:80]:
            print(f"  {rr.race_id} {rr.error}", flush=True)
    if odds_failed:
        print(f"odds失敗: {len(odds_failed)}", flush=True)
        print("odds失敗 race_id sample:", flush=True)
        for rr in odds_failed[:80]:
            print(f"  {rr.race_id} {rr.error}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FATAL ERROR", flush=True)
        traceback.print_exc()
        raise