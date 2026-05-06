# -*- coding: utf-8 -*-
import os

from db.client import select_where, upsert
from data_pipeline.fetch_results import (
    fetch_result_rows,
    parse_result_row,
    debug_print_row,
)


def _normalize_venues(venue_ids=None):
    """
    優先順位:
    1. 引数 venue_ids
    2. 環境変数 BACKFILL_VENUES
    3. 環境変数 TARGET_VENUES
    4. None = 全対象扱い
    """
    if venue_ids is None:
        env_venues = (
            os.environ.get("BACKFILL_VENUES")
            or os.environ.get("TARGET_VENUES")
            or ""
        ).strip()

        if env_venues:
            venue_ids = [
                v.strip()
                for v in env_venues.split(",")
                if v.strip()
            ]

    if venue_ids is None:
        return None

    return {str(v).zfill(2) for v in venue_ids}


def _venue_from_race_id(race_id):
    try:
        return str(race_id).split("_")[1].zfill(2)
    except Exception:
        return None


def run_result_fetch_job(target_date, debug_first_n=3, venue_ids=None):
    print("=== 結果取得ジョブ開始 ===")
    print("対象日:", target_date)
    print("引数 venue_ids:", venue_ids)
    print("ENV BACKFILL_VENUES:", os.environ.get("BACKFILL_VENUES"))
    print("ENV TARGET_VENUES:", os.environ.get("TARGET_VENUES"))

    target_venues = _normalize_venues(venue_ids)

    if target_venues:
        print("対象場:", ",".join(sorted(target_venues)))
    else:
        print("対象場: all / fetch_result_rows default")

    rows, source_url = fetch_result_rows(
        target_date,
        venue_ids=target_venues,
    )

    print("API件数:", len(rows))

    print("DEBUG result fetched venues:", sorted({
        str(row.get("race_stadium_number", "")).zfill(2)
        for row in rows
    }))

    for i, row in enumerate(rows[:debug_first_n]):
        debug_print_row(row, idx=i)

    saved_count = 0
    skip_count = 0
    venue_skip_count = 0
    no_race_skip_count = 0

    for row in rows:
        parsed = parse_result_row(row)

        if not parsed:
            skip_count += 1
            continue

        race_id = parsed["race_id"]
        venue_id = _venue_from_race_id(race_id)

        if target_venues and venue_id not in target_venues:
            print("venue skip:", race_id, "venue=", venue_id)
            venue_skip_count += 1
            continue

        races = select_where(
            "v2_races",
            {"race_id": race_id},
            limit=1,
        )

        if not races:
            print("v2_races未投入skip:", race_id, "venue=", venue_id)
            no_race_skip_count += 1
            continue

        data = {
            "race_id": parsed["race_id"],
            "first_lane": parsed["first_lane"],
            "second_lane": parsed["second_lane"],
            "third_lane": parsed["third_lane"],
            "fourth_lane": parsed["fourth_lane"],
            "fifth_lane": parsed["fifth_lane"],
            "sixth_lane": parsed["sixth_lane"],
            "trifecta_ticket": parsed["trifecta_ticket"],
            "trifecta_payout_yen": parsed["trifecta_payout_yen"],
            "exacta_ticket": parsed["exacta_ticket"],
            "exacta_payout_yen": parsed["exacta_payout_yen"],
            "result_status": parsed["result_status"],
            "source": parsed["source"],
        }

        upsert(
            "v2_results",
            data,
            on_conflict=["race_id"],
        )

        saved_count += 1

        print(
            "saved:",
            race_id,
            "3連単=", parsed["trifecta_ticket"], parsed["trifecta_payout_yen"],
            "2連単=", parsed["exacta_ticket"], parsed["exacta_payout_yen"],
        )

    print("保存件数:", saved_count)
    print("skip件数:", skip_count)
    print("venue skip件数:", venue_skip_count)
    print("v2_races未投入skip件数:", no_race_skip_count)