# -*- coding: utf-8 -*-
"""
collect_racer_course_stats_pg.py

BOAT RACE公式の「選手コース別成績」を取得し、Railway Postgresへ
日次スナップショット保存します。

保存対象（1～6コース）:
- コース別進入率
- コース別3連対率
- コース別平均ST

重要:
- 公式ページは現在時点の集計値なので、過去レースへ遡って適用しません。
- 今後の日次スナップショットとして蓄積し、shadow/A-B検証に使用します。
- 本番判定・LINE通知・購入処理には影響しません。

Start Command:
    python -u collect_racer_course_stats_pg.py
"""
from __future__ import annotations

import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from db_pg import execute, fetch_all, upsert_rows

JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
RACER_STATS_SCOPE = os.getenv("RACER_STATS_SCOPE", "target_date").strip().lower()
RACER_STATS_LOOKBACK_DAYS = max(1, int(os.getenv("RACER_STATS_LOOKBACK_DAYS", "7")))
RACER_STATS_WORKERS = max(1, int(os.getenv("RACER_STATS_WORKERS", "4")))
RACER_STATS_SLEEP_SEC = max(0.0, float(os.getenv("RACER_STATS_SLEEP_SEC", "0.10")))
RACER_STATS_LIMIT = max(0, int(os.getenv("RACER_STATS_LIMIT", "0")))
HTTP_TIMEOUT = max(5, int(os.getenv("HTTP_TIMEOUT", "35")))
RETRY_MAX = max(0, int(os.getenv("RETRY_MAX", "2")))
RETRY_SLEEP = max(0.0, float(os.getenv("RETRY_SLEEP", "1.5")))
OFFICIAL_URL = "https://www.boatrace.jp/owpc/pc/data/racersearch/course?toban={racer_number}"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; boat-ai-racer-course-stats-pg/1.0)",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
})


def _now_iso() -> str:
    return datetime.now(JST).isoformat()


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        text = unicodedata.normalize("NFKC", str(value)).replace("%", "").replace(",", "").strip()
        if not text or text in {"-", "--"}:
            return None
        return float(text)
    except Exception:
        return None


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _require_settings() -> None:
    print("✅ collect_racer_course_stats_pg.py VERSION 2026-07-15 snapshot-v1", flush=True)
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")


def _ensure_schema() -> None:
    ddl = [
        "create table if not exists v2_racer_course_stats_snapshots (id bigserial primary key);",
        "alter table v2_racer_course_stats_snapshots add column if not exists racer_number integer;",
        "alter table v2_racer_course_stats_snapshots add column if not exists snapshot_date date;",
        "alter table v2_racer_course_stats_snapshots add column if not exists course integer;",
        "alter table v2_racer_course_stats_snapshots add column if not exists entry_rate numeric;",
        "alter table v2_racer_course_stats_snapshots add column if not exists top3_rate numeric;",
        "alter table v2_racer_course_stats_snapshots add column if not exists avg_st numeric;",
        "alter table v2_racer_course_stats_snapshots add column if not exists source text;",
        "alter table v2_racer_course_stats_snapshots add column if not exists raw jsonb;",
        "alter table v2_racer_course_stats_snapshots add column if not exists created_at timestamptz;",
        "alter table v2_racer_course_stats_snapshots add column if not exists updated_at timestamptz;",
        "create unique index if not exists uq_v2_racer_course_stats_snapshot on v2_racer_course_stats_snapshots (racer_number, snapshot_date, course);",
        "create index if not exists ix_v2_racer_course_stats_snapshot_date on v2_racer_course_stats_snapshots (snapshot_date);",
    ]
    for sql in ddl:
        execute(sql)


def _fetch_html(racer_number: int) -> Optional[str]:
    url = OFFICIAL_URL.format(racer_number=racer_number)
    last_error = None
    for attempt in range(RETRY_MAX + 1):
        try:
            response = SESSION.get(url, timeout=HTTP_TIMEOUT)
            if response.status_code == 404:
                return None
            if not response.ok:
                last_error = f"HTTP {response.status_code}"
                time.sleep(RETRY_SLEEP * (attempt + 1))
                continue
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(RETRY_SLEEP * (attempt + 1))
    print(f"⚠️ fetch failed racer={racer_number}: {last_error}", flush=True)
    return None


def _extract_six_values_from_section(text: str, start_label: str, end_labels: List[str], *, percent: bool) -> List[Optional[float]]:
    start = text.find(start_label)
    if start < 0:
        return []
    segment = text[start + len(start_label):]
    end_positions = [segment.find(label) for label in end_labels if segment.find(label) >= 0]
    if end_positions:
        segment = segment[:min(end_positions)]
    pattern = r"(\d{1,3}(?:\.\d+)?)\s*%" if percent else r"(?<!\d)(0\.\d{1,2})(?!\d)"
    values = [_safe_float(v) for v in re.findall(pattern, segment)]
    return values[:6] if len(values) >= 6 else []


def _extract_table_values(soup: BeautifulSoup, heading_text: str, *, percent: bool) -> List[Optional[float]]:
    heading = soup.find(lambda tag: getattr(tag, "name", None) and heading_text in _normalize_text(tag.get_text(" ", strip=True)))
    if heading is None:
        return []
    candidates: List[str] = []
    node = heading
    for _ in range(12):
        node = node.find_next()
        if node is None:
            break
        text = _normalize_text(node.get_text(" ", strip=True))
        if text:
            candidates.append(text)
        if len(" ".join(candidates)) > 1500:
            break
    segment = " ".join(candidates)
    pattern = r"(\d{1,3}(?:\.\d+)?)\s*%" if percent else r"(?<!\d)(0\.\d{1,2})(?!\d)"
    values = [_safe_float(v) for v in re.findall(pattern, segment)]
    return values[:6] if len(values) >= 6 else []


def parse_course_stats(html: str, racer_number: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    full_text = _normalize_text(soup.get_text(" ", strip=True))

    entry_rates = _extract_table_values(soup, "コース別進入率", percent=True)
    top3_rates = _extract_table_values(soup, "コース別3連対率", percent=True)
    avg_st_values = _extract_table_values(soup, "コース別平均スタートタイミング", percent=False)

    if len(entry_rates) < 6:
        entry_rates = _extract_six_values_from_section(full_text, "コース別進入率", ["コース別3連対率", "コース別平均スタートタイミング"], percent=True)
    if len(top3_rates) < 6:
        top3_rates = _extract_six_values_from_section(full_text, "コース別3連対率", ["コース別平均スタートタイミング", "本日出走予定"], percent=True)
    if len(avg_st_values) < 6:
        avg_st_values = _extract_six_values_from_section(full_text, "コース別平均スタートタイミング", ["本日出走予定", "出場予定", "過去3節成績"], percent=False)

    debug = {
        "racer_number": racer_number,
        "entry_count": len(entry_rates),
        "top3_count": len(top3_rates),
        "avg_st_count": len(avg_st_values),
        "text_head": full_text[:1200],
    }
    if not (len(entry_rates) == 6 and len(top3_rates) == 6 and len(avg_st_values) == 6):
        return [], debug

    now_iso = _now_iso()
    rows = []
    for course in range(1, 7):
        rows.append({
            "racer_number": racer_number,
            "snapshot_date": TARGET_DATE,
            "course": course,
            "entry_rate": entry_rates[course - 1],
            "top3_rate": top3_rates[course - 1],
            "avg_st": avg_st_values[course - 1],
            "source": "boatrace_official_racer_course",
            "raw": {
                "entry_rate": entry_rates[course - 1],
                "top3_rate": top3_rates[course - 1],
                "avg_st": avg_st_values[course - 1],
            },
            "created_at": now_iso,
            "updated_at": now_iso,
        })
    return rows, debug


def _target_racer_numbers() -> List[int]:
    if RACER_STATS_SCOPE == "recent":
        start_date = (datetime.strptime(TARGET_DATE, "%Y-%m-%d") - timedelta(days=RACER_STATS_LOOKBACK_DAYS - 1)).strftime("%Y-%m-%d")
        rows = fetch_all(
            """
            select distinct e.racer_number
            from v2_race_entries e
            join v2_races r on r.race_id = e.race_id
            where r.race_date >= %s and r.race_date <= %s
              and e.racer_number is not null
            order by e.racer_number;
            """,
            (start_date, TARGET_DATE),
        )
    else:
        rows = fetch_all(
            """
            select distinct e.racer_number
            from v2_race_entries e
            join v2_races r on r.race_id = e.race_id
            where r.race_date = %s and e.racer_number is not null
            order by e.racer_number;
            """,
            (TARGET_DATE,),
        )
    numbers = []
    for row in rows:
        try:
            number = int(row.get("racer_number"))
        except Exception:
            continue
        if 1000 <= number <= 9999:
            numbers.append(number)
    numbers = sorted(set(numbers))
    return numbers[:RACER_STATS_LIMIT] if RACER_STATS_LIMIT > 0 else numbers


def _collect_one(racer_number: int) -> Tuple[int, List[Dict[str, Any]], Dict[str, Any], Optional[str]]:
    html = _fetch_html(racer_number)
    if not html:
        return racer_number, [], {}, "no_html"
    rows, debug = parse_course_stats(html, racer_number)
    if RACER_STATS_SLEEP_SEC > 0:
        time.sleep(RACER_STATS_SLEEP_SEC)
    if len(rows) != 6:
        return racer_number, [], debug, "parse_incomplete"
    return racer_number, rows, debug, None


def main() -> None:
    _require_settings()
    _ensure_schema()
    racer_numbers = _target_racer_numbers()
    print(f"TARGET_DATE={TARGET_DATE} SCOPE={RACER_STATS_SCOPE} LOOKBACK_DAYS={RACER_STATS_LOOKBACK_DAYS}", flush=True)
    print(f"target_racers={len(racer_numbers)} WORKERS={RACER_STATS_WORKERS}", flush=True)
    print("本番判定・LINE通知・購入処理は変更しません。", flush=True)

    saved_rows = 0
    success = 0
    failed: List[Tuple[int, str, Dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=RACER_STATS_WORKERS) as executor:
        futures = {executor.submit(_collect_one, n): n for n in racer_numbers}
        for index, future in enumerate(as_completed(futures), start=1):
            racer_number = futures[future]
            try:
                _, rows, debug, error = future.result()
            except Exception as exc:
                failed.append((racer_number, f"{type(exc).__name__}: {exc}", {}))
                continue
            if error:
                failed.append((racer_number, error, debug))
            else:
                saved_rows += upsert_rows(
                    "v2_racer_course_stats_snapshots",
                    rows,
                    ["racer_number", "snapshot_date", "course"],
                )
                success += 1
            if index % 50 == 0 or index == len(racer_numbers):
                print(f"progress={index}/{len(racer_numbers)} success={success} failed={len(failed)} saved_rows={saved_rows}", flush=True)

    coverage = success / len(racer_numbers) * 100.0 if racer_numbers else 0.0
    print("\n=== racer course stats collection summary ===", flush=True)
    print(f"target_racers={len(racer_numbers)}", flush=True)
    print(f"success_racers={success}", flush=True)
    print(f"failed_racers={len(failed)}", flush=True)
    print(f"saved_rows={saved_rows}", flush=True)
    print(f"coverage={coverage:.1f}%", flush=True)
    if failed:
        print("--- failed samples ---", flush=True)
        for racer_number, error, debug in failed[:20]:
            print(
                f"racer={racer_number} error={error} counts={debug.get('entry_count', '-')}/{debug.get('top3_count', '-')}/{debug.get('avg_st_count', '-')}",
                flush=True,
            )
    print("=== racer course stats collection finished ===", flush=True)


if __name__ == "__main__":
    main()