# -*- coding: utf-8 -*-
"""
repair_month_all_pg.py

Railway PostgreSQL版・完全差し替え用。

VERSION:
2026-08-19 deadline-race-scope-v9

主な修正:
- race_no ごとの締切時刻を厳密に取得。
- 全12Rを含む親div/sectionから1R締切を拾う不具合を修正。
- 1R が 11R / 12R に部分一致しない。
- 対象Rの時刻が取得できない場合、別Rの時刻で補完しない。
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


VERSION = "2026-08-19 deadline-race-scope-v9"

START_DATE = (
    os.getenv("REPAIR_START_DATE")
    or os.getenv("START_DATE")
    or "2026-05-01"
)

END_DATE = (
    os.getenv("REPAIR_END_DATE")
    or os.getenv("END_DATE")
    or "2026-05-31"
)

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

DO_RACES = (
    os.getenv("REPAIR_DO_RACES")
    or os.getenv("DO_RACES")
    or "1"
) == "1"

DO_RESULTS = (
    os.getenv("REPAIR_DO_RESULTS")
    or os.getenv("DO_RESULTS")
    or "1"
) == "1"

DO_ODDS = (
    os.getenv("REPAIR_DO_ODDS")
    or os.getenv("DO_ODDS")
    or "1"
) == "1"

SLEEP_SEC = float(
    os.getenv("REPAIR_SLEEP_SEC")
    or os.getenv("SLEEP_SEC")
    or "0.1"
)

WORKERS = int(
    os.getenv("REPAIR_WORKERS")
    or os.getenv("WORKERS")
    or "6"
)

ODDS_WORKERS = int(
    os.getenv("REPAIR_ODDS_WORKERS")
    or os.getenv("ODDS_WORKERS")
    or "2"
)

HTTP_TIMEOUT = int(
    os.getenv("HTTP_TIMEOUT")
    or "25"
)

MAX_RETRIES = int(
    os.getenv("HTTP_MAX_RETRIES")
    or "2"
)

SOURCE = (
    os.getenv("REPAIR_SOURCE")
    or "repair_month_all_pg"
)

ODDS_IS_FINAL = (
    os.getenv("ODDS_IS_FINAL")
    or "0"
) == "1"

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

CLASS_MAP = {
    "B2": 1,
    "B1": 2,
    "A2": 3,
    "A1": 4,
}


SESSION = requests.Session()

SESSION.headers.update(
    {
        "User-Agent":
            "Mozilla/5.0 "
            "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)",

        "Accept-Language":
            "ja,en-US;q=0.8,en;q=0.6",
    }
)


def _now_iso() -> str:
    return datetime.now(JST).isoformat()


def _race_id(
    date_str: str,
    venue_id: str,
    race_no: int,
) -> str:

    return (
        f"{date_str.replace('-', '')}_"
        f"{venue_id.zfill(2)}_"
        f"{int(race_no):02d}"
    )


def _parse_race_id(
    race_id: str,
) -> Optional[Tuple[str, str, int]]:

    match = re.fullmatch(
        r"(\d{4})(\d{2})(\d{2})_(\d{2})_(\d{2})",
        str(race_id or "").strip(),
    )

    if not match:
        return None

    date_str = (
        f"{match.group(1)}-"
        f"{match.group(2)}-"
        f"{match.group(3)}"
    )

    venue_id = match.group(4)
    race_no = int(match.group(5))

    try:
        datetime.strptime(
            date_str,
            "%Y-%m-%d",
        )

    except ValueError:
        return None

    if venue_id not in ALL_VENUES:
        return None

    if not 1 <= race_no <= 12:
        return None

    return (
        date_str,
        venue_id,
        race_no,
    )


def _yyyymmdd(
    date_str: str,
) -> str:

    return date_str.replace("-", "")


def _daterange(
    start_str: str,
    end_str: str,
) -> Iterable[str]:

    start = datetime.strptime(
        start_str,
        "%Y-%m-%d",
    )

    end = datetime.strptime(
        end_str,
        "%Y-%m-%d",
    )

    current = start

    while current <= end:

        yield current.strftime(
            "%Y-%m-%d"
        )

        current += timedelta(days=1)


def _to_int(
    value: Any,
) -> Optional[int]:

    if value is None:
        return None

    text = (
        str(value)
        .strip()
        .replace(",", "")
    )

    if (
        not text
        or text in (
            "-",
            "--",
            "欠",
            "欠場",
        )
    ):
        return None

    match = re.search(
        r"-?\d+",
        text,
    )

    return (
        int(match.group(0))
        if match
        else None
    )


def _clean_text(
    value: Any,
) -> str:

    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _html_text(
    html: str,
) -> str:

    return BeautifulSoup(
        html,
        "html.parser",
    ).get_text(
        " ",
        strip=True,
    )


def _official_url(
    kind: str,
    date_str: str,
    venue_id: str,
    race_no: int,
) -> str:

    return (
        f"https://www.boatrace.jp/"
        f"owpc/pc/race/{kind}"
        f"?rno={int(race_no)}"
        f"&jcd={venue_id.zfill(2)}"
        f"&hd={_yyyymmdd(date_str)}"
    )


def _fetch(
    url: str,
) -> Optional[str]:

    last_error = None

    for attempt in range(
        MAX_RETRIES + 1
    ):

        try:

            response = SESSION.get(
                url,
                timeout=HTTP_TIMEOUT,
            )

            if response.status_code == 404:
                return None

            if not response.ok:

                last_error = (
                    f"HTTP "
                    f"{response.status_code}"
                )

                time.sleep(
                    0.5
                    + attempt * 0.5
                )

                continue

            encoding = (
                response.encoding
                or ""
            ).strip()

            if not encoding:
                encoding = "utf-8"

            try:

                return (
                    response.content
                    .decode(
                        encoding
                    )
                )

            except Exception:

                return (
                    response.content
                    .decode(
                        "utf-8",
                        errors="replace",
                    )
                )

        except Exception as exc:

            last_error = str(exc)

            time.sleep(
                0.5
                + attempt * 0.5
            )

    print(
        f"fetch failed: "
        f"{url} "
        f"err={last_error}",
        flush=True,
    )

    return None


def _looks_no_race(
    html: Optional[str],
) -> bool:

    if not html:
        return True

    text = _html_text(html)

    return any(
        word in text
        for word in [
            "データがありません",
            "レース情報がありません",
            "該当するデータはありません",
            "発売しておりません",
        ]
    )


def upsert_rows(
    table: str,
    rows: List[Dict[str, Any]],
    on_conflict: str,
    chunk_size: int = 500,
) -> int:

    if not rows:
        return 0

    total = 0

    conflict_cols = [
        column.strip()
        for column
        in on_conflict.split(",")
        if column.strip()
    ]

    for i in range(
        0,
        len(rows),
        chunk_size,
    ):

        total += pg_upsert_rows(
            table=table,
            rows=rows[
                i:i + chunk_size
            ],
            conflict_cols=conflict_cols,
        )

    return total


def ensure_venues() -> None:

    rows = []

    for venue_id in ALL_VENUES:

        rows.append(
            {
                "venue_code": venue_id,
                "venue_id": venue_id,
                "venue_name":
                    VENUE_NAMES[
                        venue_id
                    ],
                "is_active": True,
                "updated_at":
                    _now_iso(),
            }
        )

    upsert_rows(
        "v2_venues",
        rows,
        "venue_id",
        100,
    )

    print(
        f"✅ v2_venues upsert: "
        f"{len(rows)}",
        flush=True,
    )


def _zen_to_han(
    text: str,
) -> str:

    return str(
        text or ""
    ).translate(
        str.maketrans(
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
    )


def _normalize_hhmm(
    value: str,
) -> Optional[str]:

    match = re.fullmatch(
        r"\s*(\d{1,2}):(\d{2})\s*",
        value or "",
    )

    if not match:
        return None

    hour = int(
        match.group(1)
    )

    minute = int(
        match.group(2)
    )

    if not (
        0 <= hour <= 23
        and 0 <= minute <= 59
    ):
        return None

    return (
        f"{hour:02d}:"
        f"{minute:02d}"
    )


def parse_deadline_time(
    html: str,
    race_no: int,
) -> Optional[str]:
    """
    対象race_noの締切予定時刻だけを取得する。

    重要:
    - div / section の親要素を使わない。
    - 1Rが11Rや12Rへ部分一致しない。
    - 対象Rを特定できない場合、
      他Rの締切時刻を代用しない。
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    target_no = int(
        race_no
    )

    full_text = _clean_text(
        _zen_to_han(
            soup.get_text(
                " ",
                strip=True,
            )
        )
    )

    target_pattern = re.compile(
        rf"(?<!\d)"
        rf"(?:第\s*)?"
        rf"{target_no}"
        rf"\s*R"
        rf"(?!\d)",
        flags=re.IGNORECASE,
    )

    deadline_patterns = [
        re.compile(
            r"締切予定時刻\s*"
            r"(\d{1,2}:\d{2})"
        ),
        re.compile(
            r"締切予定\s*"
            r"(\d{1,2}:\d{2})"
        ),
        re.compile(
            r"投票締切予定時刻\s*"
            r"(\d{1,2}:\d{2})"
        ),
        re.compile(
            r"発売締切\s*"
            r"(\d{1,2}:\d{2})"
        ),
        re.compile(
            r"締切時刻\s*"
            r"(\d{1,2}:\d{2})"
        ),
        re.compile(
            r"締切\s*"
            r"(\d{1,2}:\d{2})"
        ),
    ]

    # 小さいDOM単位だけ確認。
    # div/sectionは全12Rを含む可能性があるため除外。
    for node in soup.find_all(
        [
            "tr",
            "li",
        ]
    ):

        text = _clean_text(
            _zen_to_han(
                node.get_text(
                    " ",
                    strip=True,
                )
            )
        )

        if not text:
            continue

        if not target_pattern.search(
            text
        ):
            continue

        for pattern in deadline_patterns:

            match = pattern.search(
                text
            )

            if match:

                normalized = (
                    _normalize_hhmm(
                        match.group(1)
                    )
                )

                if normalized:
                    return normalized

        times = re.findall(
            r"(?<!\d)"
            r"(\d{1,2}:\d{2})"
            r"(?!\d)",
            text,
        )

        for value in reversed(
            times
        ):

            normalized = (
                _normalize_hhmm(
                    value
                )
            )

            if normalized:
                return normalized

    # 本文上で対象Rから次のRまでに限定。
    any_race_pattern = re.compile(
        r"(?<!\d)"
        r"(?:第\s*)?"
        r"([1-9]|1[0-2])"
        r"\s*R"
        r"(?!\d)",
        flags=re.IGNORECASE,
    )

    for target_match in (
        target_pattern.finditer(
            full_text
        )
    ):

        start = (
            target_match.start()
        )

        end = min(
            len(full_text),
            start + 500,
        )

        for next_match in (
            any_race_pattern
            .finditer(
                full_text,
                target_match.end(),
            )
        ):

            next_no = int(
                next_match.group(1)
            )

            if next_no != target_no:

                end = min(
                    end,
                    next_match.start(),
                )

                break

        nearby = full_text[
            start:end
        ]

        for pattern in deadline_patterns:

            match = pattern.search(
                nearby
            )

            if match:

                normalized = (
                    _normalize_hhmm(
                        match.group(1)
                    )
                )

                if normalized:
                    return normalized

        times = re.findall(
            r"(?<!\d)"
            r"(\d{1,2}:\d{2})"
            r"(?!\d)",
            nearby,
        )

        for value in reversed(
            times
        ):

            normalized = (
                _normalize_hhmm(
                    value
                )
            )

            if normalized:
                return normalized

    # rno指定単一Rページ用。
    # 対象Rが本文に存在する場合のみ許可。
    if target_pattern.search(
        full_text
    ):

        for pattern in deadline_patterns:

            match = pattern.search(
                full_text
            )

            if match:

                normalized = (
                    _normalize_hhmm(
                        match.group(1)
                    )
                )

                if normalized:
                    return normalized

    return None


def make_deadline_at(
    date_str: str,
    deadline_time: Optional[str],
) -> Optional[str]:

    if not deadline_time:
        return None

    try:

        hour, minute = map(
            int,
            deadline_time.split(":"),
        )

        base = datetime.strptime(
            date_str,
            "%Y-%m-%d",
        )

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


def parse_race_name(
    html: str,
) -> Optional[str]:

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for selector in [
        "h2",
        "h3",
        ".title",
        ".heading2",
        ".is-title",
    ]:

        node = soup.select_one(
            selector
        )

        if node:

            text = _clean_text(
                node.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                text
                and "BOAT"
                not in text.upper()
            ):
                return text[:100]

    return None


def _num_token(
    value: str,
) -> Optional[float]:

    try:

        return float(
            str(value)
            .replace(",", "")
        )

    except Exception:
        return None


def parse_entries(
    html: str,
    race_id: str,
) -> List[Dict[str, Any]]:

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    raw_lines = []

    for line in (
        soup
        .get_text(
            "\n",
            strip=True,
        )
        .splitlines()
    ):

        line = _clean_text(
            _zen_to_han(
                line
            )
        )

        if line:
            raw_lines.append(
                line
            )

    body_start = 0

    for i, line in enumerate(
        raw_lines
    ):

        if "登録番号/級別" in line:
            body_start = i
            break

    body_end = len(
        raw_lines
    )

    for i in range(
        body_start + 1,
        len(raw_lines),
    ):

        if raw_lines[i] in (
            "今節成績",
            "モーター・ボート変更時は赤で表示されます。",
            "PAGE TOP",
        ):

            body_end = i
            break

    lines = raw_lines[
        body_start:body_end
    ]

    lane_positions = []

    for i, line in enumerate(
        lines
    ):

        if not re.fullmatch(
            r"[1-6]",
            line,
        ):
            continue

        look = " ".join(
            lines[i:i + 8]
        )

        if re.search(
            r"\b\d{4}\s*/\s*"
            r"(A1|A2|B1|B2)\b",
            look,
        ):

            lane_positions.append(
                (
                    int(line),
                    i,
                )
            )

    entries = {}

    for idx, (
        lane,
        position,
    ) in enumerate(
        lane_positions
    ):

        next_position = (
            lane_positions[
                idx + 1
            ][1]
            if idx + 1
            < len(lane_positions)
            else len(lines)
        )

        segment_lines = lines[
            position:
            next_position
        ]

        segment = " ".join(
            segment_lines
        )

        match = re.search(
            r"\b(\d{4})\s*/\s*"
            r"(A1|A2|B1|B2)\b",
            segment,
        )

        if not match:
            continue

        numbers = re.findall(
            r"\d+\.\d+|\d+",
            segment,
        )

        avg_index = next(
            (
                k
                for k, token
                in enumerate(numbers)
                if re.fullmatch(
                    r"0\.\d{2}",
                    token,
                )
            ),
            None,
        )

        sequence = (
            numbers[avg_index:]
            if avg_index is not None
            else []
        )

        def fseq(
            n: int,
        ) -> Optional[float]:

            if len(sequence) <= n:
                return None

            return _num_token(
                sequence[n]
            )

        def iseq(
            n: int,
        ) -> Optional[int]:

            if len(sequence) <= n:
                return None

            return _to_int(
                sequence[n]
            )

        entries[lane] = {
            "race_id": race_id,
            "lane": lane,
            "course": lane,
            "racer_number":
                int(match.group(1)),
            "racer_class":
                CLASS_MAP.get(
                    match.group(2)
                ),
            "racer_class_text":
                match.group(2),

            "avg_st": fseq(0),

            "national_win_rate":
                fseq(1),

            "national_place2_rate":
                fseq(2),

            "national_place3_rate":
                fseq(3),

            "local_win_rate":
                fseq(4),

            "local_place2_rate":
                fseq(5),

            "local_place3_rate":
                fseq(6),

            "motor_no":
                iseq(7),

            "motor_place2_rate":
                fseq(8),

            "motor_place3_rate":
                fseq(9),

            "boat_no":
                iseq(10),

            "boat_place2_rate":
                fseq(11),

            "boat_place3_rate":
                fseq(12),

            "recent_form": [],

            "updated_at":
                _now_iso(),
        }

    return [
        entries[lane]
        for lane in sorted(
            entries
        )
    ]


def parse_result(
    html: str,
) -> Dict[str, Any]:

    text = _html_text(
        html
    )

    row = {
        "result_status":
            "parse_error",

        "race_status":
            "parse_error",

        "trifecta_ticket":
            None,

        "trifecta_payout_yen":
            0,

        "source":
            SOURCE,

        "fetched_at":
            _now_iso(),
    }

    match = re.search(
        r"3\s*連\s*単\s*"
        r"([1-6])\s*[-－ー]?\s*"
        r"([1-6])\s*[-－ー]?\s*"
        r"([1-6])"
        r"\s*[¥￥]?\s*"
        r"([\d,]+)\s*円?",
        text,
    )

    if match:

        first = int(
            match.group(1)
        )

        second = int(
            match.group(2)
        )

        third = int(
            match.group(3)
        )

        payout = int(
            match.group(4)
            .replace(",", "")
        )

        if (
            len(
                {
                    first,
                    second,
                    third,
                }
            ) == 3
            and payout > 0
        ):

            row.update(
                {
                    "first_lane":
                        first,

                    "second_lane":
                        second,

                    "third_lane":
                        third,

                    "trifecta_ticket":
                        f"{first}-"
                        f"{second}-"
                        f"{third}",

                    "trifecta_payout_yen":
                        payout,

                    "result_status":
                        "official",

                    "race_status":
                        "official",
                }
            )

    return row


def parse_odds3t(
    html: str,
    race_id: str,
) -> List[Dict[str, Any]]:

    text = _html_text(
        html
    )

    rows = {}

    valid_tickets = {
        f"{a}-{b}-{c}"
        for a, b, c
        in itertools.permutations(
            [1, 2, 3, 4, 5, 6],
            3,
        )
    }

    for match in re.finditer(
        r"([1-6])\s*[-－]\s*"
        r"([1-6])\s*[-－]\s*"
        r"([1-6])\s+"
        r"([0-9]+(?:\.[0-9]+)?)",
        text,
    ):

        a = match.group(1)
        b = match.group(2)
        c = match.group(3)

        if len(
            {
                a,
                b,
                c,
            }
        ) < 3:
            continue

        ticket = (
            f"{a}-{b}-{c}"
        )

        odds = float(
            match.group(4)
        )

        if (
            ticket in valid_tickets
            and odds > 0
        ):

            rows[ticket] = {
                "race_id":
                    race_id,

                "ticket":
                    ticket,

                "odds":
                    odds,

                "is_final":
                    ODDS_IS_FINAL,

                "fetched_at":
                    _now_iso(),
            }

    return sorted(
        rows.values(),
        key=lambda row:
            tuple(
                map(
                    int,
                    row["ticket"]
                    .split("-"),
                )
            ),
    )


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

    race_id = _race_id(
        date_str,
        venue_id,
        race_no,
    )

    try:

        race_saved = 0
        entries_saved = 0
        result_saved = 0
        odds_saved = 0

        if DO_RACES and not do_odds:

            html = _fetch(
                _official_url(
                    "racelist",
                    date_str,
                    venue_id,
                    race_no,
                )
            )

            if _looks_no_race(
                html
            ):

                return RaceResult(
                    race_id=race_id,
                    ok=False,
                    no_race=True,
                    error="no_race",
                )

            deadline_time = (
                parse_deadline_time(
                    html or "",
                    race_no,
                )
            )

            deadline_at = (
                make_deadline_at(
                    date_str,
                    deadline_time,
                )
            )

            print(
                f"DEADLINE "
                f"race_id={race_id} "
                f"race_no={race_no} "
                f"deadline_time="
                f"{deadline_time} "
                f"deadline_at="
                f"{deadline_at}",
                flush=True,
            )

            race_row = {
                "race_id":
                    race_id,

                "race_date":
                    date_str,

                "venue_code":
                    venue_id,

                "venue_id":
                    venue_id,

                "venue_name":
                    VENUE_NAMES.get(
                        venue_id,
                        venue_id,
                    ),

                "race_no":
                    int(race_no),

                "race_name":
                    parse_race_name(
                        html or ""
                    ),

                "deadline_time":
                    deadline_time,

                "deadline_at":
                    deadline_at,

                "status":
                    (
                        "official"
                        if DO_RESULTS
                        else "scheduled"
                    ),

                "data_quality_score":
                    0,

                "missing_count":
                    0,

                "updated_at":
                    _now_iso(),
            }

            race_saved = (
                upsert_rows(
                    "v2_races",
                    [race_row],
                    "race_id",
                    1,
                )
            )

            entries = (
                parse_entries(
                    html or "",
                    race_id,
                )
            )

            if entries:

                entries_saved = (
                    upsert_rows(
                        "v2_race_entries",
                        entries,
                        "race_id,lane",
                        20,
                    )
                )

        if DO_RESULTS and not do_odds:

            html = _fetch(
                _official_url(
                    "raceresult",
                    date_str,
                    venue_id,
                    race_no,
                )
            )

            if not _looks_no_race(
                html
            ):

                result_row = (
                    parse_result(
                        html or ""
                    )
                )

                result_row[
                    "race_id"
                ] = race_id

                result_row[
                    "race_date"
                ] = date_str

                result_saved = (
                    upsert_rows(
                        "v2_results",
                        [result_row],
                        "race_id",
                        1,
                    )
                )

        if do_odds and DO_ODDS:

            html = _fetch(
                _official_url(
                    "odds3t",
                    date_str,
                    venue_id,
                    race_no,
                )
            )

            if not _looks_no_race(
                html
            ):

                odds = (
                    parse_odds3t(
                        html or "",
                        race_id,
                    )
                )

                if odds:

                    odds_saved = (
                        upsert_rows(
                            "v2_odds_trifecta",
                            odds,
                            "race_id,ticket",
                            300,
                        )
                    )

        if SLEEP_SEC > 0:

            time.sleep(
                SLEEP_SEC
            )

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
            error=(
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )


def main() -> None:

    print(
        f"✅ repair_month_all_pg.py "
        f"VERSION {VERSION}",
        flush=True,
    )

    if not os.getenv(
        "DATABASE_URL"
    ):

        raise RuntimeError(
            "DATABASE_URL が未設定です"
        )

    ensure_venues()

    if REPAIR_RACE_IDS:

        parsed_tasks = []
        invalid_ids = []

        for race_id in (
            REPAIR_RACE_IDS
        ):

            parsed = (
                _parse_race_id(
                    race_id
                )
            )

            if parsed:
                parsed_tasks.append(
                    parsed
                )

            else:
                invalid_ids.append(
                    race_id
                )

        tasks = sorted(
            set(parsed_tasks)
        )

        print(
            "REPAIR_RACE_IDS enabled: "
            f"requested="
            f"{len(REPAIR_RACE_IDS)} "
            f"valid_tasks="
            f"{len(tasks)} "
            f"invalid="
            f"{len(invalid_ids)}",
            flush=True,
        )

        if not tasks:

            raise RuntimeError(
                "有効なREPAIR_RACE_IDS"
                "がありません"
            )

    else:

        tasks = [
            (
                date_str,
                venue_id,
                race_no,
            )
            for date_str
            in _daterange(
                START_DATE,
                END_DATE,
            )
            for venue_id
            in REPAIR_VENUES
            for race_no
            in REPAIR_RACE_NOS
        ]

    print(
        f"task_count: "
        f"{len(tasks)} "
        f"DO_RACES={DO_RACES} "
        f"DO_RESULTS={DO_RESULTS} "
        f"DO_ODDS={DO_ODDS}",
        flush=True,
    )

    total_race = 0
    total_entries = 0
    total_results = 0
    total_odds = 0

    success = 0
    no_race = 0

    failed = []

    active_tasks = []

    with ThreadPoolExecutor(
        max_workers=max(
            1,
            WORKERS,
        )
    ) as executor:

        futures = {
            executor.submit(
                process_race,
                date_str,
                venue_id,
                race_no,
                False,
            ): (
                date_str,
                venue_id,
                race_no,
            )
            for (
                date_str,
                venue_id,
                race_no,
            )
            in tasks
        }

        for future in (
            as_completed(
                futures
            )
        ):

            result = (
                future.result()
            )

            if result.ok:

                success += 1

                total_race += (
                    result.race_saved
                )

                total_entries += (
                    result.entries_saved
                )

                total_results += (
                    result.result_saved
                )

                active_tasks.append(
                    futures[future]
                )

            elif result.no_race:

                no_race += 1

            else:

                failed.append(
                    result
                )

    if DO_ODDS:

        odds_tasks = (
            sorted(
                set(active_tasks)
            )
            if DO_RACES
            else tasks
        )

        with ThreadPoolExecutor(
            max_workers=max(
                1,
                ODDS_WORKERS,
            )
        ) as executor:

            futures = [
                executor.submit(
                    process_race,
                    date_str,
                    venue_id,
                    race_no,
                    True,
                )
                for (
                    date_str,
                    venue_id,
                    race_no,
                )
                in odds_tasks
            ]

            for future in (
                as_completed(
                    futures
                )
            ):

                result = (
                    future.result()
                )

                if result.ok:

                    total_odds += (
                        result.odds_saved
                    )

    print(
        f"保存レース件数: "
        f"{total_race}",
        flush=True,
    )

    print(
        f"保存出走表件数: "
        f"{total_entries}",
        flush=True,
    )

    print(
        f"保存結果件数: "
        f"{total_results}",
        flush=True,
    )

    print(
        f"保存オッズ件数: "
        f"{total_odds}",
        flush=True,
    )

    print(
        f"成功: {success} "
        f"非開催/データなし: "
        f"{no_race} "
        f"失敗: {len(failed)}",
        flush=True,
    )

    if failed:

        for result in failed[:80]:

            print(
                f"  "
                f"{result.race_id} "
                f"{result.error}",
                flush=True,
            )


if __name__ == "__main__":

    try:

        main()

    except Exception:

        print(
            "FATAL ERROR",
            flush=True,
        )

        traceback.print_exc()

        raise