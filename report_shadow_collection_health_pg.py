# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-21 shadow-collection-health-v1"
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except Exception:
        return default


def _table_exists(table_name: str) -> bool:
    rows = fetch_all(
        "select to_regclass(%s) as relation_name",
        (table_name,),
    )
    return bool(rows and rows[0].get("relation_name"))


def _print_grouped(
    label: str,
    table_name: str,
    sql: str,
    params: Iterable[Any],
) -> int:
    print(f"\n=== {label} ===", flush=True)
    if not _table_exists(table_name):
        print(f"table={table_name} status=MISSING_TABLE", flush=True)
        return 0

    rows = fetch_all(sql, tuple(params))
    total = 0
    if not rows:
        print(f"table={table_name} rows=0", flush=True)
        return 0

    for row in rows:
        count = _safe_int(row.get("rows"), 0)
        total += count
        details = " ".join(
            f"{key}={value}"
            for key, value in row.items()
            if key != "rows"
        )
        print(f"{details} rows={count}".strip(), flush=True)

    print(f"table={table_name} total_rows={total}", flush=True)
    return total


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(f"OK report_shadow_collection_health_pg.py VERSION {VERSION}", flush=True)
    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print("READ_ONLY=1 DB_UPDATE=0 LINE=0 PROD_CHANGE=0", flush=True)
    print(
        "0件は直ちに異常とは判定しません。収集経路・設定確認用の観測値です。",
        flush=True,
    )

    totals = {}

    totals["motor2"] = _print_grouped(
        "MOTOR2 PRE / FINAL COLLECTION",
        "v2_v24_motor2_forward_shadow",
        """
        select coalesce(run_class, '') as run_class,
               coalesce(window_name, '') as window_name,
               count(*) as rows
        from v2_v24_motor2_forward_shadow
        where race_date=%s
        group by run_class, window_name
        order by run_class, window_name
        """,
        (TARGET_DATE,),
    )

    totals["candidate"] = _print_grouped(
        "CANDIDATE FILTER / N02 PRE COLLECTION",
        "v2_candidate_filter_shadow",
        """
        select coalesce(rule_id, '') as rule_id,
               coalesce(window_name, '') as window_name,
               count(*) as rows
        from v2_candidate_filter_shadow
        where race_date=%s
        group by rule_id, window_name
        order by rule_id, window_name
        """,
        (TARGET_DATE,),
    )

    totals["n02_final"] = _print_grouped(
        "N02 FINAL SHADOW COLLECTION",
        "v2_n02_windlt4_final_shadow",
        """
        select coalesce(rule_id, '') as rule_id,
               coalesce(snapshot_label, '') as snapshot_label,
               count(*) as rows
        from v2_n02_windlt4_final_shadow
        where race_date=%s
        group by rule_id, snapshot_label
        order by rule_id, snapshot_label
        """,
        (TARGET_DATE,),
    )

    totals["exhibition_decisions"] = _print_grouped(
        "EXHIBITION SHADOW DECISIONS",
        "v2_exhibition_shadow_decisions",
        """
        select coalesce(snapshot_label, '') as snapshot_label,
               coalesce(selector_mode, '') as selector_mode,
               count(*) as rows
        from v2_exhibition_shadow_decisions
        where race_date=%s
        group by snapshot_label, selector_mode
        order by snapshot_label, selector_mode
        """,
        (TARGET_DATE,),
    )

    totals["exhibition_results"] = _print_grouped(
        "EXHIBITION SHADOW RESULTS",
        "v2_exhibition_shadow_results",
        """
        select coalesce(snapshot_label, '') as snapshot_label,
               coalesce(selector_mode, '') as selector_mode,
               count(*) as rows
        from v2_exhibition_shadow_results
        where race_date=%s
        group by snapshot_label, selector_mode
        order by snapshot_label, selector_mode
        """,
        (TARGET_DATE,),
    )

    print("\n=== SHADOW COLLECTION HEALTH SUMMARY ===", flush=True)
    for key in (
        "motor2",
        "candidate",
        "n02_final",
        "exhibition_decisions",
        "exhibition_results",
    ):
        print(f"{key}_rows={totals[key]}", flush=True)

    print(
        "NOTE: N02 PRE rows appear under rule_id=N02 in v2_candidate_filter_shadow. "
        "If absent, check CANDIDATE_SHADOW_RULES in PRE logs.",
        flush=True,
    )
    print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
