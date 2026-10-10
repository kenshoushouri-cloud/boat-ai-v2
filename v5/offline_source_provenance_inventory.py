# -*- coding: utf-8 -*-
"""Static, offline V5 feature provenance review; never a live authorization.

Based only on GitHub read-only inspection of v21_realtime_collector_pg.py and
research/historical_exhibition_reuse_pg.py (2026-10-10). This is NOT a live
DB schema inspection. No source/first-observation/commit has been authenticated.
Any metadata supplied by a caller is an untrusted *claim*, not an attestation.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

# Independently frozen seven-feature inventory from the reviewed V5 contract.
# Future changes to the model's features require separately revising this audit.
REQUIRED_FEATURES = frozenset({
    "lane_class", "recent_form", "exhibition_rank", "racer_course",
    "opponent", "venue_lane", "prior_day_k",
})

MUTABLE = "MUTABLE_SNAPSHOT_NOT_ATTESTED"
DERIVED = "DERIVED_FREEZE_UNVERIFIED"
UNREVIEWED = "SOURCE_SCHEMA_UNREVIEWED"

# Only conclusions justified by the TWO reviewed GitHub source files.
# No label here means that some other repository component or DB lacks data.
_REVIEWED = (
    ("lane_class", "v2_realtime_entry_snapshots", MUTABLE),
    ("exhibition_rank", "v2_realtime_exhibition_snapshots", MUTABLE),
    ("recent_form", "derived_feature_source_not_reviewed", DERIVED),
    ("racer_course", "derived_feature_source_not_reviewed", DERIVED),
    ("opponent", "derived_feature_source_not_reviewed", DERIVED),
    ("venue_lane", "derived_feature_source_not_reviewed", DERIVED),
    ("prior_day_k", "prior_day_k_schema_not_reviewed", UNREVIEWED),
)
if {row[0] for row in _REVIEWED} != REQUIRED_FEATURES:
    raise RuntimeError("V5_STATIC_FEATURE_INVENTORY_OUT_OF_SYNC")

# Report only the *names* of unverified caller claims, never their content.
_CLAIM_NAMES = frozenset({
    "snapshot_at", "updated_at", "historical_upsert", "source_observed_at",
    "original_frozen_at", "feature_observed_at", "raw_sha256",
    "independent_auditor", "immutable", "first_write_confirmed",
    "six_active_starts_confirmed", "forward_eligible", "buy_eligible",
})


@dataclass(frozen=True, slots=True)
class FeatureSourceReview:
    feature: str
    checked_source: str
    classification: str
    claimed_fields_ignored: tuple[str, ...] = ()
    independently_frozen_proof: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class SourceProvenanceInventory:
    status: str
    features: tuple[FeatureSourceReview, ...]
    counts: tuple[tuple[str, int], ...]
    approved_provenance_features: int = field(default=0, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def review_offline_source_provenance(
    caller_metadata: object = None,
) -> SourceProvenanceInventory:
    """Return fixed seven-feature findings; no caller value can upgrade proof.

    Optional metadata is *untrusted*. Invalid/unknown fields fail closed while
    retaining the same fixed feature classifications for human review.
    A timestamp like snapshot_at or updated_at or a historical UPSERT proves
    neither independently captured source bytes nor immutable cutoff freeze.
    """
    supplied = {} if caller_metadata is None else caller_metadata
    valid = isinstance(supplied, Mapping)
    if valid:
        try:
            valid = all(
                type(name) is str and name in REQUIRED_FEATURES
                and isinstance(fields, Mapping)
                and all(type(key) is str for key in fields)
                for name, fields in supplied.items()
            )
        except (TypeError, ValueError):
            valid = False
    observed = supplied if valid else {}
    reviews = tuple(
        FeatureSourceReview(
            feature, source, status,
            tuple(sorted(set(observed.get(feature, {})) & _CLAIM_NAMES)),
        )
        for feature, source, status in _REVIEWED
    )
    counts = Counter(item.classification for item in reviews)
    return SourceProvenanceInventory(
        "STATIC_REVIEW_ONLY_ALL_HARD_HOLD" if valid else "INVALID_UNTRUSTED_INPUT_HARD_HOLD",
        reviews,
        tuple(sorted(counts.items())),
    )
