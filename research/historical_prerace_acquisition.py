# -*- coding: utf-8 -*-
"""Bounded historical pre-race acquisition from public archived sources.

This collector is intentionally artifact-only:
- no PostgreSQL access;
- no Production write;
- no results / payouts / odds;
- maximum 31-day window per run;
- raw bytes preserved with SHA256 manifest.

Source acceptance policy:
- programs/* are treated as pre-race source snapshots for the target date;
- this collector does not infer profitability or modify model inputs;
- raw acquisition is separated from later normalization / DB import.

Primary archive:
  https://boatracecsv.github.io/
which documents these files as pre-race Programs and identifies their upstream
Boatcast sources. Historical Race Cards are documented as available roughly
from 2025-05-02 onward.

Official BOAT RACE and 艇国DB fallback/verification are handled separately.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

BASE = "https://boatracecsv.github.io"
DEFAULT_SOURCES = (
    "title",
    "race_cards",
    "recent_national",
    "recent_local",
    "waku10",
    "motor_stats",
)
USER_AGENT = "boat-ai-v2-historical-prerace-acquisition/1.0"


@dataclass(frozen=True)
class FetchRecord:
    target_date: str
    source: str
    url: str
    status: str
    http_status: int | None
    bytes: int
    data_rows: int | None
    sha256: str | None
    path: str | None
    error: str | None


def iter_dates(start: date, end: date) -> Iterable[date]:
    if end < start:
        raise ValueError("end before start")
    days = (end - start).days + 1
    if days > 31:
        raise ValueError("one acquisition chunk is limited to 31 days")
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def source_url(source: str, d: date) -> str:
    if source not in DEFAULT_SOURCES:
        raise ValueError(f"unsupported source: {source}")
    return f"{BASE}/data/programs/{source}/{d:%Y/%m/%d}.csv"


def _count_rows(raw: bytes) -> int:
    text = raw.decode("utf-8-sig")
    rows = list(csv.reader(text.splitlines()))
    return max(0, len(rows) - 1)


def _looks_like_csv(raw: bytes) -> bool:
    head = raw[:512].lstrip().lower()
    return bool(raw.strip()) and not head.startswith(b"<!doctype html") and not head.startswith(b"<html")


def fetch_one(
    *,
    source: str,
    d: date,
    output_root: Path,
    timeout_s: float,
    retries: int,
) -> FetchRecord:
    url = source_url(source, d)
    last_error: str | None = None

    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                raw = response.read()
                status = int(getattr(response, "status", 200) or 200)
            if status != 200:
                last_error = f"http_{status}"
            elif not _looks_like_csv(raw):
                last_error = "not_csv"
            else:
                try:
                    rows = _count_rows(raw)
                except Exception as exc:
                    last_error = f"csv_decode:{type(exc).__name__}:{exc}"
                else:
                    rel = Path(source) / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.csv"
                    path = output_root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                    sha = hashlib.sha256(raw).hexdigest()
                    return FetchRecord(
                        target_date=d.isoformat(),
                        source=source,
                        url=url,
                        status="OK",
                        http_status=status,
                        bytes=len(raw),
                        data_rows=rows,
                        sha256=sha,
                        path=str(rel),
                        error=None,
                    )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return FetchRecord(
                    target_date=d.isoformat(),
                    source=source,
                    url=url,
                    status="MISSING_404",
                    http_status=404,
                    bytes=0,
                    data_rows=None,
                    sha256=None,
                    path=None,
                    error=None,
                )
            last_error = f"http_{exc.code}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{exc}"

        if attempt < retries:
            time.sleep(1.0)

    return FetchRecord(
        target_date=d.isoformat(),
        source=source,
        url=url,
        status="ERROR",
        http_status=None,
        bytes=0,
        data_rows=None,
        sha256=None,
        path=None,
        error=last_error,
    )


def build_summary(records: list[FetchRecord]) -> dict:
    by_source: dict[str, dict[str, int]] = {}
    for rec in records:
        stats = by_source.setdefault(
            rec.source,
            {"requested_days": 0, "ok_days": 0, "missing_days": 0, "error_days": 0, "data_rows": 0, "bytes": 0},
        )
        stats["requested_days"] += 1
        if rec.status == "OK":
            stats["ok_days"] += 1
            stats["data_rows"] += int(rec.data_rows or 0)
            stats["bytes"] += rec.bytes
        elif rec.status == "MISSING_404":
            stats["missing_days"] += 1
        else:
            stats["error_days"] += 1

    for stats in by_source.values():
        n = max(1, stats["requested_days"])
        stats["coverage_pct"] = round(100.0 * stats["ok_days"] / n, 2)

    return {
        "by_source": by_source,
        "total_requests": len(records),
        "ok_requests": sum(r.status == "OK" for r in records),
        "missing_requests": sum(r.status == "MISSING_404" for r in records),
        "error_requests": sum(r.status == "ERROR" for r in records),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument("--output-dir", default="historical-prerace-raw")
    ap.add_argument("--sources", default=",".join(DEFAULT_SOURCES))
    ap.add_argument("--timeout-s", type=float, default=20.0)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--request-interval-s", type=float, default=0.20)
    args = ap.parse_args()

    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    dates = list(iter_dates(start, end))
    sources = tuple(x.strip() for x in args.sources.split(",") if x.strip())
    unknown = sorted(set(sources) - set(DEFAULT_SOURCES))
    if unknown:
        raise SystemExit(f"unsupported sources: {unknown}")

    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    records: list[FetchRecord] = []

    for d in dates:
        for source in sources:
            rec = fetch_one(
                source=source,
                d=d,
                output_root=root,
                timeout_s=args.timeout_s,
                retries=args.retries,
            )
            records.append(rec)
            print(
                f"HIST_PRERACE_FETCH date={rec.target_date} source={rec.source} "
                f"status={rec.status} rows={rec.data_rows or 0} bytes={rec.bytes}",
                flush=True,
            )
            time.sleep(max(0.0, args.request_interval_s))

    manifest = {
        "contract": "HISTORICAL_PRERACE_RAW_ACQUISITION_V1",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "sources": list(sources),
        "source_class": "pre_race_archive",
        "deadline_policy": "source_must_represent_information_available_before_target_race_deadline",
        "raw_only": True,
        "normalized": False,
        "db_write": False,
        "production_change": False,
        "result_read": False,
        "payout_read": False,
        "odds_read": False,
        "purchase_action": False,
        "records": [asdict(r) for r in records],
        "summary": build_summary(records),
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (root / "manifest.sha256").write_text(
        f"{manifest_sha}  manifest.json\n", encoding="utf-8"
    )

    print("HIST_PRERACE_SUMMARY=" + json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True), flush=True)
    print(f"HIST_PRERACE_MANIFEST_SHA256={manifest_sha}", flush=True)
    print("HIST_PRERACE_RESULT=PASS_RAW_ARTIFACT_ONLY", flush=True)


if __name__ == "__main__":
    main()
