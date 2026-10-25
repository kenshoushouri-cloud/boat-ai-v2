# -*- coding: utf-8 -*-
"""Policy-constrained raw capture for historical 艇国データバンク race pages.

Rules enforced here:
- only boatrace-db.net HTML pages explicitly listed by caller;
- one sequential process, no concurrency;
- >=3 seconds between requests;
- no CSS/JS/image/favicon requests;
- raw HTML + SHA/provenance only;
- no result parsing, model use, LINE, purchase, or PostgreSQL write.

Later parsers must extract only preregistered pre-race sections.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

JST = timezone(timedelta(hours=9))
MIN_INTERVAL_SEC = 3.0
USER_AGENT = "boat-ai-v2-teikoku-history-research/1.0"
ALLOWED_HOSTS = {"boatrace-db.net", "www.boatrace-db.net"}
RACE_DETAIL = re.compile(
    r"^/race/detail/date/(?P<date>\d{8})/pid/(?P<pid>\d{1,2})/rno/(?P<rno>\d{1,2})/?$"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_url(url: str) -> dict[str, str]:
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
        raise ValueError("艇国 URL must use https://boatrace-db.net")
    m = RACE_DETAIL.match(p.path)
    if not m:
        raise ValueError("only historical /race/detail/date/... pages are allowed")
    return m.groupdict()


def fetch(url: str, timeout: int) -> bytes:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja,en;q=0.5",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200) or 200)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        return resp.read()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-file", required=True)
    ap.add_argument("--out-dir", default="historical-teikoku-raw")
    ap.add_argument(
        "--interval-sec",
        type=float,
        default=float(os.getenv("TEIKOKU_INTERVAL_SEC", "3.2")),
    )
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()
    if args.interval_sec < MIN_INTERVAL_SEC:
        raise SystemExit("艇国DB rule requires interval >= 3.0 seconds")

    urls = [
        line.strip()
        for line in Path(args.url_file).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(urls) != len(set(urls)):
        raise SystemExit("duplicate URLs are forbidden")
    if not urls:
        raise SystemExit("no URLs")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    print("TEIKOKU_CONCURRENCY=1 MIN_INTERVAL_SEC=3.0", flush=True)
    print("TEIKOKU_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 RESULT_PARSE=0", flush=True)

    last_started = 0.0
    for index, url in enumerate(urls, start=1):
        meta = validate_url(url)
        elapsed = time.monotonic() - last_started
        if last_started and elapsed < args.interval_sec:
            time.sleep(args.interval_sec - elapsed)
        last_started = time.monotonic()

        status = "ok"
        detail = None
        data = b""
        try:
            data = fetch(url, args.timeout)
        except Exception as exc:
            status = "error"
            detail = repr(exc)

        name = f"{meta['date']}_{int(meta['pid']):02d}_{int(meta['rno']):02d}.html"
        if status == "ok":
            (out / name).write_bytes(data)
        rows.append(
            {
                "url": url,
                "date": meta["date"],
                "venue_id": f"{int(meta['pid']):02d}",
                "race_no": int(meta["rno"]),
                "status": status,
                "bytes": len(data),
                "sha256": sha256_bytes(data) if data else None,
                "fetched_at_jst": datetime.now(JST).isoformat(),
                "file": name if status == "ok" else None,
                "detail": detail,
                "admissibility": "raw_only_pending_prerace_section_parse",
            }
        )
        print(f"TEIKOKU_PROGRESS={index}/{len(urls)} status={status} url={url}", flush=True)

    manifest = {
        "contract": "TEIKOKU_HISTORICAL_RAW_CAPTURE_V1",
        "source": "艇国データバンク",
        "single_process": True,
        "minimum_interval_sec": args.interval_sec,
        "assets_requested": False,
        "result_parse": False,
        "db_write": False,
        "line": False,
        "buy": False,
        "production_change": False,
        "pages": rows,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("TEIKOKU_RESULT=PASS_RAW_CAPTURE", flush=True)


if __name__ == "__main__":
    main()
