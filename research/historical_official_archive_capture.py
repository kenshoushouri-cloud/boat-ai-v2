# -*- coding: utf-8 -*-
"""Capture BOAT RACE official historical B/K raw archives with SHA manifests.

B = program/race-card archive (pre-race source)
K = result archive (outcome/settlement source only)

This script does not parse, score, select, notify, buy, or write PostgreSQL.
It is an immutable raw-source acquisition step for later audited parsing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JST = timezone(timedelta(hours=9))
DEFAULT_START = "2025-07-01"
DEFAULT_END = "2026-09-29"
BASE = "https://www1.mbrace.or.jp/od2"
USER_AGENT = "boat-ai-v2-historical-archive-capture/1.0"
MIN_BYTES = 32


def iter_days(start: str, end: str) -> Iterable[date]:
    a = date.fromisoformat(start)
    b = date.fromisoformat(end)
    if b < a:
        raise ValueError("end date must be >= start date")
    cur = a
    while cur <= b:
        yield cur
        cur += timedelta(days=1)


def archive_url(kind: str, day: date) -> str:
    kind = kind.upper()
    if kind not in {"B", "K"}:
        raise ValueError("kind must be B or K")
    return (
        f"{BASE}/{kind}/{day:%Y%m}/"
        f"{kind.lower()}{day:%y%m%d}.lzh"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_one(url: str, timeout: int) -> tuple[str, bytes | None, str | None]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            data = resp.read()
        if status != 200:
            return f"http_{status}", None, None
        if len(data) < MIN_BYTES:
            return "too_small", data, None
        return "ok", data, sha256_bytes(data)
    except HTTPError as exc:
        if exc.code == 404:
            return "not_found", None, None
        return f"http_{exc.code}", None, None
    except URLError as exc:
        return "url_error", None, repr(exc)
    except Exception as exc:
        return "error", None, repr(exc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=os.getenv("HIST_START_DATE", DEFAULT_START))
    ap.add_argument("--end-date", default=os.getenv("HIST_END_DATE", DEFAULT_END))
    ap.add_argument("--out-dir", default=os.getenv("HIST_OUT_DIR", "historical-official-raw"))
    ap.add_argument("--sleep-sec", type=float, default=float(os.getenv("HIST_SLEEP_SEC", "0.20")))
    ap.add_argument("--timeout", type=int, default=int(os.getenv("HIST_HTTP_TIMEOUT", "30")))
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    counts: dict[str, int] = {}

    print("HIST_OFFICIAL_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)
    print(f"HIST_OFFICIAL_PERIOD={args.start_date}..{args.end_date}", flush=True)

    for day in iter_days(args.start_date, args.end_date):
        for kind in ("B", "K"):
            url = archive_url(kind, day)
            status, data, detail = fetch_one(url, args.timeout)
            counts[status] = counts.get(status, 0) + 1
            row = {
                "date": day.isoformat(),
                "kind": kind,
                "role": "predeadline_program" if kind == "B" else "outcome_only",
                "url": url,
                "status": status,
                "fetched_at_jst": datetime.now(JST).isoformat(),
                "bytes": len(data) if data is not None else 0,
                "sha256": sha256_bytes(data) if data else None,
                "detail": detail,
            }
            if status == "ok" and data is not None:
                d = out / kind / f"{day:%Y%m}"
                d.mkdir(parents=True, exist_ok=True)
                p = d / f"{kind.lower()}{day:%y%m%d}.lzh"
                tmp = p.with_suffix(p.suffix + ".tmp")
                tmp.write_bytes(data)
                tmp.replace(p)
                row["path"] = str(p.relative_to(out))
            manifest.append(row)
            if args.sleep_sec > 0:
                time.sleep(args.sleep_sec)

    payload = {
        "contract": "BOATRACE_OFFICIAL_HISTORICAL_RAW_CAPTURE_V1",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "source": "BOAT_RACE_OFFICIAL_MBRACE_DOWNLOAD",
        "b_role": "historical_predeadline_input_source",
        "k_role": "outcome_settlement_only_never_model_input",
        "db_write": False,
        "line": False,
        "buy": False,
        "production_change": False,
        "counts": dict(sorted(counts.items())),
        "files": manifest,
    }
    (out / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "manifest.sha256").write_text(
        f"{sha256_bytes((out / 'manifest.json').read_bytes())}  manifest.json\n",
        encoding="utf-8",
    )
    print("HIST_OFFICIAL_COUNTS=" + json.dumps(payload["counts"], sort_keys=True), flush=True)
    print("HIST_OFFICIAL_RESULT=PASS_RAW_CAPTURE", flush=True)


if __name__ == "__main__":
    main()
