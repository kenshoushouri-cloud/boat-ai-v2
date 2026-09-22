# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

import pytest

from research.candidate_discovery_v4_pre_freeze_availability_capture import (
    V4PreFreezeAvailabilityCaptureError,
    build_capture_plan,
    capture_sources,
)

JST = timezone(timedelta(hours=9))


def request():
    return {
        "contract": "candidate_discovery_v4_pre_freeze_availability_capture_request_v1",
        "target_date": "2026-09-23",
        "venue_ids": ["09", "02", "17"],
        "hard_stop_at_jst": "2026-09-23T09:40:00+09:00",
        "hard_stop_basis": "earliest_scheduled_race_deadline",
    }


def ticking_clock(start="2026-09-23T08:16:00+09:00", step_seconds=1):
    current = datetime.fromisoformat(start)

    def _clock():
        nonlocal current
        value = current
        current = current + timedelta(seconds=step_seconds)
        return value

    return _clock


def fake_fetcher(url):
    return (f"<html>{url}</html>".encode("utf-8"), url)


def test_plan_is_deterministic_and_only_contains_availability_surfaces():
    plan = build_capture_plan(request())
    assert plan["venue_ids"] == ["02", "09", "17"]
    assert len(plan["sources"]) == 4
    urls = [source["source_url"] for source in plan["sources"]]
    assert urls[0].endswith("/index?hd=20260923")
    assert urls[1].endswith("/raceindex?hd=20260923&jcd=02")
    assert urls[2].endswith("/raceindex?hd=20260923&jcd=09")
    assert urls[3].endswith("/raceindex?hd=20260923&jcd=17")
    assert all("/result" not in url and "/pay" not in url for url in urls)
    assert plan["result_endpoint_reads"] == 0
    assert plan["payout_endpoint_reads"] == 0
    assert plan["purchase_action"] is False


def test_invalid_or_duplicate_venue_ids_fail_closed():
    bad = request()
    bad["venue_ids"] = ["02", "02"]
    with pytest.raises(V4PreFreezeAvailabilityCaptureError, match="unique"):
        build_capture_plan(bad)

    bad = request()
    bad["venue_ids"] = ["99"]
    with pytest.raises(V4PreFreezeAvailabilityCaptureError, match="01..24"):
        build_capture_plan(bad)


def test_hard_stop_basis_and_time_are_frozen():
    bad = request()
    bad["hard_stop_basis"] = "selected_core_deadline"
    with pytest.raises(V4PreFreezeAvailabilityCaptureError, match="hard_stop_basis"):
        build_capture_plan(bad)

    bad = request()
    bad["hard_stop_at_jst"] = "2026-09-23T08:15:00+09:00"
    with pytest.raises(V4PreFreezeAvailabilityCaptureError, match="after the 08:15"):
        build_capture_plan(bad)


def test_capture_preserves_exact_bytes_sha_and_observation_times():
    manifest, payloads = capture_sources(
        request(),
        fetcher=fake_fetcher,
        clock=ticking_clock(),
    )
    assert manifest["contract"] == (
        "candidate_discovery_v4_pre_freeze_availability_raw_manifest_v1"
    )
    assert len(manifest["sources"]) == 4
    assert set(payloads) == {
        "day-index.html",
        "venue-02-raceindex.html",
        "venue-09-raceindex.html",
        "venue-17-raceindex.html",
    }
    for source in manifest["sources"]:
        raw = payloads[source["raw_filename"]]
        import hashlib
        assert source["source_content_sha256"] == hashlib.sha256(raw).hexdigest()
        assert source["raw_bytes"] == len(raw)
        assert datetime.fromisoformat(source["observed_at"]) < datetime.fromisoformat(
            manifest["hard_stop_at_jst"]
        )
    assert manifest["all_sources_pre_hard_stop"] is True
    assert manifest["purchase_action"] is False
    assert manifest["production_mutation"] is False


def test_capture_before_source_cutoff_fails_closed():
    with pytest.raises(V4PreFreezeAvailabilityCaptureError, match="before 08:15"):
        capture_sources(
            request(),
            fetcher=fake_fetcher,
            clock=ticking_clock(start="2026-09-23T08:14:59+09:00"),
        )


def test_capture_at_or_after_hard_stop_fails_closed():
    with pytest.raises(
        V4PreFreezeAvailabilityCaptureError,
        match="at/after earliest scheduled deadline",
    ):
        capture_sources(
            request(),
            fetcher=fake_fetcher,
            clock=ticking_clock(start="2026-09-23T09:40:00+09:00"),
        )


def test_redirect_or_empty_payload_fails_closed():
    with pytest.raises(V4PreFreezeAvailabilityCaptureError, match="redirect"):
        capture_sources(
            request(),
            fetcher=lambda url: (b"x", url + "&redirected=1"),
            clock=ticking_clock(),
        )

    with pytest.raises(V4PreFreezeAvailabilityCaptureError, match="empty raw"):
        capture_sources(
            request(),
            fetcher=lambda url: (b"", url),
            clock=ticking_clock(),
        )


def test_crossing_hard_stop_during_capture_fails_closed():
    data = request()
    data["hard_stop_at_jst"] = "2026-09-23T08:16:03+09:00"
    with pytest.raises(
        V4PreFreezeAvailabilityCaptureError,
        match="earliest scheduled deadline",
    ):
        capture_sources(
            data,
            fetcher=fake_fetcher,
            clock=ticking_clock(start="2026-09-23T08:16:00+09:00", step_seconds=1),
        )


def test_capture_module_has_no_db_railway_line_or_purchase_surface():
    import inspect
    import research.candidate_discovery_v4_pre_freeze_availability_capture as module

    source = inspect.getsource(module).lower()
    for forbidden in (
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
