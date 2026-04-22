# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.append(os.path.dirname(__file__))

from config.settings import SUPABASE_URL, RACE_SCORE_THRESHOLD
from data_pipeline.load_race_list import load_race_list
from data_pipeline.load_race import load_race_context
from models.predictor_v2 import predict_race
from betting.bet_selector_v2 import select_bets
from models.risk_manager import judge_race_adoption


STAKE_PER_BET_YEN = 100
MAX_RACES_PER_DAY = 3


def daterange(start_date, end_date):
    cur = start_date
    while cur <= end_date:
        yield cur
        cur += timedelta(days=1)


def _safe_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


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


def _score_band(score):
    score = _safe_float(score)
    if score < 0.12:
        return "<0.12"
    if score < 0.15:
        return "0.12-0.15"
    if score < 0.18:
        return "0.15-0.18"
    if score < 0.21:
        return "0.18-0.21"
    return "0.21+"


def _prob_band(prob):
    prob = _safe_float(prob)
    if prob < 0.015:
        return "<0.015"
    if prob < 0.020:
        return "0.015-0.020"
    if prob < 0.030:
        return "0.020-0.030"
    if prob < 0.050:
        return "0.030-0.050"
    return "0.050+"


def _payout_band(payout_yen):
    payout_yen = _safe_int(payout_yen)
    if payout_yen == 0:
        return "0"
    if payout_yen < 300:
        return "<300"
    if payout_yen < 500:
        return "300-499"
    if payout_yen < 1000:
        return "500-999"
    if payout_yen < 3000:
        return "1000-2999"
    return "3000+"


def _init_bucket():
    return {
        "bets": 0,
        "hits": 0,
        "stake_yen": 0,
        "payout_yen": 0,
    }


def _add_bucket(bucket, hit, payout_yen):
    bucket["bets"] += 1
    bucket["stake_yen"] += STAKE_PER_BET_YEN
    if hit:
        bucket["hits"] += 1
        bucket["payout_yen"] += payout_yen


def _bucket_rows(stats_dict):
    rows = []

    for key, v in stats_dict.items():
        bets = v["bets"]
        hits = v["hits"]
        stake = v["stake_yen"]
        payout = v["payout_yen"]
        hit_rate = (hits / bets * 100) if bets > 0 else 0.0
        roi = (payout / stake * 100) if stake > 0 else 0.0
        profit = payout - stake

        rows.append({
            "key": key,
            "bets": bets,
            "hits": hits,
            "hit_rate": round(hit_rate, 2),
            "stake_yen": stake,
            "payout_yen": payout,
            "profit_yen": profit,
            "roi_pct": round(roi, 2),
        })

    rows.sort(key=lambda x: x["roi_pct"], reverse=True)
    return rows


def _print_bucket_table(title, stats_dict):
    print(f"\n=== {title} ===")
    rows = _bucket_rows(stats_dict)
    for row in rows:
        print(row)
    return rows


def run_backtest_analysis(start_date_str, end_date_str):
    print("=== バックテスト分析開始 ===")
    print("期間:", start_date_str, "→", end_date_str)
    print("SUPABASE_URL:", SUPABASE_URL)
    print("RACE_SCORE_THRESHOLD:", RACE_SCORE_THRESHOLD)
    print("STAKE_PER_BET_YEN:", STAKE_PER_BET_YEN)
    print("MAX_RACES_PER_DAY:", MAX_RACES_PER_DAY)

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    total_bets = 0
    total_hits = 0
    total_stake_yen = 0
    total_payout_yen = 0

    stats_by_score_band = defaultdict(_init_bucket)
    stats_by_prob_band = defaultdict(_init_bucket)
    stats_by_bet_type = defaultdict(_init_bucket)
    stats_by_venue = defaultdict(_init_bucket)
    stats_by_payout_band = defaultdict(_init_bucket)

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
            venue_id = str(r["venue_id"]).zfill(2)
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

            if not bets:
                continue

            candidate_rows.append({
                "context": context,
                "pred": pred,
                "bets": bets,
                "race_score": race_score,
                "venue_id": venue_id,
            })

        candidate_rows.sort(key=lambda x: x["race_score"], reverse=True)
        adopted_rows = candidate_rows[:MAX_RACES_PER_DAY]

        print("採用候補数:", len(candidate_rows), "採用数:", len(adopted_rows))

        for row in adopted_rows:
            context = row["context"]
            race_score = row["race_score"]
            venue_id = row["venue_id"]

            for bet in row["bets"]:
                hit, payout_yen, compare_ticket = _hit_check_and_payout(bet, context)

                total_bets += 1
                total_stake_yen += STAKE_PER_BET_YEN
                if hit:
                    total_hits += 1
                    total_payout_yen += payout_yen

                score_key = _score_band(race_score)
                prob_key = _prob_band(bet.get("prob", 0.0))
                type_key = bet.get("bet_type", "unknown")
                payout_key = _payout_band(payout_yen if hit else 0)

                _add_bucket(stats_by_score_band[score_key], hit, payout_yen)
                _add_bucket(stats_by_prob_band[prob_key], hit, payout_yen)
                _add_bucket(stats_by_bet_type[type_key], hit, payout_yen)
                _add_bucket(stats_by_venue[venue_id], hit, payout_yen)
                _add_bucket(stats_by_payout_band[payout_key], hit, payout_yen)

                print({
                    "race_id": context["race_id"],
                    "bet_type": type_key,
                    "ticket": bet["ticket"],
                    "prob": round(bet.get("prob", 0.0), 6),
                    "race_score": round(race_score, 6),
                    "compare": compare_ticket,
                    "hit": hit,
                    "payout_yen": payout_yen,
                })

    total_hit_rate = (total_hits / total_bets * 100) if total_bets > 0 else 0.0
    total_roi = (total_payout_yen / total_stake_yen * 100) if total_stake_yen > 0 else 0.0
    total_profit = total_payout_yen - total_stake_yen

    summary = {
        "bets": total_bets,
        "hits": total_hits,
        "hit_rate": round(total_hit_rate, 2),
        "stake_yen": total_stake_yen,
        "payout_yen": total_payout_yen,
        "profit_yen": total_profit,
        "roi_pct": round(total_roi, 2),
    }

    print("\n=== 総合 ===")
    print(summary)

    score_ranges = _print_bucket_table("score帯別", stats_by_score_band)
    prob_ranges = _print_bucket_table("予測確率帯別", stats_by_prob_band)
    bet_types = _print_bucket_table("券種別", stats_by_bet_type)
    venues = _print_bucket_table("場別", stats_by_venue)
    payout_ranges = _print_bucket_table("的中払戻帯別", stats_by_payout_band)

    result = {
        "summary": summary,
        "score_ranges": score_ranges,
        "prob_ranges": prob_ranges,
        "bet_types": bet_types,
        "venues": venues,
        "payout_ranges": payout_ranges,
    }

    return result


if __name__ == "__main__":
    analysis = run_backtest_analysis("2026-01-01", "2026-04-20")
    print("\n=== RETURN CHECK ===")
    print(analysis["summary"])
