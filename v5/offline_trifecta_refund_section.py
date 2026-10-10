"""V5 offline text-section refund/ticket shape audit; not official provenance.

BOAT RACE result pages visibly contain a '返還' section. Only its explicitly
listed boat numbers may be mapped to selected trifecta tickets. F/L flags
alone, postrace notes, guessed HTML layouts, and any absence of a section
never prove ticket-level refunds. No network/DB/BUY/Forward/real ROI.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

JST = ZoneInfo('Asia/Tokyo')
RACE_RE = re.compile(r'(20\d{6})_(0[1-9]|1\d|2[0-4])_(0[1-9]|1[0-2])\Z')
SHA_RE = re.compile(r'[a-f0-9]{64}\Z')
TICKET_RE = re.compile(r'[1-6]-[1-6]-[1-6]\Z')
MAX_HTML_BYTES = 2_097_152


@dataclass(frozen=True, slots=True)
class FrozenResultSection:
    source_url: str
    raw_bytes: bytes
    raw_sha256: str
    decision_cutoff_at: datetime
    response_completed_at: datetime
    purported_first_write: bool = False
    purported_officially_authenticated: bool = False


@dataclass(frozen=True, slots=True)
class HypotheticalTicket:
    ticket: str
    stake_yen: int


@dataclass(frozen=True, slots=True)
class RefundSectionVerdict:
    reason: str
    race_id: str = ''
    section_shape_consistent: bool = False
    mock_refund_boats: tuple[int, ...] = ()
    mock_refunded_tickets: tuple[str, ...] = ()
    mock_refund_yen: int = 0
    official_result_authenticated: bool = field(default=False, init=False)
    ticket_refunds_officially_verified: bool = field(default=False, init=False)
    original_first_write_verified: bool = field(default=False, init=False)
    roi_eligible: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)
    no_network_sql_write: bool = field(default=True, init=False)


def _aware(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _valid_url(value: object, race_id: str) -> bool:
    if type(value) is not str:
        return False
    try:
        u = urlsplit(value)
        if (u.scheme != 'https' or u.netloc != 'www.boatrace.jp'
                or u.path != '/owpc/pc/race/raceresult' or u.fragment):
            return False
        pairs = parse_qsl(u.query, keep_blank_values=True, strict_parsing=True)
        if len(pairs) != 3 or {k for k, _ in pairs} != {'hd', 'jcd', 'rno'}:
            return False
        q = dict(pairs)
        return (q['hd'] == race_id[:8] and q['jcd'] == race_id[9:11]
                and re.fullmatch(r'[1-9]|1[0-2]', q['rno']) is not None
                and int(q['rno']) == int(race_id[-2:]))
    except (ValueError, TypeError):
        return False


def inspect_offline_refund_section(*, race_id: object, result: object,
                                   hypothetical_tickets: object,
                                   enabled: bool = False) -> RefundSectionVerdict:
    """Parse explicit result HTML refund subsection; map mock tickets only.

    Does not infer refunds from start status. No actual source fixture/HTML
    schema or independently authenticated first HTTP observation is supplied.
    """
    def hold(code: str) -> RefundSectionVerdict:
        return RefundSectionVerdict(code)

    if enabled is not True:
        return hold('REFUND_SECTION_DISABLED')
    if type(result) is not FrozenResultSection:
        return hold('RESULT_SOURCE_REQUIRED')
    if (type(race_id) is not str or RACE_RE.fullmatch(race_id) is None
            or not _aware(result.decision_cutoff_at)
            or not _aware(result.response_completed_at)):
        return hold('RACE_OR_CLOCK_INVALID')
    try:
        day = datetime.strptime(race_id[:8], '%Y%m%d').date()
    except ValueError:
        return hold('RACE_OR_CLOCK_INVALID')
    if (day < date(2025, 7, 1)
            or result.decision_cutoff_at.astimezone(JST).date() != day
            or not result.decision_cutoff_at < result.response_completed_at):
        return hold('RESULT_NOT_AFTER_DECISION')
    if (result.purported_first_write is not False
            or result.purported_officially_authenticated is not False):
        return hold('UNTRUSTED_AUTHORITY_CLAIM')
    if not _valid_url(result.source_url, race_id):
        return hold('RESULT_URL_RACE_MISMATCH')
    raw = result.raw_bytes
    if (type(raw) is not bytes or not 0 < len(raw) <= MAX_HTML_BYTES
            or type(result.raw_sha256) is not str or SHA_RE.fullmatch(result.raw_sha256) is None
            or hashlib.sha256(raw).hexdigest() != result.raw_sha256):
        return hold('RESULT_BYTES_SHA_MISMATCH')
    if (type(hypothetical_tickets) is not tuple or not 1 <= len(hypothetical_tickets) <= 120
            or any(type(x) is not HypotheticalTicket for x in hypothetical_tickets)):
        return hold('MOCK_TICKET_SET_REQUIRED')
    seen = set()
    for x in hypothetical_tickets:
        if (type(x.ticket) is not str or TICKET_RE.fullmatch(x.ticket) is None
                or len(set(x.ticket.split('-'))) != 3 or x.ticket in seen
                or type(x.stake_yen) is not int or x.stake_yen < 100
                or x.stake_yen % 100 != 0):
            return hold('MOCK_TICKETS_OR_STAKES_INVALID')
        seen.add(x.ticket)
    try:
        html = raw.decode('utf-8', errors='strict')
        lines = [unicodedata.normalize('NFKC', s).strip()
                 for s in BeautifulSoup(html, 'html.parser').get_text('\n', strip=True).splitlines()]
        lines = [x for x in lines if x]
    except (UnicodeError, TypeError, ValueError):
        return hold('RESULT_ENCODING_INVALID')
    # Refuse full-race invalidation. Distinct official race status parsing is
    # required to handle 3連単不成立, cancellation, and all-ticket refund.
    text = ' '.join(lines)
    if any(marker in text for marker in ('レース中止', '開催中止', '3連単不成立', '3 連単 不成立')):
        return hold('FULL_RACE_OR_TRIFECTA_INVALID_UNRESOLVED')
    headings = [i for i, x in enumerate(lines) if x == '返還']
    ends = [i for i, x in enumerate(lines) if x == '決まり手']
    if len(headings) != 1 or len(ends) != 1 or not headings[0] < ends[0]:
        return hold('EXPLICIT_REFUND_SECTION_NOT_ISOLATED')
    section = lines[headings[0]+1:ends[0]]
    if len(section) > 6:
        return hold('REFUND_SECTION_AMBIGUOUS')
    boats = []
    for line in section:
        if re.fullmatch(r'[1-6](?:\s+[1-6])*', line) is None:
            return hold('REFUND_SECTION_AMBIGUOUS')
        boats.extend(int(t) for t in line.split())
    if len(boats) > 6 or len(set(boats)) != len(boats):
        return hold('REFUND_SECTION_AMBIGUOUS')
    ordered = tuple(sorted(boats))
    refunded = tuple(x.ticket for x in hypothetical_tickets
                     if any(int(n) in ordered for n in x.ticket.split('-')))
    money = sum(x.stake_yen for x in hypothetical_tickets if x.ticket in refunded)
    return RefundSectionVerdict('MOCK_EXPLICIT_REFUND_BOATS_PARSED_SOURCE_UNVERIFIED_HARD_HOLD',
                                race_id, True, ordered, refunded, money)
