# -*- coding: utf-8 -*-
"""Research-only archive equivalence matrix for historical odds consumers.

The existing consumers are executed unchanged against normal read-only
PostgreSQL and then again with only `v2_odds_trifecta` reads intercepted by a
verified archive partition. Exact stdout equality is required. All non-odds
evidence remains in read-only PostgreSQL; no Production path imports this file.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import os
import re
from datetime import date, timedelta
from typing import Any, Callable

from research_archive_readthrough import EvidenceQuery, JsonlGzipPartitionSource


def _capture(fn: Callable[[], None]) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


def _parse_date(name: str) -> date:
    raw = os.getenv(name, "").strip()
    if not raw:
        raise RuntimeError(f"{name} is required")
    return date.fromisoformat(raw)


def _first_diff(a_text: str, b_text: str):
    a_lines = a_text.splitlines()
    b_lines = b_text.splitlines()
    for i in range(max(len(a_lines), len(b_lines))):
        a = a_lines[i] if i < len(a_lines) else "<missing>"
        b = b_lines[i] if i < len(b_lines) else "<missing>"
        if a != b:
            return i + 1, a, b
    return None


def _archive_fetcher(original_fetch_all, archive_rows):
    def fetch_all(sql: str, params: Any = ()):
        normalized = " ".join(str(sql).lower().split())
        if "from v2_odds_trifecta" not in normalized:
            return original_fetch_all(sql, params)
        if "count(" in normalized:
            raise RuntimeError("archive consumer adapter does not emulate aggregate odds SQL")
        if not isinstance(params, (tuple, list)) or len(params) != 2:
            raise RuntimeError(f"unexpected odds query params: {params!r}")
        lo, hi = str(params[0]), str(params[1])
        positive_only = "odds > 0" in normalized or "odds>0" in normalized
        rows = []
        for r in archive_rows:
            rid = str(r.get("race_id") or "")
            if not (lo <= rid < hi):
                continue
            odd = r.get("odds")
            if positive_only:
                try:
                    if float(odd or 0) <= 0:
                        continue
                except Exception:
                    continue
            rows.append({"race_id": r.get("race_id"), "ticket": r.get("ticket"), "odds": odd})
        rows.sort(key=lambda r: (str(r.get("race_id") or ""), str(r.get("ticket") or "")))
        return rows

    return fetch_all


def _compare_module(module_name: str, archive_rows) -> tuple[str, str]:
    mod = importlib.import_module(module_name)
    original_fetch_all = mod.fetch_all
    online_output = _capture(mod.main)
    mod.fetch_all = _archive_fetcher(original_fetch_all, archive_rows)
    try:
        archive_output = _capture(mod.main)
    finally:
        mod.fetch_all = original_fetch_all
    if online_output != archive_output:
        raise AssertionError(
            f"{module_name} stdout mismatch first_diff={_first_diff(online_output, archive_output)!r}"
        )
    digest = hashlib.sha256(online_output.encode("utf-8")).hexdigest()
    return online_output, digest


def main() -> None:
    manifest_path = os.getenv("PROB_CAL_BASE_ODDS_ARCHIVE_MANIFEST", "").strip()
    if not manifest_path:
        raise RuntimeError("PROB_CAL_BASE_ODDS_ARCHIVE_MANIFEST is required")
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    start = _parse_date("BACKTEST_START_DATE")
    end = _parse_date("BACKTEST_END_DATE")
    if start > end:
        raise RuntimeError("BACKTEST_START_DATE must be <= BACKTEST_END_DATE")

    source = JsonlGzipPartitionSource(manifest_path)
    query = EvidenceQuery(
        table="v2_odds_trifecta",
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )
    if not source.covers(query):
        raise RuntimeError("archive manifest does not exactly cover requested period")
    archive_rows = [dict(r) for r in source.fetch(query)]

    # Independent source row-count equality before consumer comparisons.
    prob_mod = importlib.import_module("backtest_prob_calibration_pg")
    p = start.strftime("%Y%m%d")
    np = (end + timedelta(days=1)).strftime("%Y%m%d")
    count_rows = prob_mod.fetch_all(
        "select count(*)::bigint as n from v2_odds_trifecta where race_id >= %s and race_id < %s",
        (p, np),
    )
    online_count = int((count_rows[0] if count_rows else {}).get("n") or 0)
    if online_count != len(archive_rows):
        raise AssertionError(
            f"online/archive odds row-count mismatch online={online_count} archive={len(archive_rows)}"
        )

    prob_output, prob_sha = _compare_module("backtest_prob_calibration_pg", archive_rows)
    ready = re.search(r"^ready_races=(\d+)$", prob_output, re.MULTILINE)
    tickets = re.search(r"^ticket_rows=(\d+)$", prob_output, re.MULTILINE)
    print(
        "PROB_CAL_ARCHIVE_COMPARE=PASS "
        f"period={start.isoformat()}..{end.isoformat()} "
        f"online_odds_rows={online_count} archive_odds_rows={len(archive_rows)} "
        f"ready_races={ready.group(1) if ready else 'unknown'} "
        f"ticket_rows={tickets.group(1) if tickets else 'unknown'} "
        f"stdout_sha256={prob_sha}",
        flush=True,
    )

    wf_output, wf_sha = _compare_module("backtest_n02_walkforward_pg", archive_rows)
    wf_bets = re.search(r"^N02 ALL: bets=(\d+)", wf_output, re.MULTILINE)
    print(
        "N02_WALKFORWARD_ARCHIVE_COMPARE=PASS "
        f"bets={wf_bets.group(1) if wf_bets else 'unknown'} stdout_sha256={wf_sha}",
        flush=True,
    )

    rolling_output, rolling_sha = _compare_module("backtest_n02_rolling_pg", archive_rows)
    rolling_bets = re.search(r"^N02 ALL: bets=(\d+)", rolling_output, re.MULTILINE)
    if rolling_bets is None:
        rolling_bets = re.search(r"^OVERALL: bets=(\d+)", rolling_output, re.MULTILINE)
    print(
        "N02_ROLLING_ARCHIVE_COMPARE=PASS "
        f"bets={rolling_bets.group(1) if rolling_bets else 'unknown'} stdout_sha256={rolling_sha}",
        flush=True,
    )

    # Use a split inside the archive month so both time buckets are exercised.
    os.environ["BACKTEST_SPLIT_DATE"] = "2026-07-16"
    split_output, split_sha = _compare_module("backtest_n02_time_split_pg", archive_rows)
    split_bets = re.search(r"^N02 ALL: bets=(\d+)", split_output, re.MULTILINE)
    print(
        "N02_TIME_SPLIT_ARCHIVE_COMPARE=PASS "
        f"bets={split_bets.group(1) if split_bets else 'unknown'} stdout_sha256={split_sha}",
        flush=True,
    )

    diag_output, diag_sha = _compare_module("backtest_n01_n02_diagnostics_pg", archive_rows)
    n01_bets = re.search(r"^N01: bets=(\d+)", diag_output, re.MULTILINE)
    n02_bets = re.search(r"^N02: bets=(\d+)", diag_output, re.MULTILINE)
    print(
        "N01_N02_DIAGNOSTICS_ARCHIVE_COMPARE=PASS "
        f"n01_bets={n01_bets.group(1) if n01_bets else 'unknown'} "
        f"n02_bets={n02_bets.group(1) if n02_bets else 'unknown'} "
        f"stdout_sha256={diag_sha}",
        flush=True,
    )

    filter_output, filter_sha = _compare_module("backtest_candidate_filter_rules_pg", archive_rows)
    filter_ready = re.search(r"^ready_races=(\d+)$", filter_output, re.MULTILINE)
    filter_selections = re.search(r"^rule_selections=(\d+)$", filter_output, re.MULTILINE)
    print(
        "CANDIDATE_FILTER_ARCHIVE_COMPARE=PASS "
        f"ready_races={filter_ready.group(1) if filter_ready else 'unknown'} "
        f"rule_selections={filter_selections.group(1) if filter_selections else 'unknown'} "
        f"stdout_sha256={filter_sha}",
        flush=True,
    )

    # Set the V24 historical window before base-candidate features imports that
    # module as a helper, so module-level constants are frozen to this archive month.
    os.environ["MOTOR2_BT_START_DATE"] = start.isoformat()
    os.environ["MOTOR2_BT_END_DATE"] = end.isoformat()
    os.environ["MOTOR2_BT_PROGRESS_EVERY"] = "1000000"
    os.environ["MOTOR2_BT_MAX_RACES"] = "0"

    # Base-candidate feature research uses separate environment variable names.
    os.environ["MOTOR2_BASEFEAT_START_DATE"] = start.isoformat()
    os.environ["MOTOR2_BASEFEAT_END_DATE"] = end.isoformat()
    os.environ["MOTOR2_BASEFEAT_PROGRESS_EVERY"] = "1000000"
    os.environ["MOTOR2_BASEFEAT_MAX_RACES"] = "0"
    basefeat_output, basefeat_sha = _compare_module(
        "backtest_v24_motor2_base_candidate_features_pg", archive_rows
    )
    basefeat_processed = re.search(r"^processed=(\d+)$", basefeat_output, re.MULTILINE)
    basefeat_candidates = re.search(r"^candidate_rows=(\d+)$", basefeat_output, re.MULTILINE)
    print(
        "MOTOR2_BASEFEAT_ARCHIVE_COMPARE=PASS "
        f"processed={basefeat_processed.group(1) if basefeat_processed else 'unknown'} "
        f"candidate_rows={basefeat_candidates.group(1) if basefeat_candidates else 'unknown'} "
        f"stdout_sha256={basefeat_sha}",
        flush=True,
    )

    # The helper module is already imported with the exact July window above.
    motor_output, motor_sha = _compare_module("backtest_v24_motor2_historical_pg", archive_rows)
    motor_processed = re.search(r"^processed=(\d+)$", motor_output, re.MULTILINE)
    print(
        "PROB_CAL_ARCHIVE_COMPARE=PASS consumer=v24_motor2_historical "
        f"processed={motor_processed.group(1) if motor_processed else 'unknown'} "
        f"stdout_sha256={motor_sha}",
        flush=True,
    )

    # Reaching this line means all eight unchanged historical consumers matched exactly.
    print("PROB_CAL_ARCHIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
