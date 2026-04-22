# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(__file__))

from config.settings import SUPABASE_URL, RACE_SCORE_THRESHOLD
from data_pipeline.load_race_list import load_race_list
from data_pipeline.load_race import load_race_context
from models.predictor_v2 import predict_race
from betting.bet_selector_v2 import select_bets
from models.risk_manager import judge_race_adoption


STAKE_PER_BET_YEN = 100
MAX_RACES_PER_DAY = 3
DAILY_PROFIT_TARGET_YEN = 1000

# -------------------------
# 分析結果ベースの固定フィルター
# -------------------------
ALLOWED_VENUES = {"06"}
MIN_RACE_SCORE = 0.18
MAX_RACE_SCORE = 0.21
ALLOWED_BET_TYPES = {"exacta"}
MIN_BET_PROB = 0.015


def daterange(start_date, end_date):
    cur = start_date
    while cur <= end_date:
        yield cur
        cur += timedelta(days=1)


def _safe_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _extract_exacta_result_ticket(result_row):
    if not result_row:
        return None
    return (
        result_row.get("exacta_ticket")
        or result_row.get("nitan_ticket")
        or result_row.get("quinella_exact_ticket")
        or result_row.get("ticket_exacta")
    )


def _extract_exacta_payout_yen(result_row):
    if not result_row:
        return 0
    value = (
        result_row.get("exacta_payout_yen")
        or result_row.get("nitan_payout_yen")
        or result_row.get("quinella_exact_payout_yen")
        or result_row.get("payout_exacta_yen")
    )
    return _safe_int(value, 0)


def _extract_trifecta_result_ticket(result_row, fallback_ticket=None):
    if fallback_ticket:
        return fallback_ticket
    if not result_row:
        return None
    return (
        result_row.get("trifecta_ticket")
        or result_row.get("trifecta")
        or result_row.get("winning_ticket")
        or result_row.get("ticket")
    )


def _extract_trifecta_payout_yen(result_row):
    if not result_row:
        return 0
    value = (
        result_row.get("trifecta_payout_yen")
        or result_row.get("sanrentan_payout_yen")
        or result_row.get("payout_yen")
    )
    return _safe_int(value, 0)


def _hit_check_and_payout(bet, context):
    result_ticket = context.get("result")
    result_row = context.get("result_row", {}) or {}

    bet_type = bet.get("bet_type", "trifecta")
    ticket = bet.get("ticket")

    if bet_type == "exacta":
        exacta_result_ticket = _extract_exacta_result_ticket(result_row)

        if not exacta_result_ticket and result_ticket:
            parts = str(result_ticket).split("-")
            if len(parts) >= 2:
                exacta_result_ticket = f"{parts[0]}-{parts[1]}"

        hit = (ticket == exacta_result_ticket)
        payout_yen = _extract_exacta_payout_yen(result_row) if hit else 0
        return hit, payout_yen, exacta_result_ticket

    trifecta_result_ticket = _extract_trifecta_result_ticket(result_row, result_ticket)
    hit = (ticket == trifecta_result_ticket)
    payout_yen = _extract_trifecta_payout_yen(result_row) if hit else 0
    return hit, payout_yen, trifecta_result_ticket


def _passes_analysis_filter(context, race_score, bets):
    venue_id = str(context.get("venue_id", "")).zfill(2)

    if venue_id not in ALLOWED_VENUES:
        return False, "venue除外"

    if race_score < MIN_RACE_SCORE:
        return False, "score下限未満"

    if race_score >= MAX_RACE_SCORE:
        return False, "score上限以上"

    if not bets:
        return False, "買い目なし"

    filtered = []
    for bet in bets:
        bet_type = bet.get("bet_type")
        prob = float(bet.get("prob", 0.0))

        if bet_type not in ALLOWED_BET_TYPES:
            continue
        if prob < MIN_BET_PROB:
            continue

        filtered.append(bet)

    if not filtered:
        return False, "bet条件除外"

    return True, filtered


def run_backtest(start_date_str, end_date_str):
    print("=== バックテスト開始 ===")
    print("期間:", start_date_str, "→", end_date_str)
    print("SUPABASE_URL:", SUPABASE_URL)
    print("RACE_SCORE_THRESHOLD:", RACE_SCORE_THRESHOLD)
    print("STAKE_PER_BET_YEN:", STAKE_PER_BET_YEN)
    print("MAX_RACES_PER_DAY:", MAX_RACES_PER_DAY)
    print("DAILY_PROFIT_TARGET_YEN:", DAILY_PROFIT_TARGET_YEN)
    print("ALLOWED_VENUES:", sorted(ALLOWED_VENUES))
    print("MIN_RACE_SCORE:", MIN_RACE_SCORE)
    print("MAX_RACE_SCORE:", MAX_RACE_SCORE)
    print("ALLOWED_BET_TYPES:", sorted(ALLOWED_BET_TYPES))
    print("MIN_BET_PROB:", MIN_BET_PROB)

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    total_adopted_races = 0
    total_bets = 0
    total_hits = 0
    total_stake_yen = 0
    total_payout_yen = 0
    target_achieved_days = 0

    daily_logs = []

    for d in daterange(start_date, end_date):
        race_date = d.strftime("%Y-%m-%d")
        print("\n---", race_date, "---")

        races = load_race_list(
            race_date=race_date,
            session_type="day",
            venue_ids=["01", "06", "12", "18", "24"]
        )

        candidate_rows = []

        for r in races:
            venue_id = r["venue_id"]
            race_no = r["race_no"]

            context = load_race_context(venue_id, race_no, race_date)
            if not context:
                continue

            pred = predict_race(context)
            race_score = pred.get("race_score", 0.0)
            bets = select_bets(pred, max_bets=2)

            adopt, reason = judge_race_adoption(context, pred, bets)

            if not adopt:
                continue

            if race_score < RACE_SCORE_THRESHOLD:
                continue

            ok, filter_result = _passes_analysis_filter(context, race_score, bets)
            if not ok:
                print("filter skip:", context["race_id"], filter_result)
                continue

            filtered_bets = filter_result

            candidate_rows.append({
                "context": context,
                "pred": pred,
                "bets": filtered_bets,
                "race_score": race_score,
            })

        candidate_rows.sort(key=lambda x: x["race_score"], reverse=True)
        adopted_rows = candidate_rows[:MAX_RACES_PER_DAY]

        day_adopted_races = 0
        day_bets = 0
        day_hits = 0
        day_stake_yen = 0
        day_payout_yen = 0

        for row in adopted_rows:
            context = row["context"]
            bets = row["bets"]
            race_score = row["race_score"]

            day_adopted_races += 1
            total_adopted_races += 1

            result_ticket = context.get("result")
            print("race:", context["race_id"], "selected_score=", round(race_score, 6), "result=", result_ticket)

            for b in bets:
                day_bets += 1
                total_bets += 1

                day_stake_yen += STAKE_PER_BET_YEN
                total_stake_yen += STAKE_PER_BET_YEN

                hit, payout_yen, compare_ticket = _hit_check_and_payout(b, context)

                if hit:
                    day_hits += 1
                    total_hits += 1
                    day_payout_yen += payout_yen
                    total_payout_yen += payout_yen

                print(
                    "  bet:",
                    b["ticket"],
                    "type=", b.get("bet_type"),
                    "prob=", round(b.get("prob", 0.0), 6),
                    "compare=", compare_ticket,
                    "hit=", hit,
                    "payout=", payout_yen
                )

        day_profit_yen = day_payout_yen - day_stake_yen
        day_hit_rate = (day_hits / day_bets * 100) if day_bets > 0 else 0.0
        day_roi_pct = (day_payout_yen / day_stake_yen * 100) if day_stake_yen > 0 else 0.0
        achieved = day_profit_yen >= DAILY_PROFIT_TARGET_YEN

        if achieved:
            target_achieved_days += 1

        print(f"採用レース: {day_adopted_races}")
        print(f"買い目: {day_bets}")
        print(f"的中: {day_hits}")
        print(f"的中率: {round(day_hit_rate, 2)}%")
        print(f"投資: {day_stake_yen}円")
        print(f"払戻: {day_payout_yen}円")
        print(f"収支: {day_profit_yen}円")
        print(f"ROI: {round(day_roi_pct, 2)}%")
        print(f"+1000円達成: {'YES' if achieved else 'NO'}")

        daily_logs.append({
            "date": race_date,
            "adopted_races": day_adopted_races,
            "bets": day_bets,
            "hits": day_hits,
            "hit_rate": round(day_hit_rate, 2),
            "stake_yen": day_stake_yen,
            "payout_yen": day_payout_yen,
            "profit_yen": day_profit_yen,
            "roi_pct": round(day_roi_pct, 2),
            "goal_achieved": achieved,
        })

    total_hit_rate = (total_hits / total_bets * 100) if total_bets > 0 else 0.0
    total_roi_pct = (total_payout_yen / total_stake_yen * 100) if total_stake_yen > 0 else 0.0
    total_profit_yen = total_payout_yen - total_stake_yen

    print("\n=== 総合結果 ===")
    print("総採用レース:", total_adopted_races)
    print("総買い目:", total_bets)
    print("総的中:", total_hits)
    print("的中率:", round(total_hit_rate, 2), "%")
    print("総投資:", total_stake_yen, "円")
    print("総払戻:", total_payout_yen, "円")
    print("総収支:", total_profit_yen, "円")
    print("総ROI:", round(total_roi_pct, 2), "%")
    print("+1000円達成日数:", target_achieved_days)

    print("\n=== 日別ログ ===")
    for d in daily_logs:
        print(d)


if __name__ == "__main__":
    run_backtest("2026-01-01", "2026-04-20")
