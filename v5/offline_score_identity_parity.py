# -*- coding: utf-8 -*-
"""Synthetic-only scoring row identity/parity audit; NOT a production scorer.

A caller-supplied digest is not independent source authentication. The audit
never selects/prunes races using winner, incident, VOID or postrace outcomes,
never changes historic strong-core values and cannot authorize Forward/BUY.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from v5.offline_asof_eligibility import RACE_RE, SHA_RE

MAX_ROWS = 500
TRAIN_END = '2026-03-31'
APRIL_END = '2026-04-30'
MAY_END = '2026-05-31'
FIVE_FACTORS = frozenset({'recent_form', 'exhibition_rank', 'racer_course', 'opponent', 'venue_lane'})
PERIODS = ('train', 'oos_all', 'oos_april', 'oos_may', 'oos_june_to_end')


@dataclass(frozen=True, slots=True)
class ScoringOrigin:
    """Must be bound by the *upstream scorer*, not inferred later by venue/order."""
    race_id: str
    frozen_score_row_sha256: str


@dataclass(frozen=True, slots=True)
class OfflineScorerIdentityParity:
    status: str
    original_rows: int = 0
    train_rows: int = 0
    oos_rows: int = 0
    original_baseline_sha256: str = ''
    # No winner, raw scores or original evaluation metrics are exposed here.
    race_id_row_sha256: tuple[tuple[str, str], ...] = ()
    historical_evaluation_preserved: bool = False
    postrace_pruning_performed: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _json_bytes(value: object) -> bytes:
    """Canonically serialize finite JSON-only synthetic fixtures."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def score_row_digest(row: Mapping[str, object]) -> str:
    return hashlib.sha256(_json_bytes(row)).hexdigest()


def frozen_baseline_digest(rows: object, historical_metrics: object) -> str:
    """Calculate a synthetic expectation; caller must independently freeze it."""
    return hashlib.sha256(_json_bytes({'rows': rows, 'metrics': historical_metrics})).hexdigest()


def _race_date(race_id: object) -> str | None:
    if type(race_id) is not str or RACE_RE.fullmatch(race_id) is None:
        return None
    try:
        day = datetime.strptime(race_id[:8], '%Y%m%d').date()
    except ValueError:
        return None
    return day.isoformat() if day >= date(2025, 7, 1) else None


def _period_counts(rows: tuple[Mapping[str, object], ...]) -> dict[str, int]:
    dates = [r['date'] for r in rows]
    return {
        'train': sum(d <= TRAIN_END for d in dates),
        'oos_all': sum(d > TRAIN_END for d in dates),
        'oos_april': sum(TRAIN_END < d <= APRIL_END for d in dates),
        'oos_may': sum(APRIL_END < d <= MAY_END for d in dates),
        'oos_june_to_end': sum(d > MAY_END for d in dates),
    }


def audit_offline_scorer_identity_parity(
    *, scorer_origins: object, original_score_rows: object,
    frozen_historical_metrics: object, frozen_baseline_sha256: object,
) -> OfflineScorerIdentityParity:
    """Bind score-row digests to explicit race IDs without positional joins.

    No score or outcome based filtering; every original row must map exactly
    once. Historic train/OOS metric payload must match its frozen SHA and its
    n-values must exactly match the unchanged row cohort.
    """
    def deny(reason: str) -> OfflineScorerIdentityParity:
        return OfflineScorerIdentityParity(reason)

    if (type(original_score_rows) not in (tuple, list)
            or not 0 < len(original_score_rows) <= MAX_ROWS
            or any(type(row) is not dict for row in original_score_rows)):
        return deny('INVALID_OR_EMPTY_ORIGINAL_SCORING_ROWS')
    if (type(scorer_origins) not in (tuple, list)
            or len(scorer_origins) != len(original_score_rows)
            or any(type(anchor) is not ScoringOrigin for anchor in scorer_origins)):
        return deny('SCORER_ORIGIN_COUNT_OR_TYPE_MISMATCH')
    if (type(frozen_baseline_sha256) is not str
            or SHA_RE.fullmatch(frozen_baseline_sha256) is None):
        return deny('FROZEN_BASELINE_REFERENCE_MISSING')

    try:
        rows = tuple(original_score_rows)
        # Keep the full baseline untouched; never infer identity from venue/day/order.
        for row in rows:
            if (set(row) != {'date', 'venue', 'winner', 'base', 'factors'}
                    or type(row['date']) is not str
                    or type(row['venue']) is not str
                    or not row['venue']
                    or type(row['winner']) is not int
                    or type(row['base']) is not list or len(row['base']) != 6
                    or type(row['factors']) is not dict
                    or set(row['factors']) != FIVE_FACTORS
                    or any(type(v) is not list or len(v) != 6
                           for v in row['factors'].values())):
                return deny('UNEXPECTED_LEGACY_SCORE_ROW_SHAPE')
            if date.fromisoformat(row['date']).isoformat() != row['date']:
                return deny('INVALID_SCORE_DATE')
        digest_by_row = [score_row_digest(row) for row in rows]
        actual_baseline = frozen_baseline_digest(original_score_rows, frozen_historical_metrics)
    except (TypeError, ValueError, OverflowError, RecursionError, KeyError):
        return deny('INVALID_OR_NONFINITE_BASELINE_PAYLOAD')
    if actual_baseline != frozen_baseline_sha256:
        return deny('HISTORICAL_BASELINE_DIGEST_CHANGED')
    if len(set(digest_by_row)) != len(digest_by_row):
        return deny('AMBIGUOUS_IDENTICAL_SCORE_ROWS')

    race_ids = [_race_date(anchor.race_id) for anchor in scorer_origins]
    if any(d is None for d in race_ids):
        return deny('INVALID_OR_MISSING_SCORER_RACE_ID')
    if len(set(anchor.race_id for anchor in scorer_origins)) != len(scorer_origins):
        return deny('DUPLICATE_SCORER_RACE_ID')
    anchor_hashes = [anchor.frozen_score_row_sha256 for anchor in scorer_origins]
    if (any(type(h) is not str or SHA_RE.fullmatch(h) is None for h in anchor_hashes)
            or Counter(anchor_hashes) != Counter(digest_by_row)):
        return deny('MISSING_OR_EXTRA_OR_TAMPERED_SCORING_ROW_BINDING')
    by_hash = {h: row['date'] for h, row in zip(digest_by_row, rows)}
    if any(d != by_hash[anchor.frozen_score_row_sha256]
           for d, anchor in zip(race_ids, scorer_origins)):
        return deny('SCORER_RACE_ID_DATE_MISMATCH')

    if type(frozen_historical_metrics) is not dict or set(frozen_historical_metrics) != set(PERIODS):
        return deny('INVALID_HISTORICAL_METRIC_BLOCKS')
    counts = _period_counts(rows)
    for period in PERIODS:
        block = frozen_historical_metrics[period]
        if (type(block) is not dict or set(block) != {'uncalibrated', 'calibrated'}):
            return deny('INVALID_HISTORICAL_METRIC_BLOCKS')
        for flavor in ('uncalibrated', 'calibrated'):
            part = block[flavor]
            if type(part) is not dict or type(part.get('n')) is not int or part['n'] != counts[period]:
                return deny('HISTORICAL_SCORING_COHORT_COUNT_CHANGED')

    # Even if a postrace winner is 0 or an incident appears in the baseline,
    # this code never removes that row or conditions coverage on the outcome.
    joined = tuple(sorted((anchor.race_id, anchor.frozen_score_row_sha256)
                          for anchor in scorer_origins))
    return OfflineScorerIdentityParity(
        status='SYNTHETIC_IDENTITY_AND_BASELINE_PARITY_HARD_HOLD',
        original_rows=len(rows), train_rows=counts['train'], oos_rows=counts['oos_all'],
        original_baseline_sha256=actual_baseline,
        race_id_row_sha256=joined,
        historical_evaluation_preserved=True,
    )
