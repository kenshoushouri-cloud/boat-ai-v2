# -*- coding: utf-8 -*-
"""
collect_v24_motor2_forward_shadow_pg.py

v24 MOTOR2 Forward Shadow collector

目的:
- 現行v24(BASE)は変更しない
- motor_place2_rate を使用した MOTOR2 を並行計算
- その時点の odds / market_rank / prob_rank を保存
- BASE と MOTOR2 の候補入り/候補落ちを将来データで比較する
- LINE通知・購入・本番判定は一切行わない

Railway Start Command:
    python -u collect_v24_motor2_forward_shadow_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    TARGET_DATE=YYYY-MM-DD
    TARGET_RACE_IDS=...
    MOTOR2_SHADOW_SESSION=all|day|night
"""

from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from psycopg.types.json import Jsonb

from db_pg import execute, fetch_all
import v24_pre_candidate_notifier_pg as v24


VERSION = "2026-08-19 v24-motor2-forward-shadow-v1"

JST = timezone(timedelta(hours=9))

TARGET_DATE = (
    os.getenv("TARGET_DATE")
    or datetime.now(JST).strftime("%Y-%m-%d")
)

SHADOW_SESSION = (
    os.getenv("MOTOR2_SHADOW_SESSION", "all")
    .strip()
    .lower()
)


# ============================================================
# Utility
# ============================================================

def sf(v: Any, default=None):
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default


def si(v: Any, default=0):
    try:
        if v in (None, ""):
            return default
        return int(float(v))
    except Exception:
        return default


def parse_target_race_ids() -> set[str]:
    raw = (os.getenv("TARGET_RACE_IDS") or "").strip()

    if not raw:
        return set()

    return {
        x.strip()
        for x in re.split(r"[,\s]+", raw)
        if x.strip()
    }


TARGET_RACE_IDS = parse_target_race_ids()


def valid_motor2(v: Any) -> float:
    """
    過去DBに100超の異常値が存在したため、
    0～100だけを有効値とする。

    NULL / 不正値 / >100 はBASE既定値33.0へ戻す。
    """
    x = sf(v, None)

    if x is None:
        return 33.0

    if not (0.0 <= x <= 100.0):
        return 33.0

    return x


# ============================================================
# Schema
# ============================================================

def ensure_table() -> None:

    execute(
        """
        create table if not exists v2_v24_motor2_forward_shadow (

            id bigserial primary key,

            race_id text not null,
            race_date date not null,

            venue_id text,
            race_no integer,

            ticket text not null,

            odds numeric,
            market_rank integer,

            base_prob numeric,
            base_prob_rank integer,
            base_raw_ev numeric,

            motor2_prob numeric,
            motor2_prob_rank integer,
            motor2_raw_ev numeric,

            base_low_candidate boolean not null default false,
            motor2_low_candidate boolean not null default false,

            base_mid_candidate boolean not null default false,
            motor2_mid_candidate boolean not null default false,

            candidate_transition text,

            motor2_valid_lanes integer,
            motor2_fallback_lanes integer,

            captured_at timestamptz not null default now(),

            raw jsonb
        );
        """
    )

    execute(
        """
        create index if not exists
        idx_v24_motor2_shadow_race
        on v2_v24_motor2_forward_shadow(race_id);
        """
    )

    execute(
        """
        create index if not exists
        idx_v24_motor2_shadow_date
        on v2_v24_motor2_forward_shadow(race_date);
        """
    )

    execute(
        """
        create index if not exists
        idx_v24_motor2_shadow_transition
        on v2_v24_motor2_forward_shadow(candidate_transition);
        """
    )

    # 同一取得回での二重保存防止用。
    execute(
        """
        create unique index if not exists
        uq_v24_motor2_shadow_race_ticket_capture
        on v2_v24_motor2_forward_shadow
        (race_id, ticket, captured_at);
        """
    )


# ============================================================
# BASE / MOTOR2 probability
# ============================================================

def raw_strength(
    entry: Dict[str, Any],
    lane: int,
    venue_id: str,
    use_motor2: bool,
) -> float:

    cls = si(entry.get("racer_class"), 2)
    cls_w = v24.CLASS_WEIGHT.get(cls, 0.55)

    win_rate = sf(entry.get("national_win_rate"), 0.0)
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    avg_st = sf(entry.get("avg_st"), 0.18)

    win_rate = 0.0 if win_rate is None else win_rate
    nat2 = 32.0 if nat2 is None else nat2
    loc2 = 30.0 if loc2 is None else loc2
    avg_st = 0.18 if avg_st is None else avg_st

    if use_motor2:
        mot2 = valid_motor2(entry.get("motor_place2_rate"))
    else:
        mot2 = 33.0

    boat2 = 34.0

    course_bias = (
        v24.VENUE_COURSE_BIAS
        .get(venue_id, v24.DEFAULT_COURSE_BIAS)
        .get(lane, v24.DEFAULT_COURSE_BIAS[lane])
    )

    st_score = max(
        0.0,
        min(
            1.0,
            (0.24 - avg_st) / 0.12
        )
    )

    return (
        cls_w * 1.00
        + win_rate * 0.16
        + (nat2 / 100.0) * 0.90
        + (loc2 / 100.0) * 0.55
        + (mot2 / 100.0) * 0.45
        + (boat2 / 100.0) * 0.25
        + st_score * 0.35
        + course_bias * 0.22
    )


def ticket_probabilities(
    entries: List[Dict[str, Any]],
    venue_id: str,
    use_motor2: bool,
) -> Dict[str, float]:

    by_lane = v24._entry_by_lane(entries)

    raw = {
        lane: raw_strength(
            by_lane[lane],
            lane,
            venue_id,
            use_motor2,
        )
        for lane in range(1, 7)
    }

    weights = {
        lane: math.exp(
            raw[lane] / v24.PROB_TEMP
        )
        for lane in range(1, 7)
    }

    total = sum(weights.values())

    probs: Dict[str, float] = {}

    for a in range(1, 7):

        pa = weights[a] / total
        total_b = total - weights[a]

        for b in range(1, 7):

            if b == a:
                continue

            pb = weights[b] / total_b
            total_c = total_b - weights[b]

            for c in range(1, 7):

                if c == a or c == b:
                    continue

                pc = weights[c] / total_c

                probs[f"{a}-{b}-{c}"] = (
                    pa * pb * pc
                )

    return probs


def probability_ranks(
    probs: Dict[str, float]
) -> Dict[str, int]:

    ordered = sorted(
        probs.items(),
        key=lambda kv: (-kv[1], kv[0])
    )

    return {
        ticket: rank
        for rank, (ticket, _) in enumerate(
            ordered,
            start=1,
        )
    }


# ============================================================
# Candidate bands
# ============================================================

def is_low_candidate(
    prob_rank: int,
    market_rank: int,
    odds: float,
) -> bool:

    return (
        11 <= prob_rank <= 20
        and market_rank == 1
        and 3.0 <= odds < 5.0
    )


def is_mid_candidate(
    ticket: str,
    prob_rank: int,
    market_rank: int,
    odds: float,
) -> bool:

    return (
        4 <= prob_rank <= 5
        and 21 <= market_rank <= 30
        and 30.0 <= odds < 50.0
        and v24._head_lane(ticket) != "1"
    )


def candidate_transition(
    base_candidate: bool,
    motor_candidate: bool,
) -> str:

    if base_candidate and motor_candidate:
        return "BOTH"

    if base_candidate and not motor_candidate:
        return "BASE_ONLY"

    if not base_candidate and motor_candidate:
        return "MOTOR2_ONLY"

    return "NEITHER"


# ============================================================
# Fetch
# ============================================================

def fetch_data():

    races, entries_by_race, odds_by_race = (
        v24._fetch_live_day_rows(TARGET_DATE)
    )

    # v24のfetchはTARGET_RACE_IDS環境変数もそのまま利用する。
    return races, entries_by_race, odds_by_race


# ============================================================
# Save
# ============================================================

def save_row(row: Dict[str, Any]) -> None:

    execute(
        """
        insert into v2_v24_motor2_forward_shadow (

            race_id,
            race_date,
            venue_id,
            race_no,

            ticket,

            odds,
            market_rank,

            base_prob,
            base_prob_rank,
            base_raw_ev,

            motor2_prob,
            motor2_prob_rank,
            motor2_raw_ev,

            base_low_candidate,
            motor2_low_candidate,

            base_mid_candidate,
            motor2_mid_candidate,

            candidate_transition,

            motor2_valid_lanes,
            motor2_fallback_lanes,

            captured_at,
            raw
        )

        values (

            %s,%s,%s,%s,
            %s,
            %s,%s,
            %s,%s,%s,
            %s,%s,%s,
            %s,%s,
            %s,%s,
            %s,
            %s,%s,
            now(),
            %s
        );
        """,
        (
            row["race_id"],
            row["race_date"],
            row["venue_id"],
            row["race_no"],

            row["ticket"],

            row["odds"],
            row["market_rank"],

            row["base_prob"],
            row["base_prob_rank"],
            row["base_raw_ev"],

            row["motor2_prob"],
            row["motor2_prob_rank"],
            row["motor2_raw_ev"],

            row["base_low_candidate"],
            row["motor2_low_candidate"],

            row["base_mid_candidate"],
            row["motor2_mid_candidate"],

            row["candidate_transition"],

            row["motor2_valid_lanes"],
            row["motor2_fallback_lanes"],

            Jsonb(row["raw"]),
        ),
    )


# ============================================================
# Main
# ============================================================

def main() -> None:

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError(
            "DATABASE_URL が必要です。"
        )

    print(
        f"✅ collect_v24_motor2_forward_shadow_pg.py "
        f"VERSION {VERSION}",
        flush=True,
    )

    print(
        f"TARGET_DATE={TARGET_DATE} "
        f"SESSION={SHADOW_SESSION}",
        flush=True,
    )

    print(
        "SHADOW ONLY: "
        "LINE通知なし / BUYなし / "
        "本番v24変更なし / N02変更なし",
        flush=True,
    )

    ensure_table()

    races, entries_by_race, odds_by_race = fetch_data()

    print(
        f"races={len(races)}",
        flush=True,
    )

    saved = 0
    ready = 0
    skipped_entries = 0
    skipped_odds = 0

    transitions = {
        "BOTH": 0,
        "BASE_ONLY": 0,
        "MOTOR2_ONLY": 0,
        "NEITHER": 0,
    }

    low_base = 0
    low_motor = 0

    mid_base = 0
    mid_motor = 0

    for race in races:

        rid = str(
            race.get("race_id") or ""
        )

        venue_id = str(
            race.get("venue_id")
            or race.get("venue_code")
            or ""
        ).zfill(2)

        race_no = si(
            race.get("race_no"),
            0,
        )

        entries = entries_by_race.get(
            rid,
            [],
        )

        odds = odds_by_race.get(
            rid,
            {},
        )

        by_lane = v24._entry_by_lane(entries)

        if len(by_lane) != 6:
            skipped_entries += 1
            continue

        odds_ready, detail = (
            v24._validate_odds_snapshot(odds)
        )

        if not odds_ready:
            skipped_odds += 1

            print(
                f"ODDS_NOT_READY "
                f"race_id={rid} {detail}",
                flush=True,
            )

            continue

        ready += 1

        # --------------------------------------------
        # BASE / MOTOR2 probabilities
        # --------------------------------------------

        base_probs = ticket_probabilities(
            entries,
            venue_id,
            False,
        )

        motor_probs = ticket_probabilities(
            entries,
            venue_id,
            True,
        )

        base_ranks = probability_ranks(
            base_probs
        )

        motor_ranks = probability_ranks(
            motor_probs
        )

        # --------------------------------------------
        # Market rank
        # --------------------------------------------

        market_order = sorted(
            odds.items(),
            key=lambda kv: (
                kv[1],
                kv[0],
            )
        )

        market_ranks = {
            ticket: rank
            for rank, (ticket, _) in enumerate(
                market_order,
                start=1,
            )
        }

        # --------------------------------------------
        # Motor data audit
        # --------------------------------------------

        valid_lanes = 0
        fallback_lanes = 0

        for lane in range(1, 7):

            raw_motor = sf(
                by_lane[lane].get(
                    "motor_place2_rate"
                ),
                None,
            )

            if (
                raw_motor is not None
                and 0 <= raw_motor <= 100
            ):
                valid_lanes += 1
            else:
                fallback_lanes += 1

        # --------------------------------------------
        # Save all tickets
        # --------------------------------------------

        for ticket, odd_value in odds.items():

            if ticket not in base_probs:
                continue

            if ticket not in motor_probs:
                continue

            odds_value = float(odd_value)

            br = base_ranks[ticket]
            mr = motor_ranks[ticket]

            market_rank = market_ranks[ticket]

            base_low = is_low_candidate(
                br,
                market_rank,
                odds_value,
            )

            motor_low = is_low_candidate(
                mr,
                market_rank,
                odds_value,
            )

            base_mid = is_mid_candidate(
                ticket,
                br,
                market_rank,
                odds_value,
            )

            motor_mid = is_mid_candidate(
                ticket,
                mr,
                market_rank,
                odds_value,
            )

            base_candidate = (
                base_low or base_mid
            )

            motor_candidate = (
                motor_low or motor_mid
            )

            transition = candidate_transition(
                base_candidate,
                motor_candidate,
            )

            transitions[transition] += 1

            low_base += int(base_low)
            low_motor += int(motor_low)

            mid_base += int(base_mid)
            mid_motor += int(motor_mid)

            row = {

                "race_id": rid,
                "race_date": TARGET_DATE,
                "venue_id": venue_id,
                "race_no": race_no,

                "ticket": ticket,

                "odds": odds_value,
                "market_rank": market_rank,

                "base_prob": base_probs[ticket],
                "base_prob_rank": br,
                "base_raw_ev":
                    base_probs[ticket]
                    * odds_value,

                "motor2_prob":
                    motor_probs[ticket],

                "motor2_prob_rank": mr,

                "motor2_raw_ev":
                    motor_probs[ticket]
                    * odds_value,

                "base_low_candidate":
                    base_low,

                "motor2_low_candidate":
                    motor_low,

                "base_mid_candidate":
                    base_mid,

                "motor2_mid_candidate":
                    motor_mid,

                "candidate_transition":
                    transition,

                "motor2_valid_lanes":
                    valid_lanes,

                "motor2_fallback_lanes":
                    fallback_lanes,

                "raw": {
                    "version": VERSION,
                    "shadow_only": True,
                    "base_motor2": 33.0,
                    "motor2_weight": 0.45,
                    "prob_temp": v24.PROB_TEMP,
                },
            }

            save_row(row)

            saved += 1

    # ========================================================
    # Summary
    # ========================================================

    print(
        "\n=== MOTOR2 FORWARD SHADOW SUMMARY ===",
        flush=True,
    )

    print(
        f"races={len(races)} "
        f"ready={ready} "
        f"saved={saved}",
        flush=True,
    )

    print(
        f"skipped_entries={skipped_entries} "
        f"skipped_odds={skipped_odds}",
        flush=True,
    )

    print(
        f"LOW BASE={low_base} "
        f"MOTOR2={low_motor}",
        flush=True,
    )

    print(
        f"MID BASE={mid_base} "
        f"MOTOR2={mid_motor}",
        flush=True,
    )

    print(
        "TRANSITIONS "
        f"BOTH={transitions['BOTH']} "
        f"BASE_ONLY={transitions['BASE_ONLY']} "
        f"MOTOR2_ONLY={transitions['MOTOR2_ONLY']} "
        f"NEITHER={transitions['NEITHER']}",
        flush=True,
    )

    print(
        "RESULT=PASS",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as e:

        print(
            "FATAL ERROR",
            flush=True,
        )

        print(
            f"{type(e).__name__}: {e}",
            flush=True,
        )

        import traceback
        traceback.print_exc()

        raise