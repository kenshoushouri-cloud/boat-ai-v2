# -*- coding: utf-8 -*-
"""V5 offline HTML byte-bound six-lane inspection, never an actual-start proof.

Uses existing official-style racelist and beforeinfo parsers, which do not
independently bind six beforeinfo racer registration numbers. No GET/SQL/BUY.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, date

from bs4 import BeautifulSoup
from historical_beforeinfo_parser_v3 import inspect_exhibition_time_page, EXHIBITION_STATUS_COMPLETE, _direct_cells, _lane_from_cells
from v5.official_racelist_readback import _extract_six_entrant_candidates, RacelistNotVerified, CANCEL_MARKERS, _norm
from v5.offline_paper_roster_gate import MockFrozenPage, _url_matches, _aware, JST, RACE_RE, SHA_RE

MAX_HTML_BYTES = 2_097_152


@dataclass(frozen=True, slots=True)
class OfflineHtmlRosterVerdict:
    reason: str
    race_id: str = ''
    matched_exhibition_lanes: int = 0
    racelist_six_unique_racers: bool = False
    lane_only_paper_observation: bool = False
    beforeinfo_racer_numbers_bound: bool = field(default=False, init=False)
    paper_shadow_shape_eligible: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    independently_authenticated_source: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)
    no_get_sql_write: bool = field(default=True, init=False)


def inspect_offline_html_roster(*, expected_race_id: object,
                                decision_cutoff_at: object, racelist: object,
                                beforeinfo: object, enabled: bool = False
                                ) -> OfflineHtmlRosterVerdict:
    """Parse caller-owned HTML bytes only, report six-lane observation, HOLD.

    A lane appearing on both pages does NOT independently match a racer number:
    the existing beforeinfo parser does not return one per lane.  Thus a
    successful inspection is not eligible even for the strict JSON paper gate.
    """
    def deny(code: str) -> OfflineHtmlRosterVerdict:
        return OfflineHtmlRosterVerdict(code)

    if enabled is not True:
        return deny('HTML_OFFLINE_OPT_IN_REQUIRED')
    if (type(expected_race_id) is not str or RACE_RE.fullmatch(expected_race_id) is None
            or not _aware(decision_cutoff_at)):
        return deny('HTML_RACE_OR_CUTOFF_INVALID')
    try:
        day = datetime.strptime(expected_race_id[:8], '%Y%m%d').date()
    except ValueError:
        return deny('HTML_RACE_OR_CUTOFF_INVALID')
    if day < date(2025, 7, 1) or decision_cutoff_at.astimezone(JST).date() != day:
        return deny('HTML_RACE_OR_CUTOFF_INVALID')
    if type(racelist) is not MockFrozenPage or type(beforeinfo) is not MockFrozenPage:
        return deny('HTML_SOURCE_PAGES_REQUIRED')
    for page, source in ((racelist, 'racelist'), (beforeinfo, 'beforeinfo')):
        if (page.kind != source or page.requested_url != page.final_url
                or not _url_matches(page.requested_url, source, expected_race_id)):
            return deny('HTML_URL_IDENTITY_INVALID')
        if (page.first_observed_at is not None or page.first_write_confirmed is not False
                or page.actual_source_authenticated is not False
                or page.mutable_or_upsert_only is not False or page.postrace_derived is not False):
            return deny('HTML_FORGED_AUTHORITY_OR_MUTABLE_SOURCE')
        if (type(page.raw_bytes) is not bytes
                or not 0 < len(page.raw_bytes) <= MAX_HTML_BYTES
                or type(page.raw_sha256) is not str or SHA_RE.fullmatch(page.raw_sha256) is None
                or hashlib.sha256(page.raw_bytes).hexdigest() != page.raw_sha256):
            return deny('HTML_BYTES_DIGEST_INVALID')
        if (not _aware(page.response_completed_at) or not _aware(page.frozen_at)
                or not page.response_completed_at <= page.frozen_at < decision_cutoff_at
                or page.response_completed_at.astimezone(JST).date() != day):
            return deny('HTML_NOT_FROZEN_BEFORE_CUTOFF')
    if (racelist.response_completed_at > beforeinfo.response_completed_at
            or (beforeinfo.response_completed_at - racelist.response_completed_at).total_seconds() > 86400):
        return deny('HTML_SOURCE_CLOCK_ORDER_INVALID')
    try:
        entrants = _extract_six_entrant_candidates(racelist.raw_bytes)
    except (RacelistNotVerified, ValueError, TypeError):
        return deny('HTML_RACELIST_SIX_RACER_PARSE_FAILED')
    if (type(entrants) is not list or len(entrants) != 6
            or sorted(x['lane'] for x in entrants) != list(range(1, 7))
            or len({x['racer_number'] for x in entrants}) != 6
            or any(x.get('active_verified') is not False for x in entrants)):
        return deny('HTML_RACELIST_CANDIDATE_INVALID')
    try:
        html = beforeinfo.raw_bytes.decode('utf-8', errors='strict')
        soup = BeautifulSoup(html, 'html.parser')
        lanes = []
        for tbody in soup.select('tbody.is-fs12'):
            trs = tbody.find_all('tr', recursive=False)
            if not trs:
                continue
            lane = _lane_from_cells(_direct_cells(trs[0]))
            if lane is None:
                continue
            if any(token in _norm(tbody.get_text(' ', strip=True)) for token in CANCEL_MARKERS):
                return deny('HTML_BEFOREINFO_WITHDRAWAL_DISPLAYED')
            lanes.append(lane)
        if len(lanes) != 6 or sorted(lanes) != list(range(1, 7)):
            return deny('HTML_BEFOREINFO_STRUCTURED_SIX_LANES_UNVERIFIED')
        exhibition = inspect_exhibition_time_page(html)
    except (UnicodeError, ValueError, TypeError, KeyError):
        return deny('HTML_BEFOREINFO_PARSE_FAILED')
    if (exhibition.get('status') != EXHIBITION_STATUS_COMPLETE
            or exhibition.get('source') != 'primary_structured_rows'
            or exhibition.get('valid_time_count') != 6
            or exhibition.get('lanes') != list(range(1, 7))):
        return deny('HTML_BEFOREINFO_EXHIBITION_INCOMPLETE_OR_FALLBACK')
    # No beforeinfo racer_number evidence in the imported parser contract.
    return OfflineHtmlRosterVerdict('HTML_SIX_LANES_OBSERVED_RACER_BINDING_MISSING_HARD_HOLD',
                                     expected_race_id, 6, True, True)
