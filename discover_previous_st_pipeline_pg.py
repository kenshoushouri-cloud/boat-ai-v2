# -*- coding: utf-8 -*-
"""
discover_previous_st_pipeline_pg.py

目的:
- 既存コード内で previous_st を取得・保存している実装を特定
- v2_realtime_racer_condition_snapshots の実テーブル定義を確認
- 2026-01〜03 の保存済みサンプルから、snapshot_label/source/時刻を確認
- 2026-06-01 の対象レース数を確認

読み取り専用です。DB更新・外部取得は行いません。

Railway Start Command:
    python -u discover_previous_st_pipeline_pg.py

Variables:
    DATABASE_URL=${{postgres.DATABASE_URL}}
    DISCOVER_ROOT=.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from db_pg import fetch_all, fetch_one

ROOT = Path(os.getenv("DISCOVER_ROOT", ".")).resolve()

SEARCH_TERMS = (
    "v2_realtime_racer_condition_snapshots",
    "previous_st",
    "previous_finish",
    "previous_course",
)

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".pytest_cache", ".mypy_cache", "site-packages",
}


def as_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return {"value": row}


def print_row(row: Any, prefix: str = "") -> None:
    d = as_dict(row)
    print(prefix + " ".join(f"{k}={v}" for k, v in d.items()), flush=True)


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def scan_file(path: Path) -> List[Tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    hits: List[Tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        if any(term.lower() in low for term in SEARCH_TERMS):
            hits.append((lineno, line.rstrip()))
    return hits


def classify_context(lines: List[str]) -> List[str]:
    tags = []
    joined = "\n".join(lines).lower()
    if "insert into v2_realtime_racer_condition_snapshots" in joined:
        tags.append("INSERT")
    if "update v2_realtime_racer_condition_snapshots" in joined:
        tags.append("UPDATE")
    if "on conflict" in joined:
        tags.append("UPSERT")
    if "previous_st" in joined and any(x in joined for x in ("beautifulsoup", "bs4", "requests", "httpx", "selenium")):
        tags.append("SCRAPER?")
    if "previous_st" in joined and any(x in joined for x in ("json", "payload", "api")):
        tags.append("API/PAYLOAD?")
    return tags


def main() -> None:
    print("✅ discover_previous_st_pipeline_pg.py VERSION 2026-07-20 discovery-v1", flush=True)
    print(f"ROOT={ROOT}", flush=True)
    print("読み取り専用です。DB更新・外部取得は行いません。", flush=True)

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("\n=== CODE SEARCH ===", flush=True)
    files_with_hits = 0
    total_hits = 0

    for path in sorted(iter_python_files(ROOT)):
        hits = scan_file(path)
        if not hits:
            continue

        files_with_hits += 1
        total_hits += len(hits)

        try:
            rel = path.relative_to(ROOT)
        except Exception:
            rel = path

        text_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        tags = classify_context(text_lines)

        print(f"\nFILE={rel} TAGS={','.join(tags) if tags else '-'} HITS={len(hits)}", flush=True)

        # 最大40件。各ヒットの前後2行を表示
        shown_ranges = set()
        shown = 0
        for lineno, _ in hits:
            if shown >= 40:
                print("... hit output truncated ...", flush=True)
                break
            start = max(1, lineno - 2)
            end = min(len(text_lines), lineno + 2)
            key = (start, end)
            if key in shown_ranges:
                continue
            shown_ranges.add(key)
            print(f"--- lines {start}-{end} ---", flush=True)
            for n in range(start, end + 1):
                print(f"{n:5d}: {text_lines[n-1]}", flush=True)
            shown += 1

    print(f"\ncode_files_with_hits={files_with_hits} total_hit_lines={total_hits}", flush=True)

    print("\n=== TABLE COLUMNS ===", flush=True)
    rows = fetch_all(
        """
        select
          ordinal_position,
          column_name,
          data_type,
          is_nullable,
          column_default
        from information_schema.columns
        where table_schema='public'
          and table_name='v2_realtime_racer_condition_snapshots'
        order by ordinal_position;
        """
    )
    for row in rows:
        print_row(row)

    print("\n=== INDEXES / CONSTRAINTS ===", flush=True)
    rows = fetch_all(
        """
        select indexname, indexdef
        from pg_indexes
        where schemaname='public'
          and tablename='v2_realtime_racer_condition_snapshots'
        order by indexname;
        """
    )
    for row in rows:
        print_row(row)

    print("\n=== STORED SAMPLE: 2026-01-01..2026-03-31 ===", flush=True)
    rows = fetch_all(
        """
        select
          s.race_id,
          s.lane,
          s.previous_st,
          s.previous_finish,
          s.previous_course,
          s.snapshot_label,
          s.snapshot_at,
          to_jsonb(s) as full_row
        from v2_realtime_racer_condition_snapshots s
        join v2_races r on r.race_id=s.race_id
        where r.race_date between '2026-01-01' and '2026-03-31'
          and s.previous_st is not null
        order by s.snapshot_at desc nulls last, s.race_id, s.lane
        limit 10;
        """
    )
    for row in rows:
        print_row(row)

    print("\n=== LABEL / DATE COVERAGE ===", flush=True)
    rows = fetch_all(
        """
        select
          coalesce(s.snapshot_label, '(null)') snapshot_label,
          min(r.race_date) min_date,
          max(r.race_date) max_date,
          count(*) rows,
          count(s.previous_st) previous_st_nonnull,
          count(distinct s.race_id) races
        from v2_realtime_racer_condition_snapshots s
        join v2_races r on r.race_id=s.race_id
        group by coalesce(s.snapshot_label, '(null)')
        order by min_date, snapshot_label;
        """
    )
    for row in rows:
        print_row(row)

    print("\n=== JUNE 1 TARGET ===", flush=True)
    row = fetch_one(
        """
        select
          count(*) races,
          count(distinct r.venue_id) venues,
          min(r.race_no) min_race_no,
          max(r.race_no) max_race_no
        from v2_races r
        where r.race_date='2026-06-01';
        """
    )
    print_row(row)

    print("\n=== DISCOVERY FINISHED ===", flush=True)
    print(
        "次は CODE SEARCH で特定された取得・保存関数を再利用し、"
        "2026-06-01だけを対象にした補修テストを作成します。",
        flush=True,
    )


if __name__ == "__main__":
    main()