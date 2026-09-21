# -*- coding: utf-8 -*-
import base64
import hashlib
from copy import deepcopy

import pytest

from research.candidate_discovery_v4_official_availability_parser import (
    V4OfficialAvailabilityParserError,
    parse_unavailability_evidence,
)


def _encode(text: str):
    raw = text.encode("utf-8")
    return base64.b64encode(raw).decode("ascii"), hashlib.sha256(raw).hexdigest()


def venue_input():
    excerpt = "<div>戸田</div><span>中止順延</span>"
    raw = "<html><body>" + excerpt + "</body></html>"
    raw_b64, digest = _encode(raw)
    return {
        "contract": "candidate_discovery_v4_official_unavailability_parse_input_v1",
        "source_kind": "venue_day_index",
        "target_date": "2026-09-21",
        "race_id": "20260921_02_08",
        "observed_at": "2026-09-21T09:00:00+09:00",
        "source_updated_at": "2026-09-21T08:25:00+09:00",
        "source_url": "https://www.boatrace.jp/owpc/pc/race/index?hd=20260921",
        "raw_content_base64": raw_b64,
        "source_content_sha256": digest,
        "evidence_excerpt_utf8": excerpt,
        "evidence_id": "sep21-toda-index",
    }


def race_input():
    excerpt = "<section>レース中止</section>"
    raw = "<html><body>" + excerpt + "</body></html>"
    raw_b64, digest = _encode(raw)
    return {
        "contract": "candidate_discovery_v4_official_unavailability_parse_input_v1",
        "source_kind": "race_page",
        "target_date": "2026-09-21",
        "race_id": "20260921_02_08",
        "observed_at": "2026-09-21T13:00:00+09:00",
        "source_updated_at": None,
        "source_url": (
            "https://www.boatrace.jp/owpc/pc/race/racelist"
            "?hd=20260921&jcd=02&rno=8"
        ),
        "raw_content_base64": raw_b64,
        "source_content_sha256": digest,
        "evidence_excerpt_utf8": excerpt,
        "evidence_id": "sep21-toda-r8",
    }


def test_venue_day_unavailable_parses_as_block_only_evidence():
    result = parse_unavailability_evidence(venue_input())
    assert result["status"] == "cancelled_postponed"
    assert result["scope"] == "venue"
    assert result["matched_unavailable_marker"] == "中止順延"
    assert result["positive_active_evidence_supported"] is False
    assert result["purchase_action"] is False


def test_race_page_cancelled_parses_as_race_scope():
    result = parse_unavailability_evidence(race_input())
    assert result["status"] == "cancelled_postponed"
    assert result["scope"] == "race"
    assert result["matched_unavailable_marker"] == "レース中止"


def test_digest_binds_parser_to_preserved_raw_bytes():
    bad = venue_input()
    bad["source_content_sha256"] = "0" * 64
    with pytest.raises(V4OfficialAvailabilityParserError, match="SHA-256 mismatch"):
        parse_unavailability_evidence(bad)


def test_excerpt_must_be_exactly_bound_to_raw_payload():
    bad = venue_input()
    bad["evidence_excerpt_utf8"] = "戸田 中止順延"
    with pytest.raises(V4OfficialAvailabilityParserError, match="occur exactly once"):
        parse_unavailability_evidence(bad)

    bad = venue_input()
    excerpt = bad["evidence_excerpt_utf8"]
    raw = "<html>" + excerpt + excerpt + "</html>"
    bad["raw_content_base64"], bad["source_content_sha256"] = _encode(raw)
    with pytest.raises(V4OfficialAvailabilityParserError, match="occur exactly once"):
        parse_unavailability_evidence(bad)


def test_venue_day_marker_must_identify_expected_venue():
    bad = venue_input()
    excerpt = "<div>三国</div><span>中止順延</span>"
    raw = "<html><body>" + excerpt + "</body></html>"
    bad["raw_content_base64"], bad["source_content_sha256"] = _encode(raw)
    bad["evidence_excerpt_utf8"] = excerpt
    with pytest.raises(V4OfficialAvailabilityParserError, match="expected venue"):
        parse_unavailability_evidence(bad)


def test_positive_or_ambiguous_text_never_becomes_active():
    bad = venue_input()
    excerpt = "<div>戸田</div><span>開催中</span>"
    raw = "<html><body>" + excerpt + "</body></html>"
    bad["raw_content_base64"], bad["source_content_sha256"] = _encode(raw)
    bad["evidence_excerpt_utf8"] = excerpt
    with pytest.raises(V4OfficialAvailabilityParserError, match="unavailable marker"):
        parse_unavailability_evidence(bad)


def test_race_page_identity_must_match_race_id():
    bad = race_input()
    bad["source_url"] = (
        "https://www.boatrace.jp/owpc/pc/race/racelist"
        "?hd=20260921&jcd=02&rno=7"
    )
    with pytest.raises(V4OfficialAvailabilityParserError, match="race number mismatch"):
        parse_unavailability_evidence(bad)


def test_source_update_cannot_be_after_observation():
    bad = venue_input()
    bad["source_updated_at"] = "2026-09-21T09:01:00+09:00"
    with pytest.raises(V4OfficialAvailabilityParserError, match="after observed_at"):
        parse_unavailability_evidence(bad)


def test_non_official_source_fails_closed():
    bad = race_input()
    bad["source_url"] = "https://example.com/owpc/pc/race/racelist?hd=20260921&jcd=02&rno=8"
    with pytest.raises(V4OfficialAvailabilityParserError, match="BOAT RACE official"):
        parse_unavailability_evidence(bad)


def test_parser_module_has_no_network_db_or_production_surface():
    import inspect
    import research.candidate_discovery_v4_official_availability_parser as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "psycopg",
        "database_url",
        "requests",
        "urllib",
        "railway",
        "line_notify",
        "subprocess",
        "os.environ",
        "insert into",
        "update v2_",
        "delete from",
        "vacuum",
    ):
        assert forbidden not in source
