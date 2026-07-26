# -*- coding: utf-8 -*-
"""
repair_month_all_pg.py

Railway Postgres版。
repair_month_all_v5_fixed2.py を Supabase REST API ではなく
DATABASE_URL + PostgreSQL直接接続で動かす移行版です。

Railway Start Command:
    python repair_month_all_pg.py

主な環境変数:
    REPAIR_START_DATE=2026-07-05
    REPAIR_END_DATE=2026-07-05
    REPAIR_VENUES=01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
    REPAIR_RACE_NOS=1,2,3,4,5,6,7,8,9,10,11,12
    REPAIR_DO_RACES=1
    REPAIR_DO_RESULTS=1
    REPAIR_DO_ODDS=1
    REPAIR_SLEEP_SEC=0.1
    REPAIR_WORKERS=6
    REPAIR_ODDS_WORKERS=2

注意:
- db_pg.py が同じGitHubリポジトリに必要です。
- Railway Python Service側に DATABASE_URL が必要です。
- 最初は REPAIR_RACE_NOS=1 / REPAIR_DO_ODDS=0 で小さくテストしてください。

2026-07-09 修正:
- v2_races.deadline_time / deadline_at 保存に対応。
- オッズ取得ループ時に racelist / 出走表を二重取得しないよう修正。
"""

from __future__ import annotations

import os
import re
import time
import itertools
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from db_pg import upsert_rows as pg_upsert_rows


# ============================================================
# Settings
# ============================================================

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

SOURCE = os.getenv("REPAIR_SOURCE") or "repair_month_all_pg"

JST = timezone(timedelta(hours=9))

VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "常滑",
    "07": "蒲郡", "08": "津", "09": "三国", "10": "びわこ", "11": "住之江", "12": "尼崎",
    "13": "鳴門", "14": "丸亀", "15": "児島", "16": "宮島", "17": "徳山", "18": "下関",
    "19": "若松", "20": "芦屋", "21": "福岡", "22": "唐津", "23": "唐津", "24": "大村",
}

CLASS_MAP = {"B2": 1, "B1": 2, "A2": 3, "A1": 4}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2/1.0; +https://boatrace.jp)",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
})


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


def _clean_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(" ", strip=True)


def _official_url(kind: str, date_str: str, venue_id: str, race_no: int) -> str:
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
# Railway Postgres
# ============================================================

def _require_settings() -> None:
    print("✅ repair_month_all_pg.py VERSION 2026-07-26 result-status-v3-race-date-fixed", flush=True)
    print("✅ SETTINGS CHECK", flush=True)
    print(f"DATABASE_URL: {'OK' if bool(os.getenv('DATABASE_URL')) else 'MISSING'}", flush=True)
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が未設定です")


def upsert_rows(table: str, rows: List[Dict[str, Any]], on_conflict: str, chunk_size: int = 500) -> int:
    """
    Supabase REST版と同じ呼び出し形式を保ったまま、
    Railway Postgresへ upsert する互換関数。
    """
    if not rows:
        return 0

    total = 0
    conflict_cols = [c.strip() for c in on_conflict.split(",") if c.strip()]

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        total += pg_upsert_rows(
            table=table,
            rows=chunk,
            conflict_cols=conflict_cols,
        )

    return total


def ensure_venues() -> None:
    rows = []
    for vid in ALL_VENUES:
        rows.append({
            "venue_code": vid,
            "venue_id": vid,
            "venue_name": VENUE_NAMES.get(vid, vid),
            "is_active": True,
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


def _zen_to_han(s: str) -> str:
    trans = str.maketrans({
        "０":"0","１":"1","２":"2","３":"3","４":"4","５":"5","６":"6","７":"7","８":"8","９":"9",
        "．":".","／":"/","－":"-","　":" ","：":":",
    })
    return str(s or "").translate(trans)


def parse_deadline_time(html: str) -> Optional[str]:
    """
    BOAT RACE公式の racelist ページから締切予定時刻 HH:MM を取得する。
    取れない場合は None。
    """
    text = _zen_to_han(_html_text(html))

    patterns = [
        r"締切予定時刻\s*(\d{1,2}:\d{2})",
        r"締切予定\s*(\d{1,2}:\d{2})",
        r"締切時刻\s*(\d{1,2}:\d{2})",
        r"投票締切予定時刻\s*(\d{1,2}:\d{2})",
        r"発売締切\s*(\d{1,2}:\d{2})",
        r"締切\s*(\d{1,2}:\d{2})",
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            hhmm = m.group(1)
            h, mi = hhmm.split(":")
            return f"{int(h):02d}:{int(mi):02d}"

    # 念のため、締切という語の近くにある時刻を拾う。
    m = re.search(r"締切.{0,20}?(\d{1,2}:\d{2})", text)
    if m:
        hhmm = m.group(1)
        h, mi = hhmm.split(":")
        return f"{int(h):02d}:{int(mi):02d}"

    return None


def make_deadline_at(date_str: str, deadline_time: Optional[str]) -> Optional[str]:
    """
    date_str + HH:MM からJST付きISO文字列を作る。
    例: 2026-07-09 + 08:45 -> 2026-07-09T08:45:00+09:00
    """
    if not deadline_time:
        return None

    try:
        h, m = map(int, deadline_time.split(":"))
        d = datetime.strptime(date_str, "%Y-%m-%d")
        dt = d.replace(hour=h, minute=m, second=0, microsecond=0, tzinfo=JST)
        return dt.isoformat()
    except Exception:
        return None


def _num_token(v: str) -> Optional[float]:
    try:
        return float(str(v).replace(',', ''))
    except Exception:
        return None


def parse_entries(html: str, race_id: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    raw_lines = []
    for line in soup.get_text("\n", strip=True).splitlines():
        line = _clean_text(_zen_to_han(line))
        if line:
            raw_lines.append(line)

    body_start = 0
    for i, line in enumerate(raw_lines):
        if "写真 登録番号/級別" in line or "登録番号/級別" in line:
            body_start = i
            break

    body_end = len(raw_lines)
    for i in range(body_start + 1, len(raw_lines)):
        if raw_lines[i] in ("今節成績", "モーター・ボート変更時は赤で表示されます。", "PAGE TOP"):
            body_end = i
            break

    lines = raw_lines[body_start:body_end]

    lane_positions: List[Tuple[int, int]] = []
    for i, line in enumerate(lines):
        if not re.fullmatch(r"[1-6]", line):
            continue
        look = " ".join(lines[i:i+8])
        if re.search(r"\b\d{4}\s*/\s*(A1|A2|B1|B2)\b", look):
            lane_positions.append((int(line), i))

    entries: Dict[int, Dict[str, Any]] = {}

    for idx, (lane, pos) in enumerate(lane_positions):
        next_pos = lane_positions[idx + 1][1] if idx + 1 < len(lane_positions) else len(lines)
        seg_lines = lines[pos:next_pos]
        seg = " ".join(seg_lines)

        m_no = re.search(r"\b(\d{4})\s*/\s*(A1|A2|B1|B2)\b", seg)
        if not m_no:
            continue

        racer_number = int(m_no.group(1))
        racer_class_text = m_no.group(2)
        racer_class = CLASS_MAP.get(racer_class_text)

        racer_name = None
        reg_line_index = None
        for j, line in enumerate(seg_lines):
            if re.search(r"\b\d{4}\s*/\s*(A1|A2|B1|B2)\b", line):
                reg_line_index = j
                break

        if reg_line_index is not None:
            for cand in seg_lines[reg_line_index + 1: reg_line_index + 5]:
                if re.search(r"[一-龥ぁ-んァ-ヶー]", cand) and "/" not in cand and not re.search(r"\d", cand):
                    racer_name = cand[:40]
                    break

        branch = None
        origin = None
        if reg_line_index is not None:
            for cand in seg_lines[reg_line_index + 1: reg_line_index + 8]:
                if "/" in cand and re.search(r"[一-龥ぁ-んァ-ヶー]", cand):
                    parts = [p.strip() for p in cand.split("/", 1)]
                    if len(parts) == 2:
                        branch, origin = parts[0][:20], parts[1][:20]
                    break

        f_count = None
        l_count = None
        m_f = re.search(r"\bF\s*(\d+)\b", seg)
        m_l = re.search(r"\bL\s*(\d+)\b", seg)
        if m_f:
            f_count = int(m_f.group(1))
        if m_l:
            l_count = int(m_l.group(1))

        nums = re.findall(r"\d+\.\d+|\d+", seg)
        avg_idx = None
        for k, tok in enumerate(nums):
            if re.fullmatch(r"0\.\d{2}", tok):
                avg_idx = k
                break

        seq = nums[avg_idx:] if avg_idx is not None else []

        def fseq(n: int) -> Optional[float]:
            return _num_token(seq[n]) if len(seq) > n else None

        def iseq(n: int) -> Optional[int]:
            if len(seq) <= n:
                return None
            return _to_int(seq[n])

        row: Dict[str, Any] = {
            "race_id": race_id,
            "lane": lane,
            "course": lane,
            "racer_number": racer_number,
            "racer_name": racer_name,
            "racer_class": racer_class,
            "racer_class_text": racer_class_text,
            "branch": branch,
            "origin": origin,
            "f_count": f_count,
            "l_count": l_count,
            "avg_st": fseq(0),
            "national_win_rate": fseq(1),
            "national_place2_rate": fseq(2),
            "national_place3_rate": fseq(3),
            "local_win_rate": fseq(4),
            "local_place2_rate": fseq(5),
            "local_place3_rate": fseq(6),
            "motor_no": iseq(7),
            "motor_place2_rate": fseq(8),
            "motor_place3_rate": fseq(9),
            "boat_no": iseq(10),
            "boat_place2_rate": fseq(11),
            "boat_place3_rate": fseq(12),
            "recent_form": [],
            "updated_at": _now_iso(),
        }
        entries[lane] = row

    if len(entries) < 6:
        for tr in soup.find_all("tr"):
            cells = [_clean_text(_zen_to_han(td.get_text(" ", strip=True))) for td in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            row_text = " ".join(cells)
            lane = None
            for c in cells[:3]:
                if re.fullmatch(r"[1-6]", c):
                    lane = int(c)
                    break
            if lane is None or lane in entries:
                continue
            m_no = re.search(r"\b(\d{4})\s*/?\s*(A1|A2|B1|B2)?\b", row_text)
            if not m_no:
                continue
            cls = m_no.group(2)
            entries[lane] = {
                "race_id": race_id,
                "lane": lane,
                "course": lane,
                "racer_number": int(m_no.group(1)),
                "racer_class": CLASS_MAP.get(cls) if cls else None,
                "racer_class_text": cls,
                "recent_form": [],
                "updated_at": _now_iso(),
            }

    valid_entries = [
        entries[k]
        for k in sorted(entries)
        if entries[k].get("racer_number")
    ]
    return valid_entries


def parse_result(html: str) -> Dict[str, Any]:
    """公式結果HTMLを解析し、中止・3連単不成立・解析失敗を区別する。"""
    soup = BeautifulSoup(html, "html.parser")
    text = _html_text(html)

    keys = ["first_lane", "second_lane", "third_lane", "fourth_lane", "fifth_lane", "sixth_lane"]

    def empty_result(result_status: str, race_status: str) -> Dict[str, Any]:
        # UPSERT時に過去の誤解析値を確実にNULLへ戻すため、列を省略しない。
        row: Dict[str, Any] = {
            "result_status": result_status,
            "race_status": race_status,
            "trifecta_ticket": None,
            "trifecta_payout_yen": 0,
            "source": SOURCE,
            "fetched_at": _now_iso(),
        }
        for key in keys:
            row[key] = None
        return row

    no_result_words = [
        "データがありません",
        "レース結果がありません",
        "該当するデータはありません",
        "レース情報がありません",
    ]
    if any(word in text for word in no_result_words):
        return empty_result("no_result_page", "no_result_page")

    cancelled_words = [
        "レース中止",
        "開催中止",
        "中止となりました",
        "中止になりました",
        "以降中止",
        "打ち切り",
        "打切り",
        "取り止め",
        "取止め",
    ]
    if any(word in text for word in cancelled_words):
        return empty_result("cancelled", "cancelled")

    result: Dict[str, Any] = {
        "result_status": "official",
        "race_status": "official",
        "source": SOURCE,
        "fetched_at": _now_iso(),
    }

    # 先に3連単の正常払戻を解析する。
    # 正常レースでもページ下部に「返還」欄があるため、返還文字だけを先に見ると誤分類する。
    m_tri = re.search(
        r"3\s*連\s*単\s*([1-6])\s*[-－ー]?\s*([1-6])\s*[-－ー]?\s*([1-6])"
        r"\s*[¥￥]?\s*([\d,]+)\s*円?",
        text,
    )
    if m_tri:
        lanes = [int(m_tri.group(i)) for i in (1, 2, 3)]
        payout = int(m_tri.group(4).replace(",", ""))
        if len(set(lanes)) == 3 and payout > 0:
            result["first_lane"], result["second_lane"], result["third_lane"] = lanes
            result["trifecta_ticket"] = f"{lanes[0]}-{lanes[1]}-{lanes[2]}"
            result["trifecta_payout_yen"] = payout

    # 正常な3連単払戻を取得できなかった場合だけ、不成立・全返還を判定する。
    if int(result.get("trifecta_payout_yen") or 0) <= 0:
        trifecta_invalid_patterns = [
            r"3\s*連\s*単.{0,30}不成立",
            r"3\s*連\s*単.{0,30}(?:全額)?返還",
            r"不成立.{0,30}3\s*連\s*単",
        ]
        if any(re.search(pattern, text) for pattern in trifecta_invalid_patterns):
            return empty_result("trifecta_invalid", "official")

    # 着順表を解析する。3連単から上位3艇を取得済みでも4～6着を補完する。
    finish: Dict[int, int] = {}
    for tr in soup.find_all("tr"):
        cells = [_clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        rank = _to_int(cells[0])
        lane = _to_int(cells[1])
        if rank and lane and 1 <= rank <= 6 and 1 <= lane <= 6 and lane not in finish.values():
            finish[rank] = lane

    for rank, key in enumerate(keys, start=1):
        if rank in finish:
            # 3連単の上位3艇を優先する。
            result.setdefault(key, finish[rank])

    top3 = [result.get("first_lane"), result.get("second_lane"), result.get("third_lane")]
    valid_top3 = all(isinstance(x, int) and 1 <= x <= 6 for x in top3) and len(set(top3)) == 3
    valid_payout = int(result.get("trifecta_payout_yen") or 0) > 0

    if valid_top3 and valid_payout:
        result["result_status"] = "official"
        result["race_status"] = "official"
        result.setdefault("trifecta_ticket", f"{top3[0]}-{top3[1]}-{top3[2]}")
        return result

    return empty_result("parse_error", "parse_error")

def parse_odds3t(html: str, race_id: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")

    def make_row(ticket: str, odd: float) -> Dict[str, Any]:
        return {
            "race_id": race_id,
            "ticket": ticket,
            "odds": odd,
            "is_final": True,
            "fetched_at": _now_iso(),
        }

    valid_tickets = {
        f"{a}-{b}-{c}"
        for a, b, c in itertools.permutations([1, 2, 3, 4, 5, 6], 3)
    }

    rows: Dict[str, Dict[str, Any]] = {}

    text_lines = soup.get_text("\n", strip=True)
    if "3連単オッズ" in text_lines:
        segment = text_lines.split("3連単オッズ", 1)[1]
    else:
        segment = text_lines

    for marker in ["締切時オッズは", "レース開始後", "PAGE TOP"]:
        if marker in segment:
            segment = segment.split(marker, 1)[0]

    tokens = re.findall(r"\d+(?:\.\d+)?", segment)

    def token_is_lane(tok: str, val: int) -> bool:
        return re.fullmatch(r"[1-6]", tok or "") is not None and int(tok) == val

    firsts = [1, 2, 3, 4, 5, 6]
    expected_first_row_pairs = []
    for f in firsts:
        sec = [x for x in firsts if x != f][0]
        th = [x for x in firsts if x not in (f, sec)][0]
        expected_first_row_pairs.append((sec, th))

    start_pos: Optional[int] = None
    needed = 270
    for i in range(0, max(0, len(tokens) - needed + 1)):
        ok = True
        for col, (sec, th) in enumerate(expected_first_row_pairs):
            base = i + col * 3
            if not (token_is_lane(tokens[base], sec) and token_is_lane(tokens[base + 1], th)):
                ok = False
                break
        if ok:
            start_pos = i
            break

    if start_pos is not None:
        idx = start_pos
        try:
            for sec_group in range(5):
                second_by_first = {f: [x for x in firsts if x != f][sec_group] for f in firsts}
                for third_row in range(4):
                    for f in firsts:
                        sec = second_by_first[f]
                        if third_row == 0:
                            sec_tok = tokens[idx]
                            idx += 1
                            th_tok = tokens[idx]
                            idx += 1
                            odd_tok = tokens[idx]
                            idx += 1
                            if token_is_lane(sec_tok, sec):
                                sec = int(sec_tok)
                        else:
                            th_tok = tokens[idx]
                            idx += 1
                            odd_tok = tokens[idx]
                            idx += 1

                        if not re.fullmatch(r"[1-6]", th_tok or ""):
                            continue
                        th = int(th_tok)
                        if len({f, sec, th}) < 3:
                            continue
                        try:
                            odd = float(odd_tok)
                        except Exception:
                            continue
                        if odd <= 0:
                            continue
                        ticket = f"{f}-{sec}-{th}"
                        if ticket in valid_tickets:
                            rows[ticket] = make_row(ticket, odd)
        except Exception:
            rows = {}

    if len(rows) >= 100:
        return sorted(rows.values(), key=lambda r: tuple(map(int, r["ticket"].split("-"))))

    rows = {}
    for table in soup.find_all("table"):
        raw_rows: List[List[str]] = []
        for tr in table.find_all("tr"):
            cells = [_clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if cells:
                raw_rows.append(cells)

        flat_nums = re.findall(r"\d+(?:\.\d+)?", " ".join(" ".join(r) for r in raw_rows))
        if len(flat_nums) < 40:
            continue

        possible_firsts = [int(x) for x in flat_nums[:8] if re.fullmatch(r"[1-6]", x)]
        for f in possible_firsts[:1]:
            if f not in firsts:
                continue
            idx2 = 0
            while idx2 < len(flat_nums) and not (
                idx2 + 2 < len(flat_nums)
                and flat_nums[idx2] in [str(x) for x in firsts if x != f]
            ):
                idx2 += 1
            try:
                for sec in [x for x in firsts if x != f]:
                    for third_row in range(4):
                        if third_row == 0:
                            sec_tok = flat_nums[idx2]
                            idx2 += 1
                            th_tok = flat_nums[idx2]
                            idx2 += 1
                            odd_tok = flat_nums[idx2]
                            idx2 += 1
                            if token_is_lane(sec_tok, sec):
                                sec = int(sec_tok)
                        else:
                            th_tok = flat_nums[idx2]
                            idx2 += 1
                            odd_tok = flat_nums[idx2]
                            idx2 += 1

                        if not re.fullmatch(r"[1-6]", th_tok or ""):
                            continue
                        th = int(th_tok)
                        if len({f, sec, th}) < 3:
                            continue
                        odd = float(odd_tok)
                        if odd <= 0:
                            continue
                        ticket = f"{f}-{sec}-{th}"
                        if ticket in valid_tickets:
                            rows[ticket] = make_row(ticket, odd)
            except Exception:
                pass

    if len(rows) >= 100:
        return sorted(rows.values(), key=lambda r: tuple(map(int, r["ticket"].split("-"))))

    text = _html_text(html)
    for m in re.finditer(r"([1-6])\s*[-－]\s*([1-6])\s*[-－]\s*([1-6])\s+([0-9]+(?:\.[0-9]+)?)", text):
        a, b, c = m.group(1), m.group(2), m.group(3)
        if len({a, b, c}) < 3:
            continue
        ticket = f"{a}-{b}-{c}"
        rows[ticket] = make_row(ticket, float(m.group(4)))

    if len(rows) < 100:
        compact = re.sub(r"\s+", " ", text)
        for m in re.finditer(r"\b([1-6])\s+([1-6])\s+([1-6])\s+([0-9]+(?:\.[0-9]+)?)\b", compact):
            a, b, c = m.group(1), m.group(2), m.group(3)
            if len({a, b, c}) < 3:
                continue
            odd = float(m.group(4))
            if odd <= 0:
                continue
            ticket = f"{a}-{b}-{c}"
            if ticket in valid_tickets:
                rows[ticket] = make_row(ticket, odd)

    return sorted(rows.values(), key=lambda r: tuple(map(int, r["ticket"].split("-"))))


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

        # オッズ取得ループ時は racelist / 出走表を再取得しない。
        # DO_RACES=True DO_ODDS=True の同時実行でも、racelistは前段のrace/resultループで1回だけ取得する。
        if DO_RACES and not do_odds:
            url = _official_url("racelist", date_str, venue_id, race_no)
            html = _fetch(url)
            if _looks_no_race(html):
                return RaceResult(race_id=rid, ok=False, no_race=True, error="no_race")

            deadline_time = parse_deadline_time(html or "")
            deadline_at = make_deadline_at(date_str, deadline_time)

            race_row = {
                "race_id": rid,
                "race_date": date_str,
                "venue_code": venue_id,
                "venue_id": venue_id,
                "venue_name": VENUE_NAMES.get(venue_id, venue_id),
                "race_no": int(race_no),
                "race_name": parse_race_name(html or ""),
                "deadline_time": deadline_time,
                "deadline_at": deadline_at,
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
                # v2_results.race_date を必ず保存する。
                # DO_RACES=0 / DO_RESULTS=1 の結果のみ補修では v2_races を更新しないため、
                # ここで入れないと新規月の v2_results.race_date が NULL になる。
                res_row["race_date"] = date_str
                result_saved = upsert_rows("v2_results", [res_row], "race_id", chunk_size=1)

        if do_odds and DO_ODDS:
            url = _official_url("odds3t", date_str, venue_id, race_no)
            html = _fetch(url)
            if not _looks_no_race(html):
                odds = parse_odds3t(html or "", rid)
                if odds:
                    odds_saved = upsert_rows("v2_odds_trifecta", odds, "race_id,ticket", chunk_size=300)

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