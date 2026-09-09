# -*- coding: utf-8 -*-
"""Safe v21 realtime collector entrypoint.

Reuses the established v21 weather/exhibition/database machinery while replacing
only the trifecta parsing/selection path. Direct official odds are accepted only
when they are a complete dynamic 120/60/24 set. The legacy base-table fallback
is also accepted only when complete; partial stale data is never propagated into
realtime odds snapshots.
"""
from __future__ import annotations

import time
from pathlib import Path

import official_odds3t_parser as odds_parser
import v21_realtime_collector_pg as legacy

VERSION = "2026-09-10 official-table-parser-fail-closed-v1"


def _choose_odds(html: str | None, base_values):
    official = odds_parser.parse_official_odds3t(html or "") if html else {}
    return odds_parser.choose_realtime_snapshot(official, base_values)


def main() -> None:
    legacy._require_settings()
    legacy._ensure_realtime_tables()
    now = legacy._now()
    print(f"✅ v21_realtime_collector_pg_safe.py VERSION {VERSION}", flush=True)
    print(
        f"TARGET_DATE={legacy.TARGET_DATE} SNAPSHOT_LABEL={legacy.SNAPSHOT_LABEL} "
        f"SCOPE={legacy.COLLECT_SCOPE} TARGET_ID_SCOPE={legacy.TARGET_ID_SCOPE} "
        f"TARGET_RACE_ID={legacy.TARGET_RACE_ID or '-'} "
        "ODDS_SELECTION=exact_dynamic_120_60_24_fail_closed",
        flush=True,
    )
    print(
        f"FINAL_DEADLINE_FILTER={legacy.FINAL_DEADLINE_FILTER} "
        f"FINAL_WINDOW_BEFORE_MIN={legacy.FINAL_WINDOW_BEFORE_MIN} "
        f"FINAL_WINDOW_AFTER_MIN={legacy.FINAL_WINDOW_AFTER_MIN} "
        f"NOW_JST={now.isoformat()}",
        flush=True,
    )

    races, entries_by, base_odds = legacy.fetch_day_base(legacy.TARGET_DATE)
    days = legacy._event_day_by_venue(legacy.TARGET_DATE)
    scope = []
    for race in races:
        rid = str(race.get("race_id"))
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        race_no = legacy._safe_int(race.get("race_no"))
        if legacy.TARGET_RACE_ID and rid != legacy.TARGET_RACE_ID:
            continue
        if (
            legacy.COLLECT_SCOPE == "candidates"
            and not legacy._is_candidate_race(venue, race_no, days.get(venue, 1))
        ):
            continue
        scope.append(race)

    use_filter = legacy.FINAL_DEADLINE_FILTER and not legacy.TARGET_RACE_ID
    target = []
    miss = early = passed = 0
    for race in scope:
        if not use_filter:
            target.append(race)
            continue
        ok, why = legacy._deadline_match(race, now)
        if ok:
            target.append(race)
        elif why == "deadline_missing":
            miss += 1
        elif why == "too_early":
            early += 1
        else:
            passed += 1

    print(
        f"races={len(races)} scope_races={len(scope)} target_races={len(target)}",
        flush=True,
    )
    print(
        f"deadline_filter_used={use_filter} skipped_deadline_missing={miss} "
        f"skipped_too_early={early} skipped_deadline_passed={passed}",
        flush=True,
    )

    if legacy.TARGET_RACE_ID:
        target_id_rows = target
    elif legacy.TARGET_ID_SCOPE in ("candidates", "candidate"):
        target_id_rows = []
        for race in target:
            venue = str(
                race.get("venue_id") or race.get("venue_code") or ""
            ).zfill(2)
            race_no = legacy._safe_int(race.get("race_no"))
            if legacy._is_candidate_race(venue, race_no, days.get(venue, 1)):
                target_id_rows.append(race)
    elif legacy.TARGET_ID_SCOPE in ("none", "off", "disabled"):
        target_id_rows = []
    else:
        target_id_rows = target

    collection_ids = [
        str(race.get("race_id")) for race in target if race.get("race_id")
    ]
    target_ids = [
        str(race.get("race_id"))
        for race in target_id_rows
        if race.get("race_id")
    ]
    print(
        f"collection_target_races={len(collection_ids)} "
        f"decision_target_races={len(target_ids)} "
        f"TARGET_ID_SCOPE={legacy.TARGET_ID_SCOPE}",
        flush=True,
    )
    try:
        Path(legacy.COLLECTION_RACE_IDS_FILE).write_text(
            ",".join(collection_ids), encoding="utf-8"
        )
        print(
            f"COLLECTION_RACE_IDS_FILE={legacy.COLLECTION_RACE_IDS_FILE} "
            f"written={len(collection_ids)}",
            flush=True,
        )
    except Exception as exc:
        raise RuntimeError(
            f"COLLECTION_RACE_IDS_FILEの書き込みに失敗しました: {exc}"
        ) from exc
    try:
        Path(legacy.TARGET_RACE_IDS_FILE).write_text(
            ",".join(target_ids), encoding="utf-8"
        )
        print(
            f"TARGET_RACE_IDS_FILE={legacy.TARGET_RACE_IDS_FILE} "
            f"written={len(target_ids)}",
            flush=True,
        )
    except Exception as exc:
        raise RuntimeError(
            f"TARGET_RACE_IDS_FILEの書き込みに失敗しました: {exc}"
        ) from exc

    for race in target[:20]:
        deadline = legacy._parse_deadline_at(race)
        print(
            f"  {race.get('race_id')} "
            f"deadline={deadline.isoformat() if deadline else '-'}",
            flush=True,
        )

    sw = sx = se = so = src_cond = splayer_cond = nb = ne = no = 0
    for index, race in enumerate(target, 1):
        rid = str(race.get("race_id"))
        venue = str(
            race.get("venue_id") or race.get("venue_code") or ""
        ).zfill(2)
        race_no = legacy._safe_int(race.get("race_no"))
        before_html = legacy._fetch(
            legacy._official_url("beforeinfo", legacy.TARGET_DATE, venue, race_no)
        )
        exhibition = []
        if legacy._looks_no_data(before_html):
            nb += 1
            c1, c2 = legacy.save_exhibition_and_entries(
                race, entries_by.get(rid, []), []
            )
            sx += c1
            se += c2
        else:
            sw += legacy.save_weather(race, legacy.parse_weather(before_html or ""))
            exhibition = legacy.parse_exhibition(before_html or "")
            ne += int(not exhibition)
            c1, c2 = legacy.save_exhibition_and_entries(
                race, entries_by.get(rid, []), exhibition
            )
            sx += c1
            se += c2
            race_cond, racer_cond = legacy.parse_beforeinfo_extra(
                before_html or "", entries_by.get(rid, [])
            )
            c3, c4 = legacy.save_beforeinfo_extra(
                race,
                entries_by.get(rid, []),
                race_cond,
                racer_cond,
            )
            src_cond += c3
            splayer_cond += c4

        odds_html = legacy._fetch(
            legacy._official_url("odds3t", legacy.TARGET_DATE, venue, race_no)
        )
        odds, source = _choose_odds(odds_html, base_odds.get(rid))
        if odds:
            so += legacy.save_odds(race, odds, source)
        else:
            no += 1
        print(
            f"[{index}/{len(target)}] {rid} "
            f"before={'ok' if before_html else 'ng'} "
            f"exh_rows={len(exhibition)} odds={len(odds)} "
            f"source={source if odds else '-'}",
            flush=True,
        )
        if legacy.REALTIME_SLEEP_SEC > 0:
            time.sleep(legacy.REALTIME_SLEEP_SEC)

    print("\n=== v21 safe PG realtime collection summary ===", flush=True)
    print(
        f"scope_races: {len(scope)}\n"
        f"target_races: {len(target)}\n"
        f"saved_weather: {sw}\n"
        f"saved_exhibition_rows: {sx}\n"
        f"saved_entry_rows: {se}\n"
        f"saved_race_condition_rows: {src_cond}\n"
        f"saved_racer_condition_rows: {splayer_cond}\n"
        f"saved_odds_rows: {so}\n"
        f"no_beforeinfo: {nb}\n"
        f"no_exhibition_complete: {ne}\n"
        f"no_odds: {no}",
        flush=True,
    )
    print("=== v21 safe PG リアルタイム収集終了 ===", flush=True)


if __name__ == "__main__":
    main()
