# -*- coding: utf-8 -*-
"""Historical pre-deadline source acquisition pilot.

Sources:
1. BOAT RACE official daily programme archive (B LZH) -- bulk/download service.
2. 艇国データバンク race-detail pages -- supplemental race-card snapshots.

Safety / provenance:
- no PostgreSQL access;
- no result/odds/payout parsing;
- 艇国 requests are sequential and enforce >=3 seconds between requests;
- only known, deterministic URLs are requested;
- raw source bytes are hashed and archived;
- a sanitized text extract starts at the race-card "場外締切" marker, so
  the outcome/result block that appears earlier on the historical page is not
  included in the feature-facing extract;
- historical replay may treat these race-card fields as pre-deadline values
  under the explicitly approved historical assumption, but they are never
  marked as prospective evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


USER_AGENT = "boat-ai-v2-historical-predeadline-pilot/1.0"
DEFAULT_MIN_INTERVAL_SEC = 3.2
TEIKOKU_DETAIL = (
    "https://boatrace-db.net/race/detail/date/{yyyymmdd}/"
    "pid/{venue}/rno/{race_no}/"
)
OFFICIAL_B = "https://www1.mbrace.or.jp/od2/B/{yyyymm}/b{yymmdd}.lzh"

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def teikoku_url(target_date: date, venue: int, race_no: int) -> str:
    return TEIKOKU_DETAIL.format(
        yyyymmdd=target_date.strftime("%Y%m%d"),
        venue=f"{venue:02d}",
        race_no=f"{race_no:02d}",
    )


def official_b_url(target_date: date) -> str:
    return OFFICIAL_B.format(
        yyyymm=target_date.strftime("%Y%m"),
        yymmdd=target_date.strftime("%y%m%d"),
    )


def extract_predeadline_text(html: str) -> dict[str, Any]:
    """Return result-blind race-card text beginning at the pre-race cutoff block."""
    soup = BeautifulSoup(html, "html.parser")
    text = normalize_text(soup.get_text(" ", strip=True))
    marker = "場外締切"
    pos = text.find(marker)
    if pos < 0:
        raise ValueError("predeadline marker not found")

    # Historical 艇国 detail pages render result/payoff blocks before the second
    # race-card block. Keeping only this tail prevents those outcome values from
    # entering the structured backfill path.
    tail = text[pos:]

    required_markers = ("今期", "全国", "当地", "モータ")
    missing = [x for x in required_markers if x not in tail]
    if missing:
        raise ValueError(f"race-card markers missing: {missing}")

    m = re.search(r"場外締切\s*(\d{1,2}:\d{2})", tail)
    if not m:
        raise ValueError("deadline not found")

    return {
        "deadline_text": m.group(1),
        "predeadline_text": tail,
        "required_markers": list(required_markers),
        "outcome_prefix_removed": True,
    }


class MinInterval:
    def __init__(self, seconds: float) -> None:
        self.seconds = max(3.0, float(seconds))
        self._last: float | None = None

    def wait(self) -> float:
        now = time.monotonic()
        slept = 0.0
        if self._last is not None:
            delta = now - self._last
            if delta < self.seconds:
                slept = self.seconds - delta
                time.sleep(slept)
        self._last = time.monotonic()
        return slept


def fetch(url: str, *, timeout: int = 35) -> requests.Response:
    response = SESSION.get(url, timeout=timeout)
    response.raise_for_status()
    return response


def run(
    *,
    target_date: date,
    venue: int,
    race_start: int,
    race_end: int,
    output_dir: Path,
    min_interval_sec: float,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    acquired_at = datetime.now(timezone.utc).isoformat()

    manifest: dict[str, Any] = {
        "contract": "HISTORICAL_PREDEADLINE_ACQUISITION_PILOT_V1",
        "target_date": target_date.isoformat(),
        "venue_code": f"{venue:02d}",
        "race_start": race_start,
        "race_end": race_end,
        "historical_predeadline_assumption": True,
        "assumption_basis": (
            "race-card values displayed for the historical race are treated as "
            "the pre-deadline historical snapshot for backtest reconstruction"
        ),
        "prospective_evidence": False,
        "outcome_fields_used": False,
        "db_write": False,
        "production_change": False,
        "line_send": False,
        "purchase_action": False,
        "teikoku_min_interval_sec": max(3.0, float(min_interval_sec)),
        "acquired_at_utc": acquired_at,
        "official_programme": {},
        "races": [],
    }

    # Official bulk download: one request for the day's programme archive.
    b_url = official_b_url(target_date)
    b_res = fetch(b_url)
    b_bytes = b_res.content
    if len(b_bytes) < 500:
        raise RuntimeError("official programme archive unexpectedly small")
    b_name = f"official_b_{target_date.strftime('%Y%m%d')}.lzh"
    (output_dir / b_name).write_bytes(b_bytes)
    manifest["official_programme"] = {
        "source": "boatrace_official_download",
        "url": b_url,
        "http_status": b_res.status_code,
        "bytes": len(b_bytes),
        "sha256": sha256_bytes(b_bytes),
        "file": b_name,
    }

    limiter = MinInterval(min_interval_sec)
    previous_request_started: float | None = None
    observed_intervals: list[float] = []

    for race_no in range(race_start, race_end + 1):
        slept = limiter.wait()
        request_started = time.monotonic()
        if previous_request_started is not None:
            observed_intervals.append(request_started - previous_request_started)
        previous_request_started = request_started

        url = teikoku_url(target_date, venue, race_no)
        res = fetch(url)
        raw = res.content
        encoding = res.apparent_encoding or res.encoding or "utf-8"
        html = raw.decode(encoding, errors="replace")
        parsed = extract_predeadline_text(html)

        raw_name = f"teikoku_{target_date.strftime('%Y%m%d')}_{venue:02d}_r{race_no:02d}.html"
        txt_name = f"teikoku_{target_date.strftime('%Y%m%d')}_{venue:02d}_r{race_no:02d}_predeadline.txt"
        (output_dir / raw_name).write_bytes(raw)
        (output_dir / txt_name).write_text(
            parsed["predeadline_text"] + "\n",
            encoding="utf-8",
        )

        manifest["races"].append(
            {
                "race_no": race_no,
                "source": "teikoku_databank",
                "url": url,
                "http_status": res.status_code,
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
                "encoding": encoding,
                "deadline_text": parsed["deadline_text"],
                "outcome_prefix_removed": parsed["outcome_prefix_removed"],
                "raw_file": raw_name,
                "predeadline_file": txt_name,
                "sleep_before_request_sec": round(slept, 3),
            }
        )

    if observed_intervals:
        minimum_observed = min(observed_intervals)
        manifest["minimum_observed_teikoku_request_start_interval_sec"] = round(
            minimum_observed, 3
        )
        if minimum_observed < 3.0:
            raise RuntimeError(
                f"艇国 request interval violation: {minimum_observed:.3f}s"
            )

    expected = race_end - race_start + 1
    if len(manifest["races"]) != expected:
        raise RuntimeError("race acquisition count mismatch")

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json.sha256").write_text(
        f"{sha256_bytes(manifest_path.read_bytes())}  manifest.json\n",
        encoding="utf-8",
    )

    print(
        "HIST_PREDEADLINE_PILOT_SUMMARY="
        + json.dumps(
            {
                "date": target_date.isoformat(),
                "venue": f"{venue:02d}",
                "races": len(manifest["races"]),
                "official_b_bytes": len(b_bytes),
                "min_interval_sec": manifest.get(
                    "minimum_observed_teikoku_request_start_interval_sec"
                ),
                "db_write": False,
                "outcome_fields_used": False,
                "prospective_evidence": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    print("HIST_PREDEADLINE_PILOT_RESULT=PASS_RAW_ACQUISITION", flush=True)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--venue", type=int, required=True)
    ap.add_argument("--race-start", type=int, default=1)
    ap.add_argument("--race-end", type=int, default=12)
    ap.add_argument("--output-dir", default="historical-predeadline-pilot")
    ap.add_argument(
        "--min-interval-sec",
        type=float,
        default=DEFAULT_MIN_INTERVAL_SEC,
    )
    args = ap.parse_args()

    target_date = date.fromisoformat(args.date)
    if not 1 <= args.venue <= 24:
        raise SystemExit("venue must be 1..24")
    if not 1 <= args.race_start <= args.race_end <= 12:
        raise SystemExit("race range must be within 1..12")

    run(
        target_date=target_date,
        venue=args.venue,
        race_start=args.race_start,
        race_end=args.race_end,
        output_dir=Path(args.output_dir),
        min_interval_sec=args.min_interval_sec,
    )


if __name__ == "__main__":
    main()
