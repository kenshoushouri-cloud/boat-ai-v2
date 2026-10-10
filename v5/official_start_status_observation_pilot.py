# -*- coding: utf-8 -*-
"""V5 mainline: bounded official source observation harness, OFF by default.

READ-ONLY HTTPS GET of exactly one racelist and one beforeinfo per 1-2
explicit race IDs, using an injected requests-compatible session. No retries,
database, file writes, logging, collector, LINE, predictions, stakes, or BUY.
Never persist or return raw HTML, names, racer IDs, or decoded payload.
No CI job in this project ever calls real official sites with this harness.

All source "positive start" labels are UNVERIFIED CANDIDATES, not evidence
of six confirmed starters. A valid sha256/time stamp does not prove that a
source was first seen or that official publishing/decision cutoff occurred.
"""
from __future__ import annotations

import base64
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from historical_beforeinfo_parser_v3 import inspect_exhibition_time_page
from v5.official_http_receipt import _aware_dt, UnverifiedCapture
from v5.official_http_transport import capture_v5_official_response

JST = ZoneInfo("Asia/Tokyo")
BASE = "https://www.boatrace.jp/owpc/pc/race/"
RACE_PATTERN = re.compile(
    r"^(20\d{6})_(0[1-9]|1[0-9]|2[0-4])_(0[1-9]|1[0-2])$"
)
SOURCE_ORDER = ("official_racelist", "official_beforeinfo")
# These are merely search cues. Never auto-interpret text as positive proof.
CANDIDATE_LABELS = ("出走確定", "出走状況", "出走予定", "欠場")
MAX_RACES = 2
MAX_TOTAL_GETS = 2 * MAX_RACES
TIMEOUT_SECONDS = 12.0


class ObservationNotApproved(ValueError):
    """Unapproved/invalid observation; no HTTP should be attempted."""


def bounded_observation_spec(race_ids: Any) -> tuple[tuple[str, str, str], ...]:
    """Validate one/two actual-calendar race IDs and build fixed HTTPS URLs.

    Each item: (race_id, source_kind, exact_official_url).
    Only the official `racelist` and `beforeinfo` endpoints are in scope.
    """
    if (not isinstance(race_ids, (list, tuple))
            or not 1 <= len(race_ids) <= MAX_RACES
            or any(not isinstance(r, str) for r in race_ids)
            or len(set(race_ids)) != len(race_ids)):
        raise ObservationNotApproved("ONE_OR_TWO_DISTINCT_RACES_REQUIRED")
    dates = set()
    targets = []
    for race_id in race_ids:
        match = RACE_PATTERN.fullmatch(race_id)
        if match is None:
            raise ObservationNotApproved("INVALID_RACE_ID")
        date, venue, number = match.groups()
        try:
            datetime.strptime(date, "%Y%m%d")
        except ValueError as exc:
            raise ObservationNotApproved("INVALID_CALENDAR_DATE") from exc
        dates.add(date)
        for kind in SOURCE_ORDER:
            endpoint = kind.removeprefix("official_")
            url = f"{BASE}{endpoint}?rno={int(number)}&jcd={venue}&hd={date}"
            targets.append((race_id, kind, url))
    if len(dates) != 1:
        raise ObservationNotApproved("ONLY_ONE_RACE_DAY_PER_PILOT")
    return tuple(targets)


def _labels_only(source: str, raw: bytes) -> dict[str, Any]:
    """Extract only anonymous aggregate hints; no source text in output."""
    try:
        html = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        return {"html_parse": "UNKNOWN_CHARSET", "potential_status_labels": {},
                "structured_exhibition_complete": False}
    soup = BeautifulSoup(html, "html.parser")
    labels = [
        unicodedata.normalize("NFKC", tag.get_text(" ", strip=True))
        for tag in soup.find_all(("th", "dt"))
    ]
    counts = {key: sum(key in label for label in labels) for key in CANDIDATE_LABELS}
    # Occurrence of an unknown UI label cannot be used to approve active starts.
    complete = False
    if source == "official_beforeinfo":
        parsed = inspect_exhibition_time_page(html)
        complete = (
            parsed.get("status") == "complete"
            and parsed.get("source") == "primary_structured_rows"
            and parsed.get("valid_time_count") == 6
        )
    return {
        "html_parse": "LABEL_COUNTS_ONLY",
        "potential_status_labels": counts,
        "structured_exhibition_complete": complete,
    }


def run_bounded_official_observation(
    *,
    race_ids: Any,
    session: Any,
    external_get_approved: bool = False,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Explicitly opted-in probe with a STRICT maximum of 4 HTTP GETs.

    Inject a fake session for offline CI. A future separate live pilot requires
    a reviewed manual invocation with exact race IDs on their own day; there
    is NO scheduled job, environment switch, CLI, or implicit network call.
    """
    if external_get_approved is not True:
        raise ObservationNotApproved("OFF_BY_DEFAULT_MANUAL_SCOPE_REQUIRED")
    spec = bounded_observation_spec(race_ids)
    if session is None or not callable(getattr(session, "get", None)):
        raise ObservationNotApproved("EXPLICIT_HTTP_SESSION_REQUIRED")
    now = clock or (lambda: datetime.now(timezone.utc))
    try:
        first_observed = _aware_dt(now())
    except (UnverifiedCapture, ValueError, TypeError) as exc:
        raise ObservationNotApproved("UNVERIFIED_OBSERVATION_CLOCK") from exc
    if first_observed.astimezone(JST).strftime("%Y%m%d") != race_ids[0][:8]:
        raise ObservationNotApproved("RACE_DAY_MUST_EQUAL_JST_OBSERVATION_DAY")

    # No cross-day observation, no retries. Results NEVER include body, base64,
    # racer identity, query URL with names, or request/client credentials.
    reports: list[dict[str, Any]] = []
    attempted = 0
    for race_id, source, url in spec:
        try:
            attempted += 1
            obtained = capture_v5_official_response(
                session=session,
                requested_url=url,
                expected_source=source,
                expected_race_id=race_id,
                clock=now,
                timeout_seconds=TIMEOUT_SECONDS,
            )
            receipt = obtained["receipt_proposal"]
            raw = base64.b64decode(receipt["raw_base64"], validate=True)
            if receipt.get("source") != source:
                raise UnverifiedCapture("SOURCE_MISMATCH")
            reports.append({
                "race_id": race_id,
                "source": source,
                "status": "OBSERVED_CONTENT_NOT_AUTHENTICATED",
                "raw_sha256": receipt["raw_sha256"],
                "raw_size_bytes": receipt["raw_size_bytes"],
                "response_completed_at": receipt["response_completed_at"],
                "hints": _labels_only(source, raw),
                "all_six_active_confirmed": False,
                "first_observed_at": None,
                "forward_eligible": False,
            })
        except (UnverifiedCapture, KeyError, ValueError) as exc:
            # Error classes generated by V5 only; never expose remote response
            # body, redirect URL, exception chain, tokens or personal details.
            return {
                "status": "INCOMPLETE_STOPPED",
                "error_code": str(exc) if isinstance(exc, UnverifiedCapture) else "INSPECTION_FAILED",
                "attempted_gets": attempted,
                "max_gets": MAX_TOTAL_GETS,
                "observations": reports,
                "all_six_active_confirmed": False,
                "persistence_performed": False,
                "forward_eligible": False,
            }
    return {
        "status": "READ_ONLY_DISCOVERY_COMPLETE_NOT_VERIFIED",
        "attempted_gets": attempted,
        "max_gets": MAX_TOTAL_GETS,
        "observations": reports,
        "all_six_active_confirmed": False,
        "persistence_performed": False,
        "forward_eligible": False,
        "limitations": (
            "HTTP bytes/hash/time are local observations, not authenticated "
            "first observation or independent official positive six-starter "
            "proof. Header label hints are never a vote or authorization."
        ),
    }
