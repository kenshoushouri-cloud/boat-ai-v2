# -*- coding: utf-8 -*-
"""Compliant structural probe for 艇国データバンク historical motor pages.

Purpose:
- prove that a known motor-detail URL exposes dated historical race rows;
- verify that a target cutoff can exclude target/future rows;
- create the foundation for supplemental prior-only historical reconstruction.

This probe does NOT write PostgreSQL and does NOT use aggregate values as if
they were historical snapshots. The target source is supplemental to BOAT RACE
official data.

Published access rules encoded here:
- at least 3 seconds between automated requests;
- known existing URLs only;
- no static asset fetching;
- single-process/single-IP usage;
- do not use 艇国 for program/result/racer-term bulk categories where the
  BOAT RACE official download service is required.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


TEIKOKU_HOST = "boatrace-db.net"
MIN_ACCESS_INTERVAL_SEC = 3.0
KNOWN_MOTOR_URL_RE = re.compile(
    r"^https://boatrace-db\.net/stadium/mdetail/pid/(?P<pid>\d{2})/mno/(?P<mno>\d{1,3})/$"
)
USER_AGENT = "boat-ai-v2-historical-research/1.0 (compliant supplemental probe)"


@dataclass(frozen=True)
class DatedToken:
    year: int
    month: int
    day: int

    @property
    def iso(self) -> str:
        return date(self.year, self.month, self.day).isoformat()


class AccessLimiter:
    def __init__(self, interval_sec: float = MIN_ACCESS_INTERVAL_SEC) -> None:
        if interval_sec < 3.0:
            raise ValueError("艇国 automated access interval must be >= 3 seconds")
        self.interval_sec = float(interval_sec)
        self._last_request_at: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._last_request_at is not None:
            remaining = self.interval_sec - (now - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()


def validate_known_motor_url(url: str) -> tuple[str, int]:
    if urlparse(url).hostname != TEIKOKU_HOST:
        raise ValueError("unexpected host")
    match = KNOWN_MOTOR_URL_RE.fullmatch(url)
    if match is None:
        raise ValueError("only known motor-detail URL shape is allowed")
    return match.group("pid"), int(match.group("mno"))


def fetch_html(url: str, limiter: AccessLimiter) -> str:
    validate_known_motor_url(url)
    limiter.wait()
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def extract_dated_tokens(text: str, *, default_year: int) -> list[DatedToken]:
    """Extract ordered year/month/day tokens without inventing missing dates.

    An explicit YYYY年M月D日 token updates the current year.
    A later M月D日 token is interpreted only with that established/current year.
    """
    normalized = _norm(text)
    pattern = re.compile(
        r"(?:(?P<year>20\d{2})\s*年\s*)?"
        r"(?P<month>1[0-2]|0?[1-9])\s*月\s*"
        r"(?P<day>3[01]|[12]\d|0?[1-9])\s*日"
    )
    current_year = default_year
    out: list[DatedToken] = []
    for match in pattern.finditer(normalized):
        if match.group("year"):
            current_year = int(match.group("year"))
        token = DatedToken(
            current_year,
            int(match.group("month")),
            int(match.group("day")),
        )
        # Date constructor validates impossible dates.
        date(token.year, token.month, token.day)
        out.append(token)
    return out


def prior_only_tokens(tokens: Iterable[DatedToken], cutoff: date) -> list[DatedToken]:
    return [t for t in tokens if date(t.year, t.month, t.day) < cutoff]


def summarize_motor_page(html: str, *, cutoff: date) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    text = _norm(soup.get_text(" ", strip=True))
    tokens = extract_dated_tokens(text, default_year=cutoff.year)
    prior = prior_only_tokens(tokens, cutoff)
    future_or_target = [
        t for t in tokens if date(t.year, t.month, t.day) >= cutoff
    ]

    title = _norm(soup.title.get_text(" ", strip=True)) if soup.title else ""
    period_match = re.search(
        r"集計期間\s*[：:]?\s*([^。]+)",
        text,
    )
    update_match = re.search(
        r"最終データ更新\s*[：:]?\s*(20\d{2}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})",
        text,
    )

    tables = soup.find_all("table")
    table_widths: list[int] = []
    date_bearing_rows = 0
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["th", "td"])
            if cells:
                table_widths.append(len(cells))
            row_text = _norm(row.get_text(" ", strip=True))
            if re.search(r"(?:20\d{2}\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*日", row_text):
                date_bearing_rows += 1

    return {
        "title": title,
        "aggregate_period_text": period_match.group(1).strip() if period_match else None,
        "last_data_update": update_match.group(1) if update_match else None,
        "table_count": len(tables),
        "table_row_width_min": min(table_widths) if table_widths else None,
        "table_row_width_max": max(table_widths) if table_widths else None,
        "date_bearing_rows": date_bearing_rows,
        "dated_token_count": len(tokens),
        "prior_only_token_count": len(prior),
        "target_or_future_token_count": len(future_or_target),
        "prior_only_min_date": min((t.iso for t in prior), default=None),
        "prior_only_max_date": max((t.iso for t in prior), default=None),
        "target_or_future_min_date": min(
            (t.iso for t in future_or_target), default=None
        ),
        "prior_only_reconstruction_possible": bool(prior and future_or_target),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--url",
        default="https://boatrace-db.net/stadium/mdetail/pid/24/mno/60/",
    )
    ap.add_argument("--cutoff-date", default="2025-07-15")
    ap.add_argument("--output", default="teikoku-motor-history-probe.json")
    args = ap.parse_args()

    pid, mno = validate_known_motor_url(args.url)
    cutoff = date.fromisoformat(args.cutoff_date)
    html = fetch_html(args.url, AccessLimiter())
    summary = summarize_motor_page(html, cutoff=cutoff)

    payload = {
        "contract": "TEIKOKU_MOTOR_HISTORY_PREDEADLINE_PROBE_V1",
        "source": "TEIKOKU_DATA_BANK",
        "source_role": "supplemental_only",
        "url": args.url,
        "pid": pid,
        "motor_no": mno,
        "cutoff_date": cutoff.isoformat(),
        "access_interval_sec": MIN_ACCESS_INTERVAL_SEC,
        "known_url_only": True,
        "static_assets_fetched": False,
        "program_result_racer_term_bulk_used": False,
        "aggregate_values_used_as_historical_snapshot": False,
        "future_rows_used": False,
        "db_read": False,
        "db_write": False,
        "production_change": False,
        "purchase_action": False,
        "summary": summary,
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("TEIKOKU_MOTOR_PROBE=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))

    if summary["prior_only_reconstruction_possible"] is not True:
        raise RuntimeError("dated history cannot yet support strict prior-only reconstruction")
    print("TEIKOKU_MOTOR_PROBE_RESULT=PASS_PRIOR_ONLY_STRUCTURE")


if __name__ == "__main__":
    main()
