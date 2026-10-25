# -*- coding: utf-8 -*-
from pathlib import Path

import research.v51_exhibition_time_historical_readiness_pg as ex


def test_historical_provenance_contract_is_explicit():
    assert (
        ex.EXPLICIT_SOURCE_CONTRACT
        == "BOATRACE_OFFICIAL_ARCHIVED_BEFOREINFO_PREDEADLINE_ASSUMED_V1"
    )
    assert "official_beforeinfo_historical" in ex.ACCEPTED_SOURCES


def test_time_validation_is_conservative():
    assert ex._finite_time(6.72)
    assert not ex._finite_time(None)
    assert not ex._finite_time(0)
    assert not ex._finite_time(999)


def test_audit_is_result_blind_and_read_only():
    s = Path(
        "research/v51_exhibition_time_historical_readiness_pg.py"
    ).read_text(encoding="utf-8").lower()
    assert "set transaction read only" in s
    for token in (
        "v2_results",
        "v2_result_entries",
        "v2_odds",
        "payout_yen",
        "trifecta_payout",
        "insert into",
        "update v2_",
        "delete from",
    ):
        assert token not in s
