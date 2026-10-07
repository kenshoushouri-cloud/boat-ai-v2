# -*- coding: utf-8 -*-
from pathlib import Path

import research.historical_exhibition_reuse_pg as m


def test_date_range_is_inclusive():
    assert m._date_range("2026-10-01","2026-10-03") == [
        "2026-10-01","2026-10-02","2026-10-03"
    ]


def test_source_labels_are_frozen():
    assert m.SOURCE_LABELS == ("learning_all","final_ab")
    assert m.REUSE_SOURCE == "reused_realtime_exhibition_snapshot_v1"


def test_script_has_no_http_and_only_historical_target_write():
    text=Path("research/historical_exhibition_reuse_pg.py").read_text(
        encoding="utf-8"
    ).lower()
    assert "requests" not in text
    assert "v2_results" not in text
    assert "v2_odds" not in text
    assert "snapshot_label='historical'" in text
    assert "learning_all" in text
    assert "final_ab" in text
    assert "on conflict(race_id,snapshot_label,lane)" in text


def test_reuse_requires_exact_six_valid_rows_and_skips_conflicts():
    stats=m._stats_sql().lower()
    write=m._write_sql().lower()
    for sql in (stats,write):
        assert "lanes=6" in sql
        assert "valid_times=6" in sql
        assert "valid_ranks=6" in sql
        assert "valid_diffs=6" in sql
        assert "conflict" in sql
    assert "when c.race_id is not null then null" in write
