# -*- coding: utf-8 -*-
"""Research-only pre-freeze BOAT RACE availability raw capture contract.

The capture layer intentionally runs before Candidate Discovery V4 freezes its
formal core. It receives the already-known same-day venue universe and a
fail-closed hard stop derived from the earliest scheduled race deadline, then
preserves only official availability surfaces:

- same-day venue index
- per-venue race index

It never reads result/payout endpoints, PostgreSQL, Railway, LINE, or purchase
surfaces. Production wiring is deliberately absent from this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

REQUEST_CONTRACT = "candidate_discovery_v4_pre_freeze_availability_capture_request_v1"
PLAN_CONTRACT = "candidate_discovery_v4_pre_freeze_availability_capture_plan_v1"
MANIFEST_CONTRACT = "candidate_discovery_v4_pre_freeze_availability_raw_manifest_v1"

JST = timezone(timedelta(hours=9))
SOURCE_CUTOFF = time(8, 15)
MAX_SOURCE_BYTES = 5_000_000
VENUE_IDS = {f"{idx:02d}" for idx in range(1, 25)}
HARD_STOP_BASIS = "earliest_scheduled_race_deadline"
BASE = "https://www.boatrace.jp/owpc/pc/race"


class V4PreFreezeAvailabilityCaptureError(ValueError):
    pass


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise V4PreFreezeAvailabilityCaptureError(
            f"{field} must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise V4PreFreezeAvailabilityCaptureError(
            f"{field} is not valid ISO datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V4PreFreezeAvailabilityCaptureError(
            f"{field} must be timezone-aware"
        )
    return parsed.astimezone(JST)


def _parse_request(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise V4PreFreezeAvailabilityCaptureError("capture request must be an object")
    if data.get("contract") != REQUEST_CONTRACT:
        raise V4PreFreezeAvailabilityCaptureError("unexpected capture request contract")

    target_raw = data.get("target_date")
    if not isinstance(target_raw, str):
        raise V4PreFreezeAvailabilityCaptureError("target_date missing")
    try:
        target_day = date.fromisoformat(target_raw)
    except ValueError as exc:
        raise V4PreFreezeAvailabilityCaptureError(
            "target_date must be a valid ISO date"
        ) from exc

    venues = data.get("venue_ids")
    if not isinstance(venues, list) or not venues:
        raise V4PreFreezeAvailabilityCaptureError("venue_ids must be a non-empty list")
    if any(not isinstance(v, str) or v not in VENUE_IDS for v in venues):
        raise V4PreFreezeAvailabilityCaptureError("venue_ids must be unique official 01..24 IDs")
    if len(set(venues)) != len(venues):
        raise V4PreFreezeAvailabilityCaptureError("venue_ids must be unique")

    if data.get("hard_stop_basis") != HARD_STOP_BASIS:
        raise V4PreFreezeAvailabilityCaptureError(
            "hard_stop_basis must be earliest_scheduled_race_deadline"
        )
    hard_stop = _aware_datetime(data.get("hard_stop_at_jst"), field="hard_stop_at_jst")
    if hard_stop.date() != target_day:
        raise V4PreFreezeAvailabilityCaptureError(
            "hard_stop_at_jst must fall on target_date in JST"
        )

    cutoff = datetime.combine(target_day, SOURCE_CUTOFF, tzinfo=JST)
    if hard_stop <= cutoff:
        raise V4PreFreezeAvailabilityCaptureError(
            "hard stop must be after the 08:15 source cutoff"
        )

    return {
        "target_date": target_day,
        "venue_ids": sorted(venues),
        "source_cutoff_at_jst": cutoff,
        "hard_stop_at_jst": hard_stop,
    }


def build_capture_plan(data: Any) -> dict[str, Any]:
    req = _parse_request(data)
    compact = req["target_date"].strftime("%Y%m%d")
    sources = [
        {
            "source_id": "day-index",
            "source_kind": "venue_day_index",
            "source_url": f"{BASE}/index?hd={compact}",
        }
    ]
    for venue_id in req["venue_ids"]:
        sources.append(
            {
                "source_id": f"venue-{venue_id}-raceindex",
                "source_kind": "venue_race_index",
                "venue_id": venue_id,
                "source_url": f"{BASE}/raceindex?hd={compact}&jcd={venue_id}",
            }
        )

    return {
        "contract": PLAN_CONTRACT,
        "target_date": req["target_date"].isoformat(),
        "venue_ids": req["venue_ids"],
        "source_cutoff_at_jst": req["source_cutoff_at_jst"].isoformat(),
        "hard_stop_at_jst": req["hard_stop_at_jst"].isoformat(),
        "hard_stop_basis": HARD_STOP_BASIS,
        "sources": sources,
        "result_endpoint_reads": 0,
        "payout_endpoint_reads": 0,
        "purchase_action": False,
    }


Fetcher = Callable[[str], tuple[bytes, str]]
Clock = Callable[[], datetime]


def capture_sources(
    request_data: Any,
    *,
    fetcher: Fetcher,
    clock: Clock,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    plan = build_capture_plan(request_data)
    cutoff = _aware_datetime(plan["source_cutoff_at_jst"], field="source_cutoff_at_jst")
    hard_stop = _aware_datetime(plan["hard_stop_at_jst"], field="hard_stop_at_jst")
    target_day = date.fromisoformat(plan["target_date"])

    started = clock()
    if not isinstance(started, datetime) or started.tzinfo is None or started.utcoffset() is None:
        raise V4PreFreezeAvailabilityCaptureError("clock must return aware datetime")
    started = started.astimezone(JST)
    if started.date() != target_day:
        raise V4PreFreezeAvailabilityCaptureError(
            "capture must run on target_date in JST"
        )
    if started < cutoff:
        raise V4PreFreezeAvailabilityCaptureError(
            "capture cannot run before 08:15 source cutoff"
        )
    if started >= hard_stop:
        raise V4PreFreezeAvailabilityCaptureError(
            "capture started at/after earliest scheduled deadline"
        )

    entries: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    for source in plan["sources"]:
        before = clock()
        if not isinstance(before, datetime) or before.tzinfo is None or before.utcoffset() is None:
            raise V4PreFreezeAvailabilityCaptureError("clock must return aware datetime")
        before = before.astimezone(JST)
        if before >= hard_stop:
            raise V4PreFreezeAvailabilityCaptureError(
                f"capture hard stop reached before source: {source['source_id']}"
            )

        raw, final_url = fetcher(source["source_url"])
        if not isinstance(raw, bytes) or not raw:
            raise V4PreFreezeAvailabilityCaptureError(
                f"empty raw payload: {source['source_id']}"
            )
        if len(raw) > MAX_SOURCE_BYTES:
            raise V4PreFreezeAvailabilityCaptureError(
                f"raw payload exceeds size cap: {source['source_id']}"
            )
        if final_url != source["source_url"]:
            raise V4PreFreezeAvailabilityCaptureError(
                f"unexpected redirect/final URL: {source['source_id']}"
            )

        observed = clock()
        if not isinstance(observed, datetime) or observed.tzinfo is None or observed.utcoffset() is None:
            raise V4PreFreezeAvailabilityCaptureError("clock must return aware datetime")
        observed = observed.astimezone(JST)
        if observed >= hard_stop:
            raise V4PreFreezeAvailabilityCaptureError(
                f"source completed at/after earliest scheduled deadline: {source['source_id']}"
            )

        filename = f"{source['source_id']}.html"
        payloads[filename] = raw
        entries.append(
            {
                **source,
                "observed_at": observed.isoformat(),
                "source_content_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_filename": filename,
                "raw_bytes": len(raw),
            }
        )

    completed = clock()
    if not isinstance(completed, datetime) or completed.tzinfo is None or completed.utcoffset() is None:
        raise V4PreFreezeAvailabilityCaptureError("clock must return aware datetime")
    completed = completed.astimezone(JST)
    if completed >= hard_stop:
        raise V4PreFreezeAvailabilityCaptureError(
            "capture completed at/after earliest scheduled deadline"
        )

    manifest = {
        "contract": MANIFEST_CONTRACT,
        "target_date": plan["target_date"],
        "venue_ids": plan["venue_ids"],
        "source_cutoff_at_jst": plan["source_cutoff_at_jst"],
        "hard_stop_at_jst": plan["hard_stop_at_jst"],
        "hard_stop_basis": HARD_STOP_BASIS,
        "capture_started_at_jst": started.isoformat(),
        "capture_completed_at_jst": completed.isoformat(),
        "sources": entries,
        "all_sources_pre_hard_stop": True,
        "result_endpoint_reads": 0,
        "payout_endpoint_reads": 0,
        "purchase_action": False,
        "production_mutation": False,
    }
    return manifest, payloads


def _official_fetch(url: str) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={"User-Agent": "boat-ai-v2-research-availability-capture/1.0"},
        method="GET",
    )
    with urlopen(request, timeout=15) as response:
        raw = response.read(MAX_SOURCE_BYTES + 1)
        return raw, response.geturl()


def capture_to_directory(request_data: Any, output_dir: Path) -> dict[str, Any]:
    manifest, payloads = capture_sources(
        request_data,
        fetcher=_official_fetch,
        clock=lambda: datetime.now(JST),
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    for filename, raw in payloads.items():
        (output_dir / filename).write_bytes(raw)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    request_data = json.loads(Path(args.request).read_text(encoding="utf-8"))
    manifest = capture_to_directory(request_data, Path(args.output_dir))
    print(
        "V4_AVAILABILITY_RAW_CAPTURE="
        + json.dumps(
            {
                "target_date": manifest["target_date"],
                "source_count": len(manifest["sources"]),
                "capture_completed_at_jst": manifest["capture_completed_at_jst"],
                "purchase_action": manifest["purchase_action"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
