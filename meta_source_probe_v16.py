# -*- coding: utf-8 -*-
"""
meta_source_probe_v16.py

競艇AI v2用・グレード/女子/一般カテゴリ情報の保存先確認スクリプト。

目的:
- v15で meta_unknown が多かったため、DB内にタイトル/グレード/女子戦情報がどこにあるか確認する。
- v2_races の実列名とサンプル値を表示する。
- 存在しそうなメタ情報テーブル/ビューを順番に probe する。
- どの列を v16/v17 のカテゴリ診断に使えるか判断する材料を出す。

Railway Start Command:
    python meta_source_probe_v16.py

必要Variables:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY もしくは SUPABASE_KEY
"""

from __future__ import annotations

import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

HTTP_TIMEOUT = 25
RETRY_MAX = 2
RETRY_SLEEP = 2.0

START_DATE = "2025-03-13"
END_DATE = "2026-05-31"

# 存在しそうな候補。無いものはHTTP 404/400でskip。
CANDIDATE_TABLES = [
    "v2_races",
    "v2_results",
    "v2_race_entries",
    "v2_feature_snapshots",
    "v2_events",
    "v2_event_titles",
    "v2_series",
    "v2_series_titles",
    "v2_race_titles",
    "v2_race_metadata",
    "v2_meetings",
    "v2_tournaments",
    "v2_backfill_title_missing_targets",
    "v2_backfill_missing_r1_targets",
    "v2_backfill_payout_zero_targets",
]

TEXT_LIKE_HINTS = [
    "title", "name", "grade", "class", "category", "type", "series", "event",
    "tournament", "meeting", "program", "subtitle", "race_name", "race_title",
    "is_ladies", "gender", "woman", "women", "ladies", "venus",
]

def _require_settings() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY が必要です。")


def _http_get(url: str) -> List[Dict[str, Any]]:
    last_err: Optional[Exception] = None
    for attempt in range(1, RETRY_MAX + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            return r.json()
        except Exception as e:
            last_err = e
            if attempt < RETRY_MAX:
                time.sleep(RETRY_SLEEP)
    raise RuntimeError(str(last_err))


def _rest_get(table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
    query = urllib.parse.urlencode(params, safe=",.*()")
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    return _http_get(url)


def _try_table(table: str, params: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
    try:
        return _rest_get(table, params)
    except Exception as e:
        print(f"NG {table}: {e}", flush=True)
        return None


def _columns(rows: List[Dict[str, Any]]) -> List[str]:
    cols = set()
    for r in rows:
        cols.update(r.keys())
    return sorted(cols)


def _print_rows(title: str, rows: List[Dict[str, Any]], max_rows: int = 3, max_val: int = 120) -> None:
    print(f"\n--- {title} rows={len(rows)} ---", flush=True)
    cols = _columns(rows)
    print("columns:", ", ".join(cols), flush=True)
    hint_cols = [c for c in cols if any(h.lower() in c.lower() for h in TEXT_LIKE_HINTS)]
    if hint_cols:
        print("text/category-like columns:", ", ".join(hint_cols), flush=True)
    else:
        print("text/category-like columns: none", flush=True)
    for i, r in enumerate(rows[:max_rows], start=1):
        print(f"row {i}:", flush=True)
        for c in cols:
            v = r.get(c)
            if v is None or v == "":
                continue
            s = str(v)
            if len(s) > max_val:
                s = s[:max_val] + "..."
            if c in hint_cols or c in ("race_id", "race_date", "venue_id", "race_no"):
                print(f"  {c}: {s}", flush=True)


def _probe_v2_races_columns() -> None:
    print("\n=== v2_races column/sample probe ===", flush=True)
    rows = _try_table(
        "v2_races",
        {
            "select": "*",
            "race_date": f"gte.{START_DATE}",
            "order": "race_date.asc,venue_id.asc,race_no.asc",
            "limit": "10",
        },
    )
    if rows is not None:
        _print_rows("v2_races first sample", rows, max_rows=5)

    # meta_knownになった5件のような、テキスト列を持つ行を探すため、各日付帯を少しずつ見る
    print("\n=== v2_races monthly sparse sample ===", flush=True)
    for ym in [
        "2025-03", "2025-04", "2025-05", "2025-06", "2025-07", "2025-08",
        "2025-09", "2025-10", "2025-11", "2025-12",
        "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
    ]:
        start = ym + "-01"
        rows = _try_table(
            "v2_races",
            {
                "select": "*",
                "race_date": f"gte.{start}",
                "order": "race_date.asc,venue_id.asc,race_no.asc",
                "limit": "20",
            },
        )
        if not rows:
            continue
        cols = _columns(rows)
        hint_cols = [c for c in cols if any(h.lower() in c.lower() for h in TEXT_LIKE_HINTS)]
        non_empty = {}
        for c in hint_cols:
            vals = [str(r.get(c)) for r in rows if r.get(c) not in (None, "")]
            if vals:
                non_empty[c] = vals[:3]
        if non_empty:
            print(f"{ym}: found non-empty hint columns", flush=True)
            for c, vals in non_empty.items():
                print(f"  {c}: {' | '.join(vals)}", flush=True)


def _probe_candidate_tables() -> None:
    print("\n=== candidate table probe ===", flush=True)
    for table in CANDIDATE_TABLES:
        params = {"select": "*", "limit": "5"}
        # race_id/race_dateを持ちそうなテーブルは絞る
        if table.startswith("v2_") and table not in ("v2_events", "v2_series", "v2_event_titles", "v2_series_titles", "v2_meetings", "v2_tournaments"):
            # 絞りすぎると列確認できないので、v2_races以外はlimitだけで見る
            pass
        rows = _try_table(table, params)
        if rows is None:
            continue
        if not rows:
            print(f"OK {table}: exists but empty sample", flush=True)
            continue
        _print_rows(table, rows, max_rows=2)


def main() -> None:
    _require_settings()
    print("✅ meta_source_probe_v16.py VERSION 2026-06-23 meta-source-probe", flush=True)
    print(f"SUPABASE_URL ok: {bool(SUPABASE_URL)}", flush=True)
    _probe_v2_races_columns()
    _probe_candidate_tables()
    print("\n=== probe終了 ===", flush=True)


if __name__ == "__main__":
    main()