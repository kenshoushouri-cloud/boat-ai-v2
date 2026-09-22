# -*- coding: utf-8 -*-
import hashlib
import json
from pathlib import Path

import pytest

from research.candidate_discovery_v4_availability_gate_runtime import (
    V4AvailabilityGateRuntimeError,
    evaluate_gate_files,
)


def _artifact():
    feed = []
    venues = ["01", "02", "03", "04", "05", "06"]
    for rank, venue in enumerate(venues, 1):
        hhmm = f"{10 + rank:02d}:00"
        feed.append(
            {
                "race_id": f"20260923_{venue}_01",
                "race_date": "2026-09-23",
                "venue_id": venue,
                "race_no": 1,
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


def _write_fixture(tmp_path: Path, *, cancel_venue: str | None = None):
    artifact_path = tmp_path / "artifact.json"
    request_path = tmp_path / "request.json"
    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()

    artifact_path.write_text(
        json.dumps(_artifact(), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    venue_ids = ["01", "02", "03", "04", "05", "06"]
    request = {
        "contract": "candidate_discovery_v4_pre_freeze_availability_capture_request_v1",
        "target_date": "2026-09-23",
        "venue_ids": venue_ids,
        "scheduled_race_count": 72,
        "race_universe_sha256": "a" * 64,
        "hard_stop_at_jst": "2026-09-23T11:00:00+09:00",
        "hard_stop_basis": "earliest_scheduled_race_deadline",
    }
    request_path.write_text(
        json.dumps(request, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    venue_names = {
        "01": "桐生",
        "02": "戸田",
        "03": "江戸川",
        "04": "平和島",
        "05": "多摩川",
        "06": "浜名湖",
    }
    if cancel_venue is None:
        day_raw = b"<html><table><tr><td>normal</td></tr></table></html>"
    else:
        day_raw = (
            "<html><table>"
            f"<tr><td>{venue_names[cancel_venue]}</td><td>中止順延</td></tr>"
            "</table></html>"
        ).encode("utf-8")
    (capture_dir / "day-index.html").write_bytes(day_raw)

    sources = [
        {
            "source_id": "day-index",
            "source_kind": "venue_day_index",
            "source_url": "https://www.boatrace.jp/owpc/pc/race/index?hd=20260923",
            "observed_at": "2026-09-23T08:16:05+09:00",
            "source_content_sha256": hashlib.sha256(day_raw).hexdigest(),
            "raw_filename": "day-index.html",
            "raw_bytes": len(day_raw),
        }
    ]

    for rank, venue in enumerate(venue_ids, 1):
        hhmm = f"{10 + rank:02d}:00"
        raw = (
            "<html><table>"
            f"<tr><td>1R</td><td>{hhmm}</td><td><a>投票</a></td></tr>"
            "</table></html>"
        ).encode("utf-8")
        filename = f"venue-{venue}-raceindex.html"
        (capture_dir / filename).write_bytes(raw)
        sources.append(
            {
                "source_id": f"venue-{venue}-raceindex",
                "source_kind": "venue_race_index",
                "venue_id": venue,
                "source_url": (
                    "https://www.boatrace.jp/owpc/pc/race/raceindex"
                    f"?hd=20260923&jcd={venue}"
                ),
                "observed_at": "2026-09-23T08:16:10+09:00",
                "source_content_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_filename": filename,
                "raw_bytes": len(raw),
            }
        )

    manifest = {
        "contract": "candidate_discovery_v4_pre_freeze_availability_raw_manifest_v1",
        **{k: request[k] for k in (
            "target_date",
            "venue_ids",
            "scheduled_race_count",
            "race_universe_sha256",
            "hard_stop_at_jst",
            "hard_stop_basis",
        )},
        "source_cutoff_at_jst": "2026-09-23T08:15:00+09:00",
        "capture_started_at_jst": "2026-09-23T08:16:00+09:00",
        "capture_completed_at_jst": "2026-09-23T08:16:30+09:00",
        "sources": sources,
        "all_sources_pre_hard_stop": True,
        "result_endpoint_reads": 0,
        "payout_endpoint_reads": 0,
        "purchase_action": False,
        "production_mutation": False,
    }
    (capture_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return artifact_path, capture_dir, request_path


def _evaluate(tmp_path: Path, *, cancel_venue: str | None = None):
    artifact_path, capture_dir, request_path = _write_fixture(
        tmp_path,
        cancel_venue=cancel_venue,
    )
    return evaluate_gate_files(
        artifact_path=artifact_path,
        capture_dir=capture_dir,
        request_path=request_path,
        snapshot_output=tmp_path / "snapshot.json",
        result_output=tmp_path / "result.json",
    )


def test_all_active_runtime_passes_without_mutation(tmp_path):
    result = _evaluate(tmp_path)
    assert result["decision"] == "PASS_ACTIVE_CORE"
    assert result["eligible_under_guard"] is True
    assert result["blocked_core_races"] == []
    assert result["replacement_candidates_generated"] is False
    assert result["ranking_changed"] is False
    assert result["purchase_action"] is False
    assert (tmp_path / "snapshot.json").is_file()
    assert (tmp_path / "result.json").is_file()


def test_cancelled_selected_venue_runtime_blocks_without_replacement(tmp_path):
    result = _evaluate(tmp_path, cancel_venue="02")
    assert result["decision"] == "BLOCK_PRE_FREEZE_UNAVAILABLE_CORE"
    assert result["eligible_under_guard"] is False
    assert [row["venue_id"] for row in result["blocked_core_races"]] == ["02"]
    assert result["replacement_candidates_generated"] is False
    assert result["ranking_changed"] is False


def test_request_manifest_identity_mismatch_fails_closed(tmp_path):
    artifact_path, capture_dir, request_path = _write_fixture(tmp_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["race_universe_sha256"] = "b" * 64
    request_path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(
        V4AvailabilityGateRuntimeError,
        match="request/manifest identity mismatch",
    ):
        evaluate_gate_files(
            artifact_path=artifact_path,
            capture_dir=capture_dir,
            request_path=request_path,
            snapshot_output=tmp_path / "snapshot.json",
            result_output=tmp_path / "result.json",
        )


def test_path_traversal_raw_filename_fails_closed(tmp_path):
    artifact_path, capture_dir, request_path = _write_fixture(tmp_path)
    manifest_path = capture_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"][0]["raw_filename"] = "../day-index.html"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(V4AvailabilityGateRuntimeError, match="raw_filename"):
        evaluate_gate_files(
            artifact_path=artifact_path,
            capture_dir=capture_dir,
            request_path=request_path,
            snapshot_output=tmp_path / "snapshot.json",
            result_output=tmp_path / "result.json",
        )


def test_runtime_has_no_network_db_railway_line_or_purchase_surface():
    import inspect
    import research.candidate_discovery_v4_availability_gate_runtime as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "urllib",
        "requests",
        "psycopg",
        "database_url",
        "railway",
        "line_notify",
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "buy(",
    ):
        assert forbidden not in source
