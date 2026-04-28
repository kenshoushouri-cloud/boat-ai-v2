# -*- coding: utf-8 -*-
from models.predictor_v2 import predict_race
from betting.bet_selector_v2 import select_bets
from models.risk_manager import judge_race_adoption
from notifications.formatter_v2 import format_batch_prediction_message
from notifications.notifier import send_line_message
from db.client import upsert
from config.settings import (
    MODEL_VERSION,
    MAX_BETS_PER_RACE,
    RACE_SCORE_THRESHOLD,
    MAX_DAILY_BETS,
)

MAX_RECOMMEND_RACES = 5


def _calc_race_score(prediction_result, bets):
    candidates = prediction_result.get("candidates", [])
    top1 = candidates[0].get("probability", 0) if len(candidates) >= 1 else 0
    top2 = candidates[1].get("probability", 0) if len(candidates) >= 2 else 0
    gap = top1 - top2
    bet_prob_total = sum(b.get("prob", 0) for b in bets)
    score = (top1 * 0.5) + (gap * 20.0) + (bet_prob_total * 0.5)
    return round(score, 6)


def run_day_prediction_job(race_date, race_contexts):
    print("=== 昼予想ジョブ開始 ===")
    print("RACE_SCORE_THRESHOLD:", RACE_SCORE_THRESHOLD)
    print("対象レース数:", len(race_contexts))

    candidate_results = []

    for context in race_contexts:
        race_id = context.get("race_id")
        venue_id = context.get("venue_id")
        race_no = context.get("race_no")

        print(
            "race check:",
            race_id,
            "entries=", len(context.get("entries", [])),
            "odds=", len(context.get("odds", {})),
            "exhibition=", len(context.get("exhibition", {}))
        )

        try:
            prediction_result = predict_race(context)
        except Exception as e:
            print(f"predict error: {race_id} {e}")
            continue

        print("candidate_count:", race_id, len(prediction_result.get("candidates", [])))

        bets = select_bets(prediction_result, max_bets=MAX_BETS_PER_RACE)
        print("bet_count:", race_id, len(bets))

        adopt, reason = judge_race_adoption(context, prediction_result, bets)
        print("adopt:", race_id, adopt, reason)

        if not adopt:
            continue

        race_score = _calc_race_score(prediction_result, bets)
        print("race_score:", race_id, race_score)

        if race_score < RACE_SCORE_THRESHOLD:
            print("skip by race_score:", race_id, race_score)
            continue

        candidate_results.append({
            "race_id": race_id,
            "venue_id": venue_id,
            "race_no": race_no,
            "bets": bets,
            "weather": context.get("weather", {}),
            "odds_available": len(context.get("odds", {})) > 0,
            "race_score": race_score,
        })

    # race_scoreの高い順にソート
    candidate_results.sort(key=lambda x: x["race_score"], reverse=True)

    # 合計点数がMAX_DAILY_BETS以内になるように絞り込む
    all_results = []
    total_points = 0
    for result in candidate_results:
        bet_count = len(result["bets"])
        if total_points + bet_count > MAX_DAILY_BETS:
            continue
        all_results.append(result)
        total_points += bet_count
        if total_points >= MAX_DAILY_BETS:
            break

    all_results = all_results[:MAX_RECOMMEND_RACES]
    print("採用レース数:", len(all_results))

    if not all_results:
        msg = "【昼開催予想】\n推奨レースなし\nModel: " + MODEL_VERSION
        print(msg)
        res = send_line_message(msg)
        print(res)
        upsert("v2_notifications", {
            "notification_type": "day_prediction",
            "target_date": race_date,
            "message_body": msg,
            "delivery_status": "sent" if res.get("ok") else "failed",
            "line_response": res.get("text"),
        }, on_conflict="notification_type,target_date")
        return []

    # DB保存
    for result in all_results:
        for rank, bet in enumerate(result["bets"], 1):
            upsert("v2_predictions", {
                "race_id": result["race_id"],
                "model_version": MODEL_VERSION,
                "buy_flag": True,
                "race_score": result["race_score"],
                "ticket": bet["ticket"],
                "ticket_rank": rank,
                "probability": bet["prob"],
                "odds": bet.get("odds"),
                "expected_value": bet.get("ev"),
                "recommended_bet_yen": 100,
                "notification_type": "day_prediction",
            }, on_conflict="race_id,model_version,ticket")

    # LINE送信
    msg = format_batch_prediction_message(
        all_results,
        title="昼開催 推奨レース",
        model_version=MODEL_VERSION
    )
    print(msg)
    res = send_line_message(msg)
    print(res)

    upsert("v2_notifications", {
        "notification_type": "day_prediction",
        "target_date": race_date,
        "message_body": msg,
        "delivery_status": "sent" if res.get("ok") else "failed",
        "line_response": res.get("text"),
    }, on_conflict="notification_type,target_date")

    return all_results