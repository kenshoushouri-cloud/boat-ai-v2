# -*- coding: utf-8 -*-
"""
repair_month_all_pg.py

Railway PostgreSQL版・完全差し替え用。

VERSION:
2026-08-19 deadline-table-v10

主な修正:
- BOAT RACE公式の場コードと場名の対応を維持。
- 締切時刻は racelist 上部の 1R～12R 時刻表を「列位置」で対応付けて取得。
- 1Rの締切を2R～12Rへ誤適用する不具合を修正。
- 締切表解析に失敗した場合は別Rの時刻へフォールバックせず None。
- 早朝取得オッズを誤って最終オッズ扱いしないよう ODDS_IS_FINAL を維持。
- 三連単ticketは1～6号艇・3艇重複なしのみ保存。
- 既存のレース、出走表、結果、オッズ保存処理を維持。
"""

from __future__ import annotations

import itertools
import os
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    for v in (
        os.getenv("REPAIR_VENUES")
        or os.getenv("TARGET_VENUES")
        or ",".join(ALL_VENUES)
    ).split(",")
    if v.strip()
]

REPAIR_RACE_NOS = [
    int(x.strip())
    for x in (
        os.getenv("REPAIR_RACE_NOS")
        or os.getenv("RACE_NOS")
        or ",".join(DEFAULT_RACE_NOS)
    ).split(",")
    if x.strip()
]

REPAIR_RACE_IDS = [
    x.strip()
    for x in os.getenv("REPAIR_RACE_IDS", "").split(",")
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
ODDS_IS_FINAL = (os.getenv("ODDS_IS_FINAL") or "0") == "1"

JST = timezone(timedelta(hours=9))

VENUE_NAMES = {
    "01": "桐生",
    "02": "戸田",
    "03": "江戸川",
    "04": "平和島",
    "05": "多摩川",
    "06": "浜名湖",
    "07": "蒲郡",
    "08": "常滑",
    "09": "津",
    "10": "三国",
    "11": "びわこ",
    "12": "住之江",
    "13": "尼崎",
    "14": "鳴門",
    "15": "丸亀",
    "16": "児島",
    "17": "宮島",
    "18": "徳山",
    "19": "下関",
    "20": "若松",
    "21": "芦屋",
    "22": "福岡",
    "23": "唐津",
    "24": "大村",
}

CLASS_MAP = {"B2": 1, "B1": 2, "A2": 3, "A1": 4}

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2/1.0; +https://boatrace.jp)",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }
)


# ============================================================
# Utility
# ============================================================

def _now_iso() -> str:
    return datetime.now(JST).isoformat()


def _race_id(date_str: str, venue_id: str, race_no: int) -> str:
    return f"{date_str.replace('-', '')}_{venue_id.zfill(2)}_{int(race_no):02d}"


def _parse_race_id(race_id: str) -> Optional[Tuple[str, str, int]]:
    match = re.fullmatch(
        r"(\d{4})(\d{2})(\d{2})_(\d{2})_(\d{2})",
        str(race_id or "").strip(),
    )
    if not match:
        return None

    date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    venue_id = match.group(4)
    race_no = int(match.group(5))

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    if venue_id not in ALL_VENUES or not 1 <= race_no <= 12:
        return None

    return date_str, venue_id, race_no


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
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def _official_url(kind: str, date_str: str, venue_id: str, race_no: int) -> str:
    return (
        f"https://www.boatrace.jp/owpc/pc/race/{kind}"
        f"?rno={int(race_no)}&jcd={venue_id.zfill(2)}&hd={_yyyymmdd(date_str)}"
    )


def _fetch(url: str) -> Optional[str]:
    last_err: Optional[str] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            res = SESSION.get(url, timeout=HTTP_TIMEOUT)

            if res.status_code == 404:
                return None

            if not res.ok:
                last_err = f"HTTP {res.status_code}: {res.text[:120]}"
                time.sleep(0.5 + attempt * 0.5)
                continue

            encoding = (res.encoding or "").strip()

            if not encoding:
                head = res.content[:5000].decode("ascii", errors="ignore")
                match = re.search(
                    r"charset\s*=\s*[\"']?\s*([A-Za-z0-9._-]+)",
                    head,
                    flags=re.IGNORECASE,
                )
                if match:
                    encoding = match.group(1)

            if not encoding:
                encoding = "utf-8"

            try:
                return res.content.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                apparent = (res.apparent_encoding or "").strip()
                if apparent and apparent.lower() != encoding.lower():
                    try:
                        return res.content.decode(apparent)
                    except (LookupError, UnicodeDecodeError):
                        pass

                return res.content.decode("utf-8", errors="replace")

        except Exception as exc:
            last_err = str(exc)
            time.sleep(0.5 + attempt * 0.5)

    print(f"fetch failed: {url} err={last_err}", flush=True)
    return None


def _looks_no_race(html: Optional[str]) -> bool:
    if not html:
        return True
    text = _html_text(html)
    ng_words = [
        "データがありません",
        "レース情報がありません",
        "該当するデータはありません",
        "発売しておりません",
    ]
    return any(word in text for word in ng_words)


# ============================================================
# Railway PostgreSQL
# ============================================================

def _require_settings() -> None:
    print(
        "✅ repair_month_all_pg.py VERSION 2026-08-19 deadline-table-v10",
        flush=True,
    )
    print("✅ SETTINGS CHECK", flush=True)
    print(
        f"DATABASE_URL: {'OK' if bool(os.getenv('DATABASE_URL')) else 'MISSING'}",
        flush=True,
    )
    print(f"ODDS_IS_FINAL={ODDS_IS_FINAL}", flush=True)

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が未設定です")


def upsert_rows(
    table: str,
    rows: List[Dict[str, Any]],
    on_conflict: str,
    chunk_size: int = 500,
) -> int:
    if not rows:
        return 0

    total = 0
    conflict_cols = [c.strip() for c in on_conflict.split(",") if c.strip()]

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        total += pg_upsert_rows(
            table=table,
            rows=chunk,
            conflict_cols=conflict_cols,
        )

    return total


def ensure_venues() -> None:
    rows = [
        {
            "venue_code": venue_id,
            "venue_id": venue_id,
            "venue_name": VENUE_NAMES[venue_id],
            "is_active": True,
            "updated_at": _now_iso(),
        }
        for venue_id in ALL_VENUES
    ]

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
            text = _clean_text(node.get_text(" ", strip=True))
            if text and "BOAT" not in text.upper():
                return text[:100]

    text = _html_text(html)
    match = re.search(r"(第\d+R|\d+R)\s*([^\s]+)", text)
    return match.group(0)[:100] if match else None


def _zen_to_han(s: str) -> str:
    trans = str.maketrans(
        {
            "０": "0",
            "１": "1",
            "２": "2",
            "３": "3",
            "４": "4",
            "５": "5",
            "６": "6",
            "７": "7",
            "８": "8",
            "９": "9",
            "．": ".",
            "／": "/",
            "－": "-",
            "　": " ",
            "：": ":",
        }
    )
    return str(s or "").translate(trans)


def _normalize_hhmm(value: str) -> Optional[str]:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", value or "")
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2))

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    return f"{hour:02d}:{minute:02d}"


def parse_deadline_table(html: str) -> Dict[int, str]:
    """
    racelist上部の
      1R | 2R | ... | 12R
      締切予定時刻 | HH:MM | ... | HH:MM
    を同じ列位置で対応付ける。

    診断済み:
    三国 2026-08-19:
      1R=08:32, 2R=08:58, ... 12R=14:15
    """
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        for i, tr in enumerate(rows):
            cells = tr.find_all(["th", "td"])
            texts = [
                _clean_text(_zen_to_han(c.get_text(" ", strip=True)))
                for c in cells
            ]

            race_cols: Dict[int, int] = {}

            for col, text in enumerate(texts):
                match = re.fullmatch(
                    r"(?:第\s*)?([1-9]|1[0-2])\s*R",
                    text,
                    flags=re.IGNORECASE,
                )
                if match:
                    race_cols[col] = int(match.group(1))

            if len(race_cols) < 3:
                continue

            for deadline_tr in rows[i + 1 : i + 5]:
                deadline_cells = deadline_tr.find_all(["th", "td"])
                deadline_texts = [
                    _clean_text(_zen_to_han(c.get_text(" ", strip=True)))
                    for c in deadline_cells
                ]

                if "締切" not in " ".join(deadline_texts):
                    continue

                result: Dict[int, str] = {}

                for col, mapped_race_no in race_cols.items():
                    if col >= len(deadline_texts):
                        continue

                    match = re.search(
                        r"(?<!\d)(\d{1,2}:\d{2})(?!\d)",
                        deadline_texts[col],
                    )
                    if not match:
                        continue

                    normalized = _normalize_hhmm(match.group(1))
                    if normalized:
                        result[mapped_race_no] = normalized

                if len(result) >= 3:
                    return result

    return {}


def parse_deadline_time(html: str, race_no: int) -> Optional[str]:
    """
    v10:
    race_no近傍の文字列検索は廃止。
    公式racelistの時刻表を列対応で読み、対象Rの締切だけ返す。
    解析失敗時は誤った別R時刻を保存せずNone。
    """
    deadline_map = parse_deadline_table(html)
    return deadline_map.get(int(race_no))


def make_deadline_at(date_str: str, deadline_time: Optional[str]) -> Optional[str]:
    if not deadline_time:
        return None

    try:
        hour, minute = map(int, deadline_time.split(":"))
        base = datetime.strptime(date_str, "%Y-%m-%d")
        dt = base.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
            tzinfo=JST,
        )
        return dt.isoformat()
    except Exception:
        return None


def _num_token(v: str) -> Optional[float]:
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def parse_entries(html: str, race_id: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")

    raw_lines: List[str] = []
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
        if raw_lines[i] in (
            "今節成績",
            "モーター・ボート変更時は赤で表示されます。",
            "PAGE TOP",
        ):
            body_end = i
            break

    lines = raw_lines[body_start:body_end]

    lane_positions: List[Tuple[int, int]] = []
    for i, line in enumerate(lines):
        if not re.fullmatch(r"[1-6]", line):
            continue
        look = " ".join(lines[i : i + 8])
        if re.search(r"\b\d{4}\s*/\s*(A1|A2|B1|B2)\b", look):
            lane_positions.append((int(line), i))

    entries: Dict[int, Dict[str, Any]] = {}

    for idx, (lane, pos) in enumerate(lane_positions):
        next_pos = lane_positions[idx + 1][1] if idx + 1 < len(lane_positions) else len(lines)
        seg_lines = lines[pos:next_pos]
        seg = " ".join(seg_lines)

        match_no = re.search(r"\b(\d{4})\s*/\s*(A1|A2|B1|B2)\b", seg)
        if not match_no:
            continue

        racer_number = int(match_no.group(1))
        racer_class_text = match_no.group(2)
        racer_class = CLASS_MAP.get(racer_class_text)

        racer_name: Optional[str] = None
        reg_line_index: Optional[int] = None

        for j, line in enumerate(seg_lines):
            if re.search(r"\b\d{4}\s*/\s*(A1|A2|B1|B2)\b", line):
                reg_line_index = j
                break

        if reg_line_index is not None:
            for candidate in seg_lines[reg_line_index + 1 : reg_line_index + 5]:
                if (
                    re.search(r"[一-龥ぁ-んァ-ヶー]", candidate)
                    and "/" not in candidate
                    and not re.search(r"\d", candidate)
                ):
                    racer_name = candidate[:40]
                    break

        branch: Optional[str] = None
        origin: Optional[str] = None

        if reg_line_index is not None:
            for candidate in seg_lines[reg_line_index + 1 : reg_line_index + 8]:
                if "/" in candidate and re.search(r"[一-龥ぁ-んァ-ヶー]", candidate):
                    parts = [p.strip() for p in candidate.split("/", 1)]
                    if len(parts) == 2:
                        branch = parts[0][:20]
                        origin = parts[1][:20]
                    break

        f_count = None
        l_count = None

        match_f = re.search(r"\bF\s*(\d+)\b", seg)
        match_l = re.search(r"\bL\s*(\d+)\b", seg)

        if match_f:
            f_count = int(match_f.group(1))
        if match_l:
            l_count = int(match_l.group(1))

        nums = re.findall(r"\d+\.\d+|\d+", seg)

        avg_idx = None
        for k, token in enumerate(nums):
            if re.fullmatch(r"0\.\d{2}", token):
                avg_idx = k
                break

        seq = nums[avg_idx:] if avg_idx is not None else []

        def fseq(n: int) -> Optional[float]:
            return _num_token(seq[n]) if len(seq) > n else None

        def iseq(n: int) -> Optional[int]:
            return _to_int(seq[n]) if len(seq) > n else None

        entries[lane] = {
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

    if len(entries) < 6:
        for tr in soup.find_all("tr"):
            cells = [
                _clean_text(_zen_to_han(td.get_text(" ", strip=True)))
                for td in tr.find_all(["td", "th"])
            ]

            if len(cells) < 2:
                continue

            row_text = " ".join(cells)
            lane = None

            for cell in cells[:3]:
                if re.fullmatch(r"[1-6]", cell):
                    lane = int(cell)
                    break

            if lane is None or lane in entries:
                continue

            match_no = re.search(
                r"\b(\d{4})\s*/?\s*(A1|A2|B1|B2)?\b",
                row_text,
            )

            if not match_no:
                continue

            cls = match_no.group(2)

            entries[lane] = {
                "race_id": race_id,
                "lane": lane,
                "course": lane,
                "racer_number": int(match_no.group(1)),
                "racer_class": CLASS_MAP.get(cls) if cls else None,
                "racer_class_text": cls,
                "recent_form": [],
                "updated_at": _now_iso(),
            }

    return [
        entries[lane]
        for lane in sorted(entries)
        if entries[lane].get("racer_number")
    ]


def parse_result(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    text = _html_text(html)

    finish_keys = [
        "first_lane",
        "second_lane",
        "third_lane",
        "fourth_lane",
        "fifth_lane",
        "sixth_lane",
    ]

    def empty_result(result_status: str, race_status: str) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "result_status": result_status,
            "race_status": race_status,
            "trifecta_ticket": None,
            "trifecta_payout_yen": 0,
            "source": SOURCE,
            "fetched_at": _now_iso(),
        }
        for key in finish_keys:
            row[key] = None
        return row

    if any(
        word in text
        for word in [
            "データがありません",
            "レース結果がありません",
            "該当するデータはありません",
            "レース情報がありません",
        ]
    ):
        return empty_result("no_result_page", "no_result_page")

    if any(
        word in text
        for word in [
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
    ):
        return empty_result("cancelled", "cancelled")

    result: Dict[str, Any] = {
        "result_status": "official",
        "race_status": "official",
        "source": SOURCE,
        "fetched_at": _now_iso(),
    }

    match_tri = re.search(
        r"3\s*連\s*単\s*([1-6])\s*[-－ー]?\s*([1-6])\s*[-－ー]?\s*([1-6])"
        r"\s*[¥￥]?\s*([\d,]+)\s*円?",
        text,
    )

    if match_tri:
        lanes = [int(match_tri.group(i)) for i in (1, 2, 3)]
        payout = int(match_tri.group(4).replace(",", ""))

        if len(set(lanes)) == 3 and payout > 0:
            result["first_lane"] = lanes[0]
            result["second_lane"] = lanes[1]
            result["third_lane"] = lanes[2]
            result["trifecta_ticket"] = f"{lanes[0]}-{lanes[1]}-{lanes[2]}"
            result["trifecta_payout_yen"] = payout

    if int(result.get("trifecta_payout_yen") or 0) <= 0:
        invalid_patterns = [
            r"3\s*連\s*単.{0,30}不成立",
            r"3\s*連\s*単.{0,30}(?:全額)?返還",
            r"不成立.{0,30}3\s*連\s*単",
        ]

        if any(re.search(pattern, text) for pattern in invalid_patterns):
            return empty_result("trifecta_invalid", "official")

    finish: Dict[int, int] = {}

    for tr in soup.find_all("tr"):
        cells = [
            _clean_text(td.get_text(" ", strip=True))
            for td in tr.find_all(["td", "th"])
        ]

        if len(cells) < 2:
            continue

        rank = _to_int(cells[0])
        lane = _to_int(cells[1])

        if (
            rank
            and lane
            and 1 <= rank <= 6
            and 1 <= lane <= 6
            and lane not in finish.values()
        ):
            finish[rank] = lane

    for rank, key in enumerate(finish_keys, start=1):
        if rank in finish:
            result.setdefault(key, finish[rank])

    top3 = [
        result.get("first_lane"),
        result.get("second_lane"),
        result.get("third_lane"),
    ]

    valid_top3 = (
        all(isinstance(x, int) and 1 <= x <= 6 for x in top3)
        and len(set(top3)) == 3
    )

    valid_payout = int(result.get("trifecta_payout_yen") or 0) > 0

    if valid_top3 and valid_payout:
        result["result_status"] = "official"
        result["race_status"] = "official"
        result.setdefault(
            "trifecta_ticket",
            f"{top3[0]}-{top3[1]}-{top3[2]}",
        )
        return result

    return empty_result("parse_error", "parse_error")


def parse_odds3t(html: str, race_id: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")

    valid_tickets = {
        f"{a}-{b}-{c}"
        for a, b, c in itertools.permutations([1, 2, 3, 4, 5, 6], 3)
    }

    def make_row(ticket: str, odd: float) -> Dict[str, Any]:
        return {
            "race_id": race_id,
            "ticket": ticket,
            "odds": odd,
            "is_final": ODDS_IS_FINAL,
            "fetched_at": _now_iso(),
        }

    rows: Dict[str, Dict[str, Any]] = {}

    text_lines = soup.get_text("\n", strip=True)
    segment = (
        text_lines.split("3連単オッズ", 1)[1]
        if "3連単オッズ" in text_lines
        else text_lines
    )

    for marker in ["締切時オッズは", "レース開始後", "PAGE TOP"]:
        if marker in segment:
            segment = segment.split(marker, 1)[0]

    tokens = re.findall(r"\d+(?:\.\d+)?", segment)

    def token_is_lane(token: str, value: int) -> bool:
        return (
            re.fullmatch(r"[1-6]", token or "") is not None
            and int(token) == value
        )

    firsts = [1, 2, 3, 4, 5, 6]
    expected_pairs: List[Tuple[int, int]] = []

    for first in firsts:
        second = [x for x in firsts if x != first][0]
        third = [x for x in firsts if x not in (first, second)][0]
        expected_pairs.append((second, third))

    start_pos: Optional[int] = None
    needed = 270

    for i in range(0, max(0, len(tokens) - needed + 1)):
        ok = True

        for col, (second, third) in enumerate(expected_pairs):
            base = i + col * 3

            if not (
                token_is_lane(tokens[base], second)
                and token_is_lane(tokens[base + 1], third)
            ):
                ok = False
                break

        if ok:
            start_pos = i
            break

    if start_pos is not None:
        idx = start_pos

        try:
            for second_group in range(5):
                second_by_first = {
                    first: [x for x in firsts if x != first][second_group]
                    for first in firsts
                }

                for third_row in range(4):
                    for first in firsts:
                        second = second_by_first[first]

                        if third_row == 0:
                            second_token = tokens[idx]
                            idx += 1
                            third_token = tokens[idx]
                            idx += 1
                            odd_token = tokens[idx]
                            idx += 1

                            if token_is_lane(second_token, second):
                                second = int(second_token)

                        else:
                            third_token = tokens[idx]
                            idx += 1
                            odd_token = tokens[idx]
                            idx += 1

                        if not re.fullmatch(r"[1-6]", third_token or ""):
                            continue

                        third = int(third_token)

                        if len({first, second, third}) < 3:
                            continue

                        try:
                            odd = float(odd_token)
                        except Exception:
                            continue

                        if odd <= 0:
                            continue

                        ticket = f"{first}-{second}-{third}"

                        if ticket in valid_tickets:
                            rows[ticket] = make_row(ticket, odd)

        except Exception:
            rows = {}

    if len(rows) == 120:
        return sorted(
            rows.values(),
            key=lambda row: tuple(map(int, row["ticket"].split("-"))),
        )

    text = _html_text(html)

    for match in re.finditer(
        r"([1-6])\s*[-－]\s*([1-6])\s*[-－]\s*([1-6])"
        r"\s+([0-9]+(?:\.[0-9]+)?)",
        text,
    ):
        a, b, c = match.group(1), match.group(2), match.group(3)

        if len({a, b, c}) < 3:
            continue

        ticket = f"{a}-{b}-{c}"
        odd = float(match.group(4))

        if ticket in valid_tickets and odd > 0:
            rows[ticket] = make_row(ticket, odd)

    if len(rows) < 120:
        compact = re.sub(r"\s+", " ", text)

        for match in re.finditer(
            r"\b([1-6])\s+([1-6])\s+([1-6])"
            r"\s+([0-9]+(?:\.[0-9]+)?)\b",
            compact,
        ):
            a, b, c = match.group(1), match.group(2), match.group(3)

            if len({a, b, c}) < 3:
                continue

            ticket = f"{a}-{b}-{c}"
            odd = float(match.group(4))

            if ticket in valid_tickets and odd > 0:
                rows[ticket] = make_row(ticket, odd)

    return sorted(
        rows.values(),
        key=lambda row: tuple(map(int, row["ticket"].split("-"))),
    )


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


def process_race(
    date_str: str,
    venue_id: str,
    race_no: int,
    do_odds: bool = False,
) -> RaceResult:
    race_id = _race_id(date_str, venue_id, race_no)

    try:
        race_saved = 0
        entries_saved = 0
        result_saved = 0
        odds_saved = 0

        if DO_RACES and not do_odds:
            url = _official_url("racelist", date_str, venue_id, race_no)
            html = _fetch(url)

            if _looks_no_race(html):
                return RaceResult(
                    race_id=race_id,
                    ok=False,
                    no_race=True,
                    error="no_race",
                )

            deadline_time = parse_deadline_time(html or "", race_no)
            deadline_at = make_deadline_at(date_str, deadline_time)

            print(
                f"DEADLINE race_id={race_id} race_no={race_no} "
                f"deadline_time={deadline_time} deadline_at={deadline_at}",
                flush=True,
            )

            race_row = {
                "race_id": race_id,
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

            race_saved = upsert_rows(
                "v2_races",
                [race_row],
                "race_id",
                chunk_size=1,
            )

            entries = parse_entries(html or "", race_id)

            if entries:
                entries_saved = upsert_rows(
                    "v2_race_entries",
                    entries,
                    "race_id,lane",
                    chunk_size=20,
                )

        if DO_RESULTS and not do_odds:
            url = _official_url("raceresult", date_str, venue_id, race_no)
            html = _fetch(url)

            if not _looks_no_race(html):
                result_row = parse_result(html or "")
                result_row["race_id"] = race_id
                result_row["race_date"] = date_str

                result_saved = upsert_rows(
                    "v2_results",
                    [result_row],
                    "race_id",
                    chunk_size=1,
                )

        if do_odds and DO_ODDS:
            url = _official_url("odds3t", date_str, venue_id, race_no)
            html = _fetch(url)

            if not _looks_no_race(html):
                odds = parse_odds3t(html or "", race_id)

                if odds:
                    odds_saved = upsert_rows(
                        "v2_odds_trifecta",
                        odds,
                        "race_id,ticket",
                        chunk_size=300,
                    )

        if SLEEP_SEC > 0:
            time.sleep(SLEEP_SEC)

        return RaceResult(
            race_id=race_id,
            ok=True,
            race_saved=race_saved,
            entries_saved=entries_saved,
            result_saved=result_saved,
            odds_saved=odds_saved,
        )

    except Exception as exc:
        return RaceResult(
            race_id=race_id,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )


# ============================================================
# Main
# ============================================================

def main() -> None:
    _require_settings()
    ensure_venues()

    if REPAIR_RACE_IDS:
        parsed_tasks: List[Tuple[str, str, int]] = []
        invalid_race_ids: List[str] = []

        for race_id in REPAIR_RACE_IDS:
            parsed = _parse_race_id(race_id)

            if parsed is None:
                invalid_race_ids.append(race_id)
            else:
                parsed_tasks.append(parsed)

        tasks = sorted(set(parsed_tasks))

        print(
            "REPAIR_RACE_IDS enabled: "
            f"requested={len(REPAIR_RACE_IDS)} "
            f"valid_tasks={len(tasks)} "
            f"invalid={len(invalid_race_ids)}",
            flush=True,
        )

        if invalid_race_ids:
            print("invalid REPAIR_RACE_IDS sample:", flush=True)

            for race_id in invalid_race_ids[:20]:
                print(f"  {race_id}", flush=True)

        if not tasks:
            raise RuntimeError(
                "REPAIR_RACE_IDSは設定されていますが、有効なrace_idがありません。"
            )

    else:
        dates = list(_daterange(START_DATE, END_DATE))

        tasks = [
            (date_str, venue_id, race_no)
            for date_str in dates
            for venue_id in REPAIR_VENUES
            for race_no in REPAIR_RACE_NOS
        ]

    print("=== 全場・全R 月次補修開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"venues: {','.join(REPAIR_VENUES)}", flush=True)
    print(
        f"race_nos: {','.join(map(str, REPAIR_RACE_NOS))}",
        flush=True,
    )
    print(
        f"DO_RACES={DO_RACES} DO_RESULTS={DO_RESULTS} DO_ODDS={DO_ODDS}",
        flush=True,
    )
    print(
        f"WORKERS={WORKERS} ODDS_WORKERS={ODDS_WORKERS} "
        f"SLEEP_SEC={SLEEP_SEC}",
        flush=True,
    )
    print(f"task_count: {len(tasks)}", flush=True)

    total_race_saved = 0
    total_entries_saved = 0
    total_result_saved = 0
    total_odds_saved = 0

    success = 0
    no_race = 0
    failed: List[RaceResult] = []
    active_tasks: List[Tuple[str, str, int]] = []

    with ThreadPoolExecutor(max_workers=max(1, WORKERS)) as executor:
        futures = {
            executor.submit(process_race, date_str, venue_id, race_no, False):
            (date_str, venue_id, race_no)
            for date_str, venue_id, race_no in tasks
        }

        for idx, future in enumerate(as_completed(futures), start=1):
            result = future.result()

            if result.ok:
                success += 1
                total_race_saved += result.race_saved
                total_entries_saved += result.entries_saved
                total_result_saved += result.result_saved
                active_tasks.append(futures[future])

            elif result.no_race:
                no_race += 1

            else:
                failed.append(result)

            if idx % 100 == 0 or idx == len(tasks):
                print(
                    f"progress race/result: {idx}/{len(tasks)} "
                    f"success={success} no_race={no_race} "
                    f"failed={len(failed)}",
                    flush=True,
                )

    odds_success = 0
    odds_failed: List[RaceResult] = []

    if DO_ODDS:
        if DO_RACES:
            odds_tasks = sorted(set(active_tasks))

            print(
                f"odds_target_filter: before={len(tasks)} "
                f"after={len(odds_tasks)} "
                f"skipped_no_race={len(tasks) - len(odds_tasks)}",
                flush=True,
            )

        else:
            odds_tasks = tasks

            print(
                f"odds_target_filter: DO_RACES=False -> "
                f"all_tasks={len(odds_tasks)}",
                flush=True,
            )

        if odds_tasks:
            with ThreadPoolExecutor(max_workers=max(1, ODDS_WORKERS)) as executor:
                futures = {
                    executor.submit(process_race, date_str, venue_id, race_no, True):
                    (date_str, venue_id, race_no)
                    for date_str, venue_id, race_no in odds_tasks
                }

                for idx, future in enumerate(as_completed(futures), start=1):
                    result = future.result()

                    if result.ok:
                        odds_success += 1
                        total_odds_saved += result.odds_saved

                    elif not result.no_race:
                        odds_failed.append(result)

                    if idx % 100 == 0 or idx == len(odds_tasks):
                        print(
                            f"progress odds: {idx}/{len(odds_tasks)} "
                            f"odds_success={odds_success} "
                            f"odds_failed={len(odds_failed)} "
                            f"odds_rows={total_odds_saved}",
                            flush=True,
                        )

        else:
            print(
                "odds_targets=0 のためオッズ取得をスキップします。",
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

        for result in failed[:80]:
            print(
                f"  {result.race_id} {result.error}",
                flush=True,
            )

    if odds_failed:
        print(f"odds失敗: {len(odds_failed)}", flush=True)
        print("odds失敗 race_id sample:", flush=True)

        for result in odds_failed[:80]:
            print(
                f"  {result.race_id} {result.error}",
                flush=True,
            )


if __name__ == "__main__":
    try:
        main()

    except Exception:
        print("FATAL ERROR", flush=True)
        traceback.print_exc()
        raise