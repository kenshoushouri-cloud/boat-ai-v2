# -*- coding: utf-8 -*-
"""
v22_racer_course_shadow_pg.py

選手コース別成績を使ったshadow順位を保存します。
本番BUY/WATCH/SKIP、LINE通知、購入処理は変更しません。

前提:
- v2_racer_course_stats_snapshots に日次スナップショットがある
- v2_race_entries / v2_odds_trifecta が保存済み
- TARGET_RACE_IDS を指定すれば、そのレースだけ処理する

Start Command:
    python -u v22_racer_course_shadow_pg.py

Variables:
    DATABASE_URL
    TARGET_DATE=YYYY-MM-DD
    TARGET_RACE_IDS=comma-separated race_ids
    SNAPSHOT_LABEL=final_ab
    SELECTOR_MODE=ab
    RACER_COURSE_SHADOW_WEIGHT=0.20
"""

from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from db_pg import execute, fetch_all, upsert_rows

import v22_realtime_decision_engine_pg as base

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
TARGET_RACE_IDS_RAW = os.getenv("TARGET_RACE_IDS", "").strip()
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"
RACER_COURSE_SHADOW_WEIGHT = float(
    os.getenv("RACER_COURSE_SHADOW_WEIGHT", "0.20")
)
SAVE_SHADOW = os.getenv("SAVE_RACER_COURSE_SHADOW", "1").strip() not in (
    "0", "false", "False", "no", "NO"
)

TARGET_RACE_IDS = [
    value.strip()
    for value in TARGET_RACE_IDS_RAW.split(",")
    if value.strip()
]


def _require_settings() -> None:
    print(
        "✅ v22_racer_course_shadow_pg.py "
        "VERSION 2026-07-15 racer-course-shadow-v1",
        flush=True,
    )
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")


def _ensure_schema() -> None:
    ddl = [
        """
        create table if not exists v2_racer_course_shadow_rankings (
            id bigserial primary key
        );
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists race_id text;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists race_date date;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists venue_id text;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists race_no integer;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists snapshot_label text;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists selector_mode text;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists ticket text;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists odds numeric;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists market_rank integer;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists baseline_prob numeric;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists baseline_prob_rank integer;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists shadow_prob numeric;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists shadow_prob_rank integer;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists rank_delta integer;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists baseline_candidate boolean;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists shadow_candidate boolean;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists candidate_change text;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists course_stats_coverage integer;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists shadow_weight numeric;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists raw jsonb;
        """,
        """
        alter table v2_racer_course_shadow_rankings
        add column if not exists updated_at timestamptz;
        """,
        """
        create unique index if not exists
        uq_v2_racer_course_shadow_rankings
        on v2_racer_course_shadow_rankings
        (race_id, snapshot_label, selector_mode, ticket);
        """,
        """
        create index if not exists
        ix_v2_racer_course_shadow_rankings_date
        on v2_racer_course_shadow_rankings
        (race_date);
        """,
    ]
    for sql in ddl:
        execute(sql)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _target_races() -> List[Dict[str, Any]]:
    if TARGET_RACE_IDS_RAW and not TARGET_RACE_IDS:
        print("今回の対象レースは0件です。", flush=True)
        return []

    if TARGET_RACE_IDS:
        return fetch_all(
            """
            select *
            from v2_races
            where race_id = any(%s)
            order by venue_id, race_no;
            """,
            (TARGET_RACE_IDS,),
        )

    return fetch_all(
        """
        select *
        from v2_races
        where race_date = %s
        order by venue_id, race_no;
        """,
        (TARGET_DATE,),
    )


def _fetch_entries(race_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not race_ids:
        return {}
    rows = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id = any(%s)
        order by race_id, lane;
        """,
        (race_ids,),
    )
    out: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row.get("race_id")), []).append(row)
    return out


def _fetch_odds(race_ids: List[str]) -> Dict[str, Dict[str, float]]:
    if not race_ids:
        return {}
    rows = fetch_all(
        """
        select race_id, ticket, odds
        from v2_odds_trifecta
        where race_id = any(%s)
        order by race_id, ticket;
        """,
        (race_ids,),
    )
    out: Dict[str, Dict[str, float]] = {}
    for row in rows:
        ticket = base._norm_ticket(row.get("ticket"))
        odds = _safe_float(row.get("odds"), 0.0)
        if ticket and odds > 0:
            out.setdefault(str(row.get("race_id")), {})[ticket] = odds
    return out


def _fetch_course_stats(
    entries_by_race: Dict[str, List[Dict[str, Any]]]
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    racer_numbers = sorted({
        _safe_int(entry.get("racer_number"), 0)
        for entries in entries_by_race.values()
        for entry in entries
        if _safe_int(entry.get("racer_number"), 0) > 0
    })
    if not racer_numbers:
        return {}

    rows = fetch_all(
        """
        select distinct on (racer_number, course)
            racer_number,
            course,
            snapshot_date,
            entry_rate,
            top3_rate,
            avg_st
        from v2_racer_course_stats_snapshots
        where racer_number = any(%s)
          and snapshot_date <= %s
        order by
            racer_number,
            course,
            snapshot_date desc;
        """,
        (racer_numbers, TARGET_DATE),
    )

    out: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for row in rows:
        key = (
            _safe_int(row.get("racer_number"), 0),
            _safe_int(row.get("course"), 0),
        )
        out[key] = row
    return out


def _course_adjustment(stat: Optional[Dict[str, Any]]) -> float:
    if not stat:
        return 0.0

    entry_rate = _safe_float(stat.get("entry_rate"), 16.67)
    top3_rate = _safe_float(stat.get("top3_rate"), 33.33)
    avg_st = _safe_float(stat.get("avg_st"), 0.18)

    top3_component = max(-1.0, min(1.0, (top3_rate - 33.33) / 40.0))
    st_component = max(-1.0, min(1.0, (0.18 - avg_st) / 0.08))
    familiarity_component = max(
        -1.0,
        min(1.0, (entry_rate - 16.67) / 20.0),
    )

    combined = (
        top3_component * 0.55
        + st_component * 0.30
        + familiarity_component * 0.15
    )
    return combined * RACER_COURSE_SHADOW_WEIGHT


def _shadow_rank_candidates(
    entries: List[Dict[str, Any]],
    venue_id: str,
    odds: Dict[str, float],
    course_stats: Dict[Tuple[int, int], Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, Dict[int, float]]:
    by_lane = base._entry_by_lane(entries)

    raw: Dict[int, float] = {}
    adjustments: Dict[int, float] = {}
    coverage = 0

    for lane in range(1, 7):
        entry = by_lane[lane]
        racer_number = _safe_int(entry.get("racer_number"), 0)
        stat = course_stats.get((racer_number, lane))
        if stat:
            coverage += 1
        adjustment = _course_adjustment(stat)
        adjustments[lane] = adjustment
        raw[lane] = (
            base._lane_raw_strength(entry, lane, venue_id)
            + adjustment
        )

    weights = {
        lane: math.exp(raw[lane] / base.PROB_TEMP)
        for lane in range(1, 7)
    }
    total = sum(weights.values())

    rows: List[Dict[str, Any]] = []
    for a in range(1, 7):
        pa = weights[a] / total
        total_b = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / total_b
            total_c = total_b - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                ticket = f"{a}-{b}-{c}"
                odd = _safe_float(odds.get(ticket), 0.0)
                if odd <= 0:
                    continue
                prob = pa * pb * (weights[c] / total_c)
                rows.append(
                    {
                        "ticket": ticket,
                        "prob": prob,
                        "odds": odd,
                        "raw_ev": prob * odd,
                    }
                )

    for index, row in enumerate(
        sorted(rows, key=lambda x: (x["odds"], -x["prob"])),
        start=1,
    ):
        row["market_rank"] = index

    for index, row in enumerate(
        sorted(rows, key=lambda x: x["prob"], reverse=True),
        start=1,
    ):
        row["prob_rank"] = index

    rows.sort(key=lambda x: x["prob"], reverse=True)
    return rows, coverage, adjustments


def _is_low_core_candidate(row: Dict[str, Any]) -> bool:
    return (
        11 <= _safe_int(row.get("prob_rank"), 999) <= 20
        and _safe_int(row.get("market_rank"), 999) == 1
        and 3.0 <= _safe_float(row.get("odds"), 0.0) < 5.0
    )


def _change_label(
    baseline_candidate: bool,
    shadow_candidate: bool,
) -> str:
    if baseline_candidate and shadow_candidate:
        return "kept"
    if baseline_candidate and not shadow_candidate:
        return "removed"
    if not baseline_candidate and shadow_candidate:
        return "added"
    return "none"


def main() -> None:
    _require_settings()
    _ensure_schema()

    print(
        f"TARGET_DATE={TARGET_DATE} "
        f"SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"SELECTOR_MODE={SELECTOR_MODE} "
        f"RACER_COURSE_SHADOW_WEIGHT={RACER_COURSE_SHADOW_WEIGHT}",
        flush=True,
    )
    print(
        "本番判定・LINE通知・購入処理は変更しません。",
        flush=True,
    )

    races = _target_races()
    race_ids = [str(race.get("race_id")) for race in races]
    entries_by_race = _fetch_entries(race_ids)
    odds_by_race = _fetch_odds(race_ids)
    course_stats = _fetch_course_stats(entries_by_race)

    save_rows: List[Dict[str, Any]] = []
    ready_races = 0
    skipped_entries = 0
    skipped_odds = 0
    full_coverage_races = 0
    rank_improved = 0
    rank_worsened = 0
    rank_same = 0
    added = 0
    removed = 0
    kept = 0
    none = 0

    now_iso = datetime.now(JST).isoformat()

    for race in races:
        race_id = str(race.get("race_id"))
        venue_id = str(
            race.get("venue_id") or race.get("venue_code") or ""
        ).zfill(2)
        race_no = _safe_int(race.get("race_no"), 0)

        entries = entries_by_race.get(race_id, [])
        odds = odds_by_race.get(race_id, {})

        if len(base._entry_by_lane(entries)) != 6:
            skipped_entries += 1
            continue
        if len(odds) < 100:
            skipped_odds += 1
            continue

        ready_races += 1

        baseline_rows = base._rank_candidates(entries, venue_id, odds)
        shadow_rows, coverage, adjustments = _shadow_rank_candidates(
            entries,
            venue_id,
            odds,
            course_stats,
        )
        if coverage == 6:
            full_coverage_races += 1

        baseline_by_ticket = {
            str(row.get("ticket")): row
            for row in baseline_rows
        }
        shadow_by_ticket = {
            str(row.get("ticket")): row
            for row in shadow_rows
        }

        for ticket, baseline_row in baseline_by_ticket.items():
            shadow_row = shadow_by_ticket.get(ticket)
            if not shadow_row:
                continue

            baseline_rank = _safe_int(
                baseline_row.get("prob_rank"),
                999,
            )
            shadow_rank = _safe_int(
                shadow_row.get("prob_rank"),
                999,
            )
            rank_delta = baseline_rank - shadow_rank

            if rank_delta > 0:
                rank_improved += 1
            elif rank_delta < 0:
                rank_worsened += 1
            else:
                rank_same += 1

            baseline_candidate = _is_low_core_candidate(
                baseline_row
            )
            shadow_candidate = _is_low_core_candidate(
                shadow_row
            )
            change = _change_label(
                baseline_candidate,
                shadow_candidate,
            )

            if change == "added":
                added += 1
            elif change == "removed":
                removed += 1
            elif change == "kept":
                kept += 1
            else:
                none += 1

            save_rows.append(
                {
                    "race_id": race_id,
                    "race_date": TARGET_DATE,
                    "venue_id": venue_id,
                    "race_no": race_no,
                    "snapshot_label": SNAPSHOT_LABEL,
                    "selector_mode": SELECTOR_MODE,
                    "ticket": ticket,
                    "odds": _safe_float(
                        baseline_row.get("odds"),
                        0.0,
                    ),
                    "market_rank": _safe_int(
                        baseline_row.get("market_rank"),
                        999,
                    ),
                    "baseline_prob": _safe_float(
                        baseline_row.get("prob"),
                        0.0,
                    ),
                    "baseline_prob_rank": baseline_rank,
                    "shadow_prob": _safe_float(
                        shadow_row.get("prob"),
                        0.0,
                    ),
                    "shadow_prob_rank": shadow_rank,
                    "rank_delta": rank_delta,
                    "baseline_candidate": baseline_candidate,
                    "shadow_candidate": shadow_candidate,
                    "candidate_change": change,
                    "course_stats_coverage": coverage,
                    "shadow_weight": RACER_COURSE_SHADOW_WEIGHT,
                    "raw": {
                        "lane_adjustments": adjustments,
                    },
                    "updated_at": now_iso,
                }
            )

    saved = (
        upsert_rows(
            "v2_racer_course_shadow_rankings",
            save_rows,
            [
                "race_id",
                "snapshot_label",
                "selector_mode",
                "ticket",
            ],
        )
        if SAVE_SHADOW and save_rows
        else 0
    )

    print("\n=== racer course shadow summary ===", flush=True)
    print(f"races={len(races)} ready_races={ready_races}", flush=True)
    print(
        f"skipped_entries={skipped_entries} "
        f"skipped_odds={skipped_odds}",
        flush=True,
    )
    print(
        f"full_coverage_races={full_coverage_races}/"
        f"{ready_races}",
        flush=True,
    )
    print(f"saved_rows={saved}", flush=True)
    print(
        f"rank_improved={rank_improved} "
        f"rank_worsened={rank_worsened} "
        f"rank_same={rank_same}",
        flush=True,
    )
    print(
        f"candidate_added={added} "
        f"candidate_removed={removed} "
        f"candidate_kept={kept} "
        f"candidate_none={none}",
        flush=True,
    )
    print("=== racer course shadow finished ===", flush=True)


if __name__ == "__main__":
    main()