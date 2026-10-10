"""V5 offline result-HTML 3-ren-tan ticket/payout byte-parity, ALWAYS HOLD.

Adapted narrowly from repair_month_all_pg.py parse_result. An arbitrary
caller-supplied HTML body/hash is NOT independently authenticated official
result evidence. Refunds, F/L and order-specific returns are NOT parsed.
No HTTP, DB, betting, or production integration.
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
# Same ticket/payout textual grammar as the existing repair_month_all_pg parser;
# select exactly one candidate, never the first of conflicting candidates.
PAYOUT_RE = re.compile(
    r'3\s*連\s*単\s*([1-6])\s*[-－ー]?\s*([1-6])\s*[-－ー]?\s*([1-6])'
    r'\s*[¥￥]?\s*([\d,]+)\s*円?'
)


@dataclass(frozen=True, slots=True)
class ClaimedResultHtml:
    source_url: str
    raw_bytes: bytes
    raw_sha256: str
    response_completed_at: datetime
    cutoff_at: datetime
    claimed_winning_ticket: str
    claimed_trifecta_payout_yen: int
    redirected: bool = False
    claimed_official_authenticated: bool = False
    claimed_first_write_verified: bool = False


@dataclass(frozen=True, slots=True)
class ResultHtmlParity:
    reason: str
    race_id: str = ''
    content_ticket_payout_parity: bool = False
    parsed_ticket: str = ''
    parsed_payout_yen: int = 0
    refund_ticket_details_verified: bool = field(default=False, init=False)
    official_source_authenticated: bool = field(default=False, init=False)
    original_first_write_verified: bool = field(default=False, init=False)
    economic_roi_eligible: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)
    no_get_sql_write: bool = field(default=True, init=False)


def _aware(v: object) -> bool:
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def _url_matches(url: object, race_id: str) -> bool:
    if type(url) is not str:
        return False
    try:
        u = urlsplit(url)
        if (u.scheme != 'https' or u.netloc != 'www.boatrace.jp'
                or u.path != '/owpc/pc/race/raceresult' or u.fragment):
            return False
        pairs = parse_qsl(u.query, keep_blank_values=True, strict_parsing=True)
        if len(pairs) != 3 or {key for key, _ in pairs} != {'rno', 'jcd', 'hd'}:
            return False
        q = dict(pairs)
        return (q['hd'] == race_id[:8] and q['jcd'] == race_id[9:11]
                and re.fullmatch(r'[1-9]|1[0-2]', q['rno']) is not None
                and int(q['rno']) == int(race_id[-2:]))
    except (TypeError, ValueError):
        return False


def compare_result_html_payout(*, expected_race_id: object,
                               capture: object, enabled: bool = False) -> ResultHtmlParity:
    """Claimed payout must appear exactly once in bound synthetic result HTML.

    A positive result is mock content parity only; a normal official race can
    STILL contain F/L refunds, not determined here. Never compute real ROI.
    """
    def hold(reason: str) -> ResultHtmlParity:
        return ResultHtmlParity(reason)
    if enabled is not True:
        return hold('RESULT_HTML_PARITY_DISABLED')
    if type(capture) is not ClaimedResultHtml:
        return hold('RESULT_HTML_RECEIPT_MISSING')
    if (type(expected_race_id) is not str or RACE_RE.fullmatch(expected_race_id) is None
            or not _aware(capture.cutoff_at) or not _aware(capture.response_completed_at)):
        return hold('RESULT_RACE_OR_CLOCK_INVALID')
    try:
        race_day = datetime.strptime(expected_race_id[:8], '%Y%m%d').date()
    except ValueError:
        return hold('RESULT_RACE_OR_CLOCK_INVALID')
    if (race_day < date(2025, 7, 1)
            or capture.cutoff_at.astimezone(JST).date() != race_day
            or not capture.cutoff_at < capture.response_completed_at):
        return hold('RESULT_NOT_POSTRACE_OR_RACE_DAY_MISMATCH')
    if (capture.redirected is not False or capture.claimed_official_authenticated is not False
            or capture.claimed_first_write_verified is not False):
        return hold('RESULT_PREMATURE_AUTHORITY_CLAIM')
    if not _url_matches(capture.source_url, expected_race_id):
        return hold('RESULT_URL_RACE_ID_MISMATCH')
    raw = capture.raw_bytes
    if (type(raw) is not bytes or not 0 < len(raw) <= 2_097_152
            or type(capture.raw_sha256) is not str or SHA_RE.fullmatch(capture.raw_sha256) is None
            or hashlib.sha256(raw).hexdigest() != capture.raw_sha256):
        return hold('RESULT_ORIGINAL_BYTES_SHA_MISMATCH')
    if (type(capture.claimed_winning_ticket) is not str
            or re.fullmatch(r'[1-6]-[1-6]-[1-6]', capture.claimed_winning_ticket) is None
            or len(set(capture.claimed_winning_ticket.split('-'))) != 3
            or type(capture.claimed_trifecta_payout_yen) is not int
            or not 0 < capture.claimed_trifecta_payout_yen <= 100_000_000):
        return hold('RESULT_CLAIM_SHAPE_INVALID')
    try:
        page = raw.decode('utf-8', errors='strict')
        body = unicodedata.normalize('NFKC', BeautifulSoup(page, 'html.parser').get_text(' ', strip=True))
    except (UnicodeError, ValueError, TypeError):
        return hold('RESULT_HTML_ENCODING_OR_PARSE_UNKNOWN')
    if any(mark in body for mark in ('レース中止', '開催中止', '取り止め', '3連単不成立')):
        return hold('RESULT_CANCEL_OR_TRIFECTA_INVALID_UNRESOLVED')
    hits = PAYOUT_RE.findall(body)
    if len(hits) != 1:
        return hold('RESULT_MISSING_OR_AMBIGUOUS_TRIFECTA_ROW')
    a, b, c, yen = hits[0]
    try:
        payout = int(yen.replace(',', ''))
    except ValueError:
        return hold('RESULT_TRIFECTA_PAYOUT_INVALID')
    if len({a, b, c}) != 3 or not 0 < payout <= 100_000_000:
        return hold('RESULT_TRIFECTA_TICKET_OR_PAYOUT_INVALID')
    ticket = '-'.join((a, b, c))
    if (ticket != capture.claimed_winning_ticket
            or payout != capture.claimed_trifecta_payout_yen):
        return hold('RESULT_CLAIM_NOT_IN_ORIGINAL_HTML')
    return ResultHtmlParity('MOCK_RESULT_TICKET_PAYOUT_PARITY_REFUND_UNVERIFIED_HARD_HOLD',
                            expected_race_id, True, ticket, payout)
