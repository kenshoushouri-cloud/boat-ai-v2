# -*- coding: utf-8 -*-
import base64
import hashlib

import pytest

from research.candidate_discovery_v4_official_active_parser import (
    V4OfficialActiveAvailabilityParserError,
    parse_active_evidence,
)


def _encode(text: str):
    raw = text.encode("utf-8")
    return base64.b64encode(raw).decode("ascii"), hashlib.sha256(raw).hexdigest()


def active_input():
    excerpt = "<tr><td>2R</td><td>11:03</td><td><a>投票</a></td></tr>"
    raw = "<html><body>" + excerpt + "</body></html>"
    raw_b64, digest = _encode(raw)
    return {
        "contract": "candidate_discovery_v4_official_active_parse_input_v1",
        "source_kind": "venue_race_index",
        "target_date": "2026-09-21",
        "race_id": "20260921_09_02",
        "deadline_hhmm": "11:03",
        "observed_at": "2026-09-21T10:30:00+09:00",
        "source_updated_at": None,
        "source_url": (
            "https://www.boatrace.jp/owpc/pc/race/raceindex"
            "?hd=20260921&jcd=09"
        ),
        "raw_content_base64": raw_b64,
        "source_content_sha256": digest,
        "race_row_excerpt_utf8": excerpt,
        "evidence_id": "sep21-tsu-r2-active",
    }


def test_explicit_predeadline_race_row_betting_action_parses_active():
    result = parse_active_evidence(active_input())
    assert result["status"] == "active"
    assert result["scope"] == "race"
    assert result["matched_active_marker"] == "投票"
    assert result["real_raw_fixture_required_before_production"] is True
    assert result["purchase_action"] is False


def test_page_existence_or_deadline_without_betting_action_never_becomes_active():
    bad = active_input()
    excerpt = "<tr><td>2R</td><td>11:03</td><td></td></tr>"
    raw = "<html><body>" + excerpt + "</body></html>"
    bad["raw_content_base64"], bad["source_content_sha256"] = _encode(raw)
    bad["race_row_excerpt_utf8"] = excerpt
    with pytest.raises(
        V4OfficialActiveAvailabilityParserError,
        match="lacks explicit betting action",
    ):
        parse_active_evidence(bad)


@pytest.mark.parametrize("marker", ["発売終了", "中止", "順延"])
def test_blocking_marker_overrides_betting_text(marker):
    bad = active_input()
    excerpt = (
        "<tr><td>2R</td><td>11:03</td>"
        f"<td>投票 {marker}</td></tr>"
    )
    raw = "<html><body>" + excerpt + "</body></html>"
    bad["raw_content_base64"], bad["source_content_sha256"] = _encode(raw)
    bad["race_row_excerpt_utf8"] = excerpt
    with pytest.raises(
        V4OfficialActiveAvailabilityParserError,
        match="blocking marker",
    ):
        parse_active_evidence(bad)


def test_active_observation_must_be_before_frozen_deadline():
    bad = active_input()
    bad["observed_at"] = "2026-09-21T11:03:00+09:00"
    with pytest.raises(
        V4OfficialActiveAvailabilityParserError,
        match="before selected race deadline",
    ):
        parse_active_evidence(bad)


def test_race_row_deadline_must_match_frozen_deadline():
    bad = active_input()
    bad["deadline_hhmm"] = "11:04"
    with pytest.raises(
        V4OfficialActiveAvailabilityParserError,
        match="deadline does not match",
    ):
        parse_active_evidence(bad)


def test_race_row_excerpt_must_be_isolated_to_selected_race():
    bad = active_input()
    excerpt = (
        "<tr><td>2R</td><td>11:03</td><td>投票</td></tr>"
        "<tr><td>3R</td><td>11:32</td><td>投票</td></tr>"
    )
    raw = "<html><body>" + excerpt + "</body></html>"
    bad["raw_content_base64"], bad["source_content_sha256"] = _encode(raw)
    bad["race_row_excerpt_utf8"] = excerpt
    with pytest.raises(
        V4OfficialActiveAvailabilityParserError,
        match="not isolated",
    ):
        parse_active_evidence(bad)


def test_digest_binds_active_parser_to_preserved_raw_bytes():
    bad = active_input()
    bad["source_content_sha256"] = "0" * 64
    with pytest.raises(
        V4OfficialActiveAvailabilityParserError,
        match="SHA-256 mismatch",
    ):
        parse_active_evidence(bad)


def test_source_url_must_match_target_date_and_venue():
    bad = active_input()
    bad["source_url"] = (
        "https://www.boatrace.jp/owpc/pc/race/raceindex"
        "?hd=20260921&jcd=10"
    )
    with pytest.raises(
        V4OfficialActiveAvailabilityParserError,
        match="venue mismatch",
    ):
        parse_active_evidence(bad)

    bad = active_input()
    bad["source_url"] += "&unexpected=1"
    with pytest.raises(
        V4OfficialActiveAvailabilityParserError,
        match="canonical venue race-index URL",
    ):
        parse_active_evidence(bad)


def test_active_parser_module_has_no_network_db_or_production_surface():
    import inspect
    import research.candidate_discovery_v4_official_active_parser as module

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
