# -*- coding: utf-8 -*-
"""Respectful read-only 艇国データバンク pre-race table cross-check.

Phase 1 intentionally does NOT persist third-party data. It verifies that a
known historical race page exposes a distinct pre-race entry table containing
the fields we may use to cross-check BOAT RACE official historical inputs.

Site-access contract:
- boatrace-db.net only;
- known race-detail URLs only;
- >=3.0 seconds between automated requests;
- one process / no parallelism;
- HTML page only; no static assets;
- no result/payout extraction;
- no DB write.

The page itself can contain results because it is an archive page. This parser
selects only the table containing the pre-race markers 今期/全国/当地/モータ/
ボート and never parses payout/result tables.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


MIN_INTERVAL_SEC = 3.05
URL_RE = re.compile(
    r"^https://boatrace-db\.net/race/detail/date/(?P<date>\d{8})/"
    r"pid/(?P<pid>\d{2})/rno/(?P<rno>\d{1,2})/$"
)
PRE_RACE_MARKERS = ("今期", "全国", "当地", "モータ", "ボート")
FORBIDDEN_RESULT_MARKERS = ("3連単", "3連複", "2連単", "2連複", "払戻")


@dataclass
class FetchAudit:
    request_count: int = 0
    last_request_monotonic: float | None = None


class RespectfulFetcher:
    def __init__(
        self,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.sleep_fn = sleep_fn
        self.clock_fn = clock_fn
        self.audit = FetchAudit()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "boat-ai-v2-historical-crosscheck/1.0 "
                    "(research; single-thread; >=3s interval)"
                )
            }
        )

    def get(self, url: str) -> str:
        validate_url(url)
        now = self.clock_fn()
        if self.audit.last_request_monotonic is not None:
            elapsed = now - self.audit.last_request_monotonic
            if elapsed < MIN_INTERVAL_SEC:
                self.sleep_fn(MIN_INTERVAL_SEC - elapsed)
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        self.audit.request_count += 1
        self.audit.last_request_monotonic = self.clock_fn()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text


def validate_url(url: str) -> re.Match[str]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "boatrace-db.net":
        raise ValueError("only https://boatrace-db.net is allowed")
    m = URL_RE.fullmatch(url)
    if not m:
        raise ValueError("only known race-detail URL shape is allowed")
    rno = int(m.group("rno"))
    if not 1 <= rno <= 12:
        raise ValueError("race number must be 1..12")
    return m


def find_pre_race_table(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        if all(marker in text for marker in PRE_RACE_MARKERS):
            candidates.append((table, text))

    if len(candidates) != 1:
        raise RuntimeError(
            f"expected exactly one pre-race table, found {len(candidates)}"
        )

    table, text = candidates[0]
    # Fail closed if result/payout labels leaked into the selected table.
    leaked = [x for x in FORBIDDEN_RESULT_MARKERS if x in text]
    if leaked:
        raise RuntimeError(f"selected table contains result markers: {leaked}")

    racer_ids = []
    for value in re.findall(r"(?<!\d)([2-5]\d{3})(?!\d)", text):
        if value not in racer_ids:
            racer_ids.append(value)

    rows = table.find_all("tr")
    return {
        "markers_present": list(PRE_RACE_MARKERS),
        "racer_number_candidates": racer_ids,
        "table_rows": len(rows),
        "result_markers_excluded": True,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--url",
        default="https://boatrace-db.net/race/detail/date/20250701/pid/19/rno/10/",
    )
    ap.add_argument(
        "--expected-racers",
        default="3618,5231,4678,5138,5214,5255",
        help="comma-separated known official racer numbers for cross-check only",
    )
    args = ap.parse_args()

    identity = validate_url(args.url)
    fetcher = RespectfulFetcher()
    html = fetcher.get(args.url)
    table = find_pre_race_table(html)

    expected = [x.strip() for x in args.expected_racers.split(",") if x.strip()]
    found = set(table["racer_number_candidates"])
    missing = [x for x in expected if x not in found]
    if missing:
        raise RuntimeError(f"expected racers missing from pre-race table: {missing}")

    payload = {
        "contract": "TEIKOKU_PREDEADLINE_CROSSCHECK_V1",
        "source_role": "CROSSCHECK_ONLY",
        "target_date": identity.group("date"),
        "venue_pid": identity.group("pid"),
        "race_no": int(identity.group("rno")),
        "request_count": fetcher.audit.request_count,
        "minimum_request_interval_sec": MIN_INTERVAL_SEC,
        "parallel_requests": False,
        "static_asset_requests": False,
        "pre_race_table": table,
        "expected_racers_matched": len(expected),
        "result_fields_parsed": False,
        "payout_fields_parsed": False,
        "db_write": False,
        "production_change": False,
        "line": False,
        "stake_change": False,
        "purchase_action": False,
    }
    print("TEIKOKU_CROSSCHECK=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))
    print("TEIKOKU_CROSSCHECK_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
