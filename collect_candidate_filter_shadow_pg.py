# -*- coding: utf-8 -*-
"""
collect_candidate_filter_shadow_pg.py

候補フィルターShadow専用。
v24_pre_candidate_notifier_pg.py と同じ確率計算を利用し、
有望ルールに一致した買い目を専用テーブルへ保存します。

VERSION 2026-08-13 phase4-shadow-v2.3

重要:
- LINE通知しません。
- v2_realtime_decisionsを変更しません。
- v2_exhibition_shadow_decisionsを変更しません。
- 購入処理はありません。
- 同一race_id・rule_idは「最新の選択1件」に更新します。
  morning/day/nightの重複枠や再実行で買い目が変わっても、
  同じレース・同じルールを複数点として数えません。

通常は run_pre_window_pg.py から、v24仮候補処理の後に実行します。

Start Command（単体テスト用）:
    python -u collect_candidate_filter_shadow_pg.py

Variables:
    DATABASE_URL
    TARGET_DATE=YYYY-MM-DD
    TARGET_RACE_IDS=comma separated race ids
    WINDOW_NAME=morning|day|night

任意:
    CANDIDATE_SHADOW_ENABLED=1
    CANDIDATE_SHADOW_REQUIRE_COMPLETE_ODDS=1
    CANDIDATE_SHADOW_RULES=S01,S02,S03,S04,S05
    CANDIDATE_SHADOW_DISABLED_RULES=
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db_pg import execute, fetch_all, upsert_rows
import v24_pre_candidate_notifier_pg as v24

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
WINDOW_NAME = (
    os.getenv("WINDOW_NAME")
    or os.getenv("WINDOW_MODE")
    or os.getenv("PRE_SESSION")
    or "unknown"
).strip().lower()

ENABLED = os.getenv("CANDIDATE_SHADOW_ENABLED", "1").strip().lower() in {
    "1", "true", "yes", "on"
}
REQUIRE_COMPLETE_ODDS = (
    os.getenv("CANDIDATE_SHADOW_REQUIRE_COMPLETE_ODDS", "1")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)


def _parse_rule_ids(raw: str) -> set[str]:
    return {
        value.strip().upper()
        for value in re.split(r"[,\s]+", raw or "")
        if value.strip()
    }


RULES_ENV_RAW = os.getenv(
    "CANDIDATE_SHADOW_RULES",
    "S01,S02,S03,S04,S05",
)
DISABLED_RULES_ENV_RAW = os.getenv(
    "CANDIDATE_SHADOW_DISABLED_RULES",
    "",
)

REQUESTED_RULE_IDS = _parse_rule_ids(RULES_ENV_RAW)
DISABLED_RULE_IDS = _parse_rule_ids(DISABLED_RULES_ENV_RAW)

RULES = [
    {
        "rule_id": "S01",
        "description": "pr6-15 mr21-30 odds30-50 R01-09 standard EV",
        "pr_min": 6, "pr_max": 15,
        "mr_min": 21, "mr_max": 30,
        "odds_min": 30.0, "odds_max": 50.0,
        "race_nos": set(range(1, 10)),
        "venue_style": "standard",
        "event_category": "ALL",
        "select_mode": "ev",
    },
    {
        "rule_id": "S02",
        "description": "pr16-30 mr6-10 odds20-30 R07-09 in_strong prob",
        "pr_min": 16, "pr_max": 30,
        "mr_min": 6, "mr_max": 10,
        "odds_min": 20.0, "odds_max": 30.0,
        "race_nos": {7, 8, 9},
        "venue_style": "in_strong",
        "event_category": "ALL",
        "select_mode": "prob",
    },
    {
        "rule_id": "S03",
        "description": "pr11-25 mr6-10 odds30-50 R07-09 standard EV",
        "pr_min": 11, "pr_max": 25,
        "mr_min": 6, "mr_max": 10,
        "odds_min": 30.0, "odds_max": 50.0,
        "race_nos": {7, 8, 9},
        "venue_style": "standard",
        "event_category": "ALL",
        "select_mode": "ev",
    },
    {
        "rule_id": "S04",
        "description": "pr1-5 mr11-20 odds20-30 R01-03 all EV",
        "pr_min": 1, "pr_max": 5,
        "mr_min": 11, "mr_max": 20,
        "odds_min": 20.0, "odds_max": 30.0,
        "race_nos": {1, 2, 3},
        "venue_style": "ALL",
        "event_category": "ALL",
        "select_mode": "ev",
    },
    {
        "rule_id": "S05",
        "description": "pr1-5 mr1-5 odds10-20 all_ladies prob",
        "pr_min": 1, "pr_max": 5,
        "mr_min": 1, "mr_max": 5,
        "odds_min": 10.0, "odds_max": 20.0,
        "race_nos": set(range(1, 13)),
        "venue_style": "ALL",
        "event_category": "all_ladies",
        "select_mode": "prob",
    },
    {
        "rule_id": "N01",
        "description": "Phase4 A_STABLE pr11-25 mr2-5 odds3-6 R07-12 EV",
        "pr_min": 11, "pr_max": 25,
        "mr_min": 2, "mr_max": 5,
        "odds_min": 3.0, "odds_max": 6.0,
        "race_nos": set(range(7, 13)),
        "venue_style": "ALL",
        "event_category": "ALL",
        "select_mode": "ev",
    },
    {
        "rule_id": "N02",
        "description": "Phase4 B_PROFIT pr11-20 mr2-5 odds3-6 R07-10 EV",
        "pr_min": 11, "pr_max": 20,
        "mr_min": 2, "mr_max": 5,
        "odds_min": 3.0, "odds_max": 6.0,
        "race_nos": set(range(7, 11)),
        "venue_style": "ALL",
        "event_category": "ALL",
        "select_mode": "ev",
    },
]


ALL_RULE_IDS = {str(rule["rule_id"]).upper() for rule in RULES}
UNKNOWN_REQUESTED_RULE_IDS = sorted(REQUESTED_RULE_IDS - ALL_RULE_IDS)
UNKNOWN_DISABLED_RULE_IDS = sorted(DISABLED_RULE_IDS - ALL_RULE_IDS)

ACTIVE_RULE_IDS = (
    ALL_RULE_IDS if not REQUESTED_RULE_IDS else REQUESTED_RULE_IDS & ALL_RULE_IDS
) - DISABLED_RULE_IDS

ACTIVE_RULES = [
    rule for rule in RULES
    if str(rule["rule_id"]).upper() in ACTIVE_RULE_IDS
]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _target_race_ids() -> set[str]:
    raw = (os.getenv("TARGET_RACE_IDS") or "").strip()
    if not raw:
        return set()
    return {
        value.strip()
        for value in re.split(r"[,\s]+", raw)
        if value.strip()
    }


def _ensure_schema() -> None:
    ddl = [
        """
        create table if not exists v2_candidate_filter_shadow (
            id bigserial primary key
        );
        """,
        "alter table v2_candidate_filter_shadow add column if not exists race_id text;",
        "alter table v2_candidate_filter_shadow add column if not exists race_date date;",
        "alter table v2_candidate_filter_shadow add column if not exists venue_id text;",
        "alter table v2_candidate_filter_shadow add column if not exists race_no integer;",
        "alter table v2_candidate_filter_shadow add column if not exists window_name text;",
        "alter table v2_candidate_filter_shadow add column if not exists rule_id text;",
        "alter table v2_candidate_filter_shadow add column if not exists rule_description text;",
        "alter table v2_candidate_filter_shadow add column if not exists ticket text;",
        "alter table v2_candidate_filter_shadow add column if not exists odds numeric;",
        "alter table v2_candidate_filter_shadow add column if not exists prob numeric;",
        "alter table v2_candidate_filter_shadow add column if not exists prob_rank integer;",
        "alter table v2_candidate_filter_shadow add column if not exists market_rank integer;",
        "alter table v2_candidate_filter_shadow add column if not exists raw_ev numeric;",
        "alter table v2_candidate_filter_shadow add column if not exists venue_style text;",
        "alter table v2_candidate_filter_shadow add column if not exists event_category text;",
        "alter table v2_candidate_filter_shadow add column if not exists event_day_no integer;",
        "alter table v2_candidate_filter_shadow add column if not exists snapshot_at timestamptz;",
        "alter table v2_candidate_filter_shadow add column if not exists result_ticket text;",
        "alter table v2_candidate_filter_shadow add column if not exists payout_yen integer;",
        "alter table v2_candidate_filter_shadow add column if not exists hit boolean;",
        "alter table v2_candidate_filter_shadow add column if not exists investment_yen integer default 100;",
        "alter table v2_candidate_filter_shadow add column if not exists return_yen integer;",
        "alter table v2_candidate_filter_shadow add column if not exists evaluated_at timestamptz;",
        "alter table v2_candidate_filter_shadow add column if not exists evaluation_status text;",
        "alter table v2_candidate_filter_shadow add column if not exists evaluation_note text;",
        "alter table v2_candidate_filter_shadow add column if not exists raw jsonb;",
        "alter table v2_candidate_filter_shadow add column if not exists created_at timestamptz default now();",
        "alter table v2_candidate_filter_shadow add column if not exists updated_at timestamptz;",
    ]
    for sql in ddl:
        execute(sql)

    # v1の「race_id・rule_id・ticket」単位の一意制約を廃止。
    execute(
        "drop index if exists uq_v2_candidate_filter_shadow_main;"
    )

    # 既に重複がある場合は、最新snapshotを残して整理する。
    execute(
        """
        delete from v2_candidate_filter_shadow old_row
        using v2_candidate_filter_shadow keep_row
        where old_row.race_id = keep_row.race_id
          and old_row.rule_id = keep_row.rule_id
          and (
              coalesce(old_row.snapshot_at, old_row.updated_at, old_row.created_at)
              <
              coalesce(keep_row.snapshot_at, keep_row.updated_at, keep_row.created_at)
              or (
                  coalesce(old_row.snapshot_at, old_row.updated_at, old_row.created_at)
                  =
                  coalesce(keep_row.snapshot_at, keep_row.updated_at, keep_row.created_at)
                  and old_row.id < keep_row.id
              )
          );
        """
    )

    execute(
        """
        create unique index if not exists
        uq_v2_candidate_filter_shadow_race_rule
        on v2_candidate_filter_shadow (race_id, rule_id);
        """
    )
    execute(
        """
        create index if not exists ix_v2_candidate_filter_shadow_date
        on v2_candidate_filter_shadow (race_date, rule_id);
        """
    )


def _fetch_day_rows():
    day_prefix = TARGET_DATE.replace("-", "")
    next_prefix = (
        datetime.strptime(TARGET_DATE, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y%m%d")

    races = fetch_all(
        """
        select *
        from v2_races
        where race_date=%s
        order by venue_id, race_no;
        """,
        (TARGET_DATE,),
    )

    target_ids = _target_race_ids()
    if target_ids:
        races = [
            row for row in races
            if str(row.get("race_id") or "") in target_ids
        ]

    entries = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id, lane;
        """,
        (day_prefix, next_prefix),
    )

    odds = fetch_all(
        """
        select race_id,ticket,odds
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        order by race_id,ticket;
        """,
        (day_prefix, next_prefix),
    )

    entries_by: Dict[str, List[Dict[str, Any]]] = {}
    for row in entries:
        entries_by.setdefault(str(row.get("race_id")), []).append(row)

    odds_by: Dict[str, Dict[str, float]] = {}
    for row in odds:
        race_id = str(row.get("race_id") or "")
        ticket = v24._norm_ticket(row.get("ticket"))
        odd = _safe_float(row.get("odds"), 0.0)
        if race_id and ticket and odd > 0:
            odds_by.setdefault(race_id, {})[ticket] = odd

    return races, entries_by, odds_by


def _match_rule(row: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    odd = _safe_float(row.get("odds"), 0.0)

    return (
        rule["pr_min"] <= pr <= rule["pr_max"]
        and rule["mr_min"] <= mr <= rule["mr_max"]
        and rule["odds_min"] <= odd < rule["odds_max"]
    )


def _select_one(
    matches: List[Dict[str, Any]],
    mode: str,
) -> Optional[Dict[str, Any]]:
    if not matches:
        return None

    if mode == "ev":
        return max(
            matches,
            key=lambda row: (
                _safe_float(row.get("raw_ev"), 0.0),
                _safe_float(row.get("prob"), 0.0),
            ),
        )

    return max(
        matches,
        key=lambda row: (
            _safe_float(row.get("prob"), 0.0),
            _safe_float(row.get("raw_ev"), 0.0),
        ),
    )


def main() -> None:
    print(
        "✅ collect_candidate_filter_shadow_pg.py "
        "VERSION 2026-08-13 phase4-shadow-v2.3",
        flush=True,
    )
    print(
        f"TARGET_DATE={TARGET_DATE} WINDOW_NAME={WINDOW_NAME} "
        f"ENABLED={ENABLED} REQUIRE_COMPLETE_ODDS={REQUIRE_COMPLETE_ODDS}",
        flush=True,
    )
    print(
        "ACTIVE_RULES="
        + (",".join(sorted(ACTIVE_RULE_IDS)) if ACTIVE_RULE_IDS else "(none)"),
        flush=True,
    )
    if UNKNOWN_REQUESTED_RULE_IDS:
        print(
            "⚠️ unknown requested rules: "
            + ",".join(UNKNOWN_REQUESTED_RULE_IDS),
            flush=True,
        )
    if UNKNOWN_DISABLED_RULE_IDS:
        print(
            "⚠️ unknown disabled rules: "
            + ",".join(UNKNOWN_DISABLED_RULE_IDS),
            flush=True,
        )
    print(
        "同一race_id・rule_idは最新1件へ更新。"
        "LINE通知・本番判定・購入処理は変更しません。",
        flush=True,
    )

    if not ENABLED:
        print("CANDIDATE_SHADOW_ENABLED=0 のためスキップします。", flush=True)
        return

    if not ACTIVE_RULES:
        print("有効なShadowルールが0件のためスキップします。", flush=True)
        return

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    _ensure_schema()
    races, entries_by, odds_by = _fetch_day_rows()
    event_day_by_venue = v24._compute_event_day_by_venue(TARGET_DATE)

    rows_out: List[Dict[str, Any]] = []
    ready_races = 0
    skipped_entries = 0
    skipped_odds = 0
    matched_by_rule = {rule["rule_id"]: 0 for rule in ACTIVE_RULES}
    now_iso = datetime.now(JST).isoformat()

    for race in races:
        race_id = str(race.get("race_id") or "")
        venue_id = str(
            race.get("venue_id")
            or race.get("venue_code")
            or ""
        ).zfill(2)
        race_no = _safe_int(race.get("race_no"), 0)

        entries = entries_by.get(race_id, [])
        if len(v24._entry_by_lane(entries)) != 6:
            skipped_entries += 1
            continue

        odds = odds_by.get(race_id, {})
        if REQUIRE_COMPLETE_ODDS:
            ready, _ = v24._validate_odds_snapshot(odds)
            if not ready:
                skipped_odds += 1
                continue
        elif not odds:
            skipped_odds += 1
            continue

        ready_races += 1

        meta_text = v24._metadata_text(race)
        venue_style = v24._infer_venue_style(venue_id)
        event_category = v24._infer_event_category(meta_text)
        event_day_no = event_day_by_venue.get(venue_id, 1)
        ranked = v24._rank_candidates(entries, venue_id, odds)

        for rule in ACTIVE_RULES:
            if race_no not in rule["race_nos"]:
                continue
            if (
                rule["venue_style"] != "ALL"
                and venue_style != rule["venue_style"]
            ):
                continue
            if (
                rule["event_category"] != "ALL"
                and event_category != rule["event_category"]
            ):
                continue

            matches = [
                row for row in ranked
                if _match_rule(row, rule)
            ]
            selected = _select_one(matches, str(rule["select_mode"]))
            if not selected:
                continue

            matched_by_rule[rule["rule_id"]] += 1

            rows_out.append(
                {
                    "race_id": race_id,
                    "race_date": TARGET_DATE,
                    "venue_id": venue_id,
                    "race_no": race_no,
                    "window_name": WINDOW_NAME,
                    "rule_id": rule["rule_id"],
                    "rule_description": rule["description"],
                    "ticket": str(selected.get("ticket") or ""),
                    "odds": _safe_float(selected.get("odds"), 0.0),
                    "prob": _safe_float(selected.get("prob"), 0.0),
                    "prob_rank": _safe_int(selected.get("prob_rank"), 999),
                    "market_rank": _safe_int(selected.get("market_rank"), 999),
                    "raw_ev": _safe_float(selected.get("raw_ev"), 0.0),
                    "venue_style": venue_style,
                    "event_category": event_category,
                    "event_day_no": event_day_no,
                    "snapshot_at": now_iso,
                    "investment_yen": 100,
                    # 最新選択へ更新する際は評価を未評価へ戻す。
                    "result_ticket": None,
                    "payout_yen": None,
                    "hit": None,
                    "return_yen": None,
                    "evaluated_at": None,
                    "evaluation_status": None,
                    "evaluation_note": None,
                    "updated_at": now_iso,
                    "raw": {
                        "rule": {
                            **{
                                key: value
                                for key, value in rule.items()
                                if key != "race_nos"
                            },
                            "race_nos": sorted(rule["race_nos"]),
                        },
                        "window_name": WINDOW_NAME,
                        "selector_source": "v24_probability_model",
                        "selection_policy": "latest_by_race_rule",
                        "active_rule_ids": sorted(ACTIVE_RULE_IDS),
                    },
                }
            )

    saved = 0
    if rows_out:
        saved = upsert_rows(
            "v2_candidate_filter_shadow",
            rows_out,
            ["race_id", "rule_id"],
        )

    print(
        f"races={len(races)} ready_races={ready_races} "
        f"skipped_entries={skipped_entries} skipped_odds={skipped_odds}",
        flush=True,
    )
    print(
        f"candidate_rows={len(rows_out)} saved_rows={saved}",
        flush=True,
    )
    for rule_id, count in matched_by_rule.items():
        print(f"{rule_id} matched={count}", flush=True)

    print("=== candidate filter shadow collection finished ===", flush=True)


if __name__ == "__main__":
    main()