# -*- coding: utf-8 -*-
import hashlib
from copy import deepcopy

import pytest

from research.candidate_discovery_v4_availability_guard import (
    evaluate_availability_guard,
)
from research.candidate_discovery_v4_availability_snapshot_binder import (
    V4AvailabilitySnapshotBinderError,
    bind_availability_snapshot,
)


def artifact():
    core = [
        ("20260923_02_08", "02", 8, "10:40"),
        ("20260923_17_04", "17", 4, "11:40"),
        ("20260923_09_05", "09", 5, "09:40"),
        ("20260923_02_11", "02", 11, "12:30"),
        ("20260923_03_07", "03", 7, "10:15"),
        ("20260923_10_06", "10", 6, "10:20"),
    ]
    feed = []
    for rank, (race_id, venue, race_no, hhmm) in enumerate(core, 1):
        feed.append(
            {
                "race_id": race_id,
                "race_date": "2026-09-23",
                "venue_id": venue,
                "race_no": race_no,
                "deadline_at": f"2026-09-23T{hhmm}:00+09:00",
                "daily_rank": rank,
                "tickets": [
                    {"core_order": 1, "ticket": "1-2-3"},
                    {"core_order": 2, "ticket": "1-3-2"},
                ],
            }
        )
    return {
        "contract": "candidate_discovery_v4_main_feed_v1",
        "generated_at_jst": "2026-09-23T08:17:00+09:00",
        "prospective_evidence_eligible": True,
        "purchase_action": False,
        "freeze_provenance": {
            "target_date": "2026-09-23",
            "completed_at_jst": "2026-09-23T08:17:00+09:00",
            "all_frozen_rows_pre_deadline": True,
        },
        "feed": feed,
    }


def _venue_page(rows):
    return (
        "<html><table>"
        + "".join(
            f"<tr><td>{race_no}R</td><td>{hhmm}</td><td><a>投票</a></td></tr>"
            for race_no, hhmm in rows
        )
        + "</table></html>"
    ).encode("utf-8")


def raw_fixture(cancel_venue=None):
    venue_rows = {
        "02": [(8, "10:40"), (11, "12:30")],
        "17": [(4, "11:40")],
        "09": [(5, "09:40")],
        "03": [(7, "10:15")],
        "10": [(6, "10:20")],
    }
    if cancel_venue is None:
        day = "<html><table><tr><td>通常開催</td></tr></table></html>".encode("utf-8")
    else:
        names = {"02": "戸田", "09": "津"}
        day = (
            "<html><table>"
            f"<tr><td>{names[cancel_venue]}</td><td>中止順延</td></tr>"
            "</table></html>"
        ).encode("utf-8")

    payloads = {"day-index.html": day}
    sources = [
        {
            "source_id": "day-index",
            "source_kind": "venue_day_index",
            "source_url": "https://www.boatrace.jp/owpc/pc/race/index?hd=20260923",
            "observed_at": "2026-09-23T08:16:10+09:00",
            "source_content_sha256": hashlib.sha256(day).hexdigest(),
            "raw_filename": "day-index.html",
            "raw_bytes": len(day),
        }
    ]
    for venue_id, rows in venue_rows.items():
        raw = _venue_page(rows)
        filename = f"venue-{venue_id}-raceindex.html"
        source_id = f"venue-{venue_id}-raceindex"
        payloads[filename] = raw
        sources.append(
            {
                "source_id": source_id,
                "source_kind": "venue_race_index",
                "venue_id": venue_id,
                "source_url": (
                    "https://www.boatrace.jp/owpc/pc/race/raceindex"
                    f"?hd=20260923&jcd={venue_id}"
                ),
                "observed_at": "2026-09-23T08:16:20+09:00",
                "source_content_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_filename": filename,
                "raw_bytes": len(raw),
            }
        )
    manifest = {
        "contract": "candidate_discovery_v4_pre_freeze_availability_raw_manifest_v1",
        "target_date": "2026-09-23",
        "venue_ids": sorted(venue_rows),
        "source_cutoff_at_jst": "2026-09-23T08:15:00+09:00",
        "hard_stop_at_jst": "2026-09-23T09:40:00+09:00",
        "hard_stop_basis": "earliest_scheduled_race_deadline",
        "scheduled_race_count": 60,
        "race_universe_sha256": "a" * 64,
        "capture_started_at_jst": "2026-09-23T08:16:00+09:00",
        "capture_completed_at_jst": "2026-09-23T08:16:30+09:00",
        "sources": sources,
        "all_sources_pre_hard_stop": True,
        "result_endpoint_reads": 0,
        "payout_endpoint_reads": 0,
        "purchase_action": False,
        "production_mutation": False,
    }
    return manifest, payloads


def test_all_active_raw_binds_exact_six_and_guard_passes():
    manifest, payloads = raw_fixture()
    snapshot = bind_availability_snapshot(artifact(), manifest, payloads)
    assert len(snapshot["races"]) == 6
    assert len(snapshot["evidence_sources"]) == 5
    venue02 = [row for row in snapshot["races"] if row["venue_id"] == "02"]
    assert len(venue02) == 2
    assert venue02[0]["evidence_id"] == venue02[1]["evidence_id"]
    assert venue02[0]["evidence_binding_sha256"] != venue02[1][
        "evidence_binding_sha256"
    ]
    result = evaluate_availability_guard(artifact(), snapshot)
    assert result["decision"] == "PASS_ACTIVE_CORE"
    assert result["eligible_under_guard"] is True


def test_pre_freeze_venue_cancel_raw_binds_blocking_snapshot():
    manifest, payloads = raw_fixture(cancel_venue="02")
    snapshot = bind_availability_snapshot(artifact(), manifest, payloads)
    venue02 = [row for row in snapshot["races"] if row["venue_id"] == "02"]
    assert {row["status"] for row in venue02} == {"cancelled_postponed"}
    assert {row["scope"] for row in venue02} == {"venue"}
    assert {row["evidence_id"] for row in venue02} == {"day-index"}
    result = evaluate_availability_guard(artifact(), snapshot)
    assert result["decision"] == "BLOCK_PRE_FREEZE_UNAVAILABLE_CORE"
    assert len(result["blocked_core_races"]) == 2


def test_generated_timestamp_must_match_freeze_completion():
    bad_artifact = artifact()
    bad_artifact["freeze_provenance"]["completed_at_jst"] = (
        "2026-09-23T08:17:01+09:00"
    )
    manifest, payloads = raw_fixture()
    with pytest.raises(
        V4AvailabilitySnapshotBinderError,
        match="must equal freeze completion",
    ):
        bind_availability_snapshot(bad_artifact, manifest, payloads)


def test_partial_venue_range_blocks_only_covered_core_race():
    manifest, payloads = raw_fixture()
    day = (
        "<html><table>"
        "<tr><td>戸田</td><td>11R以降中止</td></tr>"
        "</table></html>"
    ).encode("utf-8")
    payloads["day-index.html"] = day
    day_source = next(
        source
        for source in manifest["sources"]
        if source["source_id"] == "day-index"
    )
    day_source["source_content_sha256"] = hashlib.sha256(day).hexdigest()
    day_source["raw_bytes"] = len(day)

    snapshot = bind_availability_snapshot(artifact(), manifest, payloads)
    toda = sorted(
        [row for row in snapshot["races"] if row["venue_id"] == "02"],
        key=lambda row: row["race_id"],
    )
    assert len(toda) == 2
    r8 = next(row for row in toda if row["race_id"].endswith("_08"))
    r11 = next(row for row in toda if row["race_id"].endswith("_11"))
    assert r8["status"] == "active"
    assert r8["scope"] == "race"
    assert r11["status"] == "cancelled_postponed"
    assert r11["scope"] == "venue_race_range"
    assert r11["cancel_from_race_no"] == 11

    result = evaluate_availability_guard(artifact(), snapshot)
    assert result["decision"] == "BLOCK_PRE_FREEZE_UNAVAILABLE_CORE"
    assert [row["race_id"] for row in result["blocked_core_races"]] == [
        "20260923_02_11"
    ]


def test_raw_capture_after_artifact_freeze_is_rejected():
    manifest, payloads = raw_fixture()
    manifest["capture_completed_at_jst"] = "2026-09-23T08:18:00+09:00"
    with pytest.raises(
        V4AvailabilitySnapshotBinderError,
        match="completed after artifact freeze",
    ):
        bind_availability_snapshot(artifact(), manifest, payloads)


def test_raw_sha_mismatch_is_rejected_before_parsing():
    manifest, payloads = raw_fixture()
    manifest["sources"][1]["source_content_sha256"] = "0" * 64
    with pytest.raises(
        V4AvailabilitySnapshotBinderError,
        match="SHA-256 mismatch",
    ):
        bind_availability_snapshot(artifact(), manifest, payloads)


def test_missing_venue_source_fails_closed():
    manifest, payloads = raw_fixture()
    manifest["sources"] = [
        source for source in manifest["sources"]
        if source["source_id"] != "venue-17-raceindex"
    ]
    with pytest.raises(
        V4AvailabilitySnapshotBinderError,
        match="venue raceindex raw source missing",
    ):
        bind_availability_snapshot(artifact(), manifest, payloads)


def test_ambiguous_duplicate_race_row_fails_closed():
    manifest, payloads = raw_fixture()
    source = next(
        item for item in manifest["sources"]
        if item["source_id"] == "venue-17-raceindex"
    )
    raw = (
        "<html><table>"
        "<tr><td>4R</td><td>11:40</td><td>投票</td></tr>"
        "<tr><td>4R</td><td>11:40</td><td>投票</td></tr>"
        "</table></html>"
    ).encode("utf-8")
    payloads[source["raw_filename"]] = raw
    source["source_content_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(
        V4AvailabilitySnapshotBinderError,
        match="exactly one active race-row candidate",
    ):
        bind_availability_snapshot(artifact(), manifest, payloads)


def test_missing_positive_marker_fails_closed_through_active_parser():
    manifest, payloads = raw_fixture()
    source = next(
        item for item in manifest["sources"]
        if item["source_id"] == "venue-17-raceindex"
    )
    raw = (
        "<html><table>"
        "<tr><td>4R</td><td>11:40</td><td></td></tr>"
        "</table></html>"
    ).encode("utf-8")
    payloads[source["raw_filename"]] = raw
    source["source_content_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(
        V4AvailabilitySnapshotBinderError,
        match="active parser rejected",
    ):
        bind_availability_snapshot(artifact(), manifest, payloads)


def test_binder_has_no_network_db_railway_line_or_purchase_surface():
    import inspect
    import research.candidate_discovery_v4_availability_snapshot_binder as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "urllib",
        "requests",
        "psycopg",
        "database_url",
        "railway_api",
        "line_notify",
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "buy(",
    ):
        assert forbidden not in source
