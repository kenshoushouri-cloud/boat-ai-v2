# -*- coding: utf-8 -*-
from data_pipeline.load_race_list import load_race_list
from data_pipeline.load_race import load_race_context
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
)


MAX_RECOMMEND_RACES = 5


def save_notification_log(
    target_date,
    message_body,
    notification_type,
    delivery_result,
    race_id=None,
    venue_id=None
):
    upsert("v2_notifications", {
        "notification_type": notification_type,
        "target_date": target_date,
        "race_id": race_id,
        "venue_id": venue_id,
        "message_body": message_body,
        "delivery_status": "sent" if delivery_result.get("ok") else "failed",
        "retry_key": None,
        "line_response": delivery_result.get("text"),
        "sent_at": None
    }, on_conflict=["id"])


def _calc_race_score(prediction_result, bets):
    candidates = prediction_result.get("candidates", [])

    top1 = candidates[0].get("probability", 0) if len(candidates) >= 1 else 0
    top2 = candidates[1].get("probability", 0) if len(candidates) >= 2 else 0
    gap = top1 - top2

    bet_prob_total = sum(b.get("prob", 0) for b in bets)

    score = (top1 * 0.5) + (gap * 20.0) + (bet_prob_total * 0.5)
    return round(score, 6)


def run_night_prediction_job(race_date):
    print("=== 夜予想ジョブ開始 ===")
    print("RACE_SCORE_THRESHOLD:", RACE_SCORE_THRESHOLD)

    races = load_race_list(
        race_date=race_date,
        session_type="night",
        venue_ids=["01", "06", "12", "18", "24"]
    )

    print("対象レース数:", len(races))

    candidate_results = []

    for r in races:
        venue_id = r.get("venue_id")
        race_no = r.get("race_no")

        context = load_race_context(venue_id, race_no, race_date)
        if not context:
            print("contextなし:", venue_id, race_no)
            continue

        print(
            "race check:",
            context["race_id"],
            "entries=", len(context.get("entries", [])),
            "odds=", len(context.get("odds", {})),
            "weather=", bool(context.get("weather")),
            "exhibition=", len(context.get("exhibition", {}))
        )

        prediction_result = predict_race(context)
        print(
            "candidate_count:",
            context["race_id"],
            len(prediction_result.get("candidates", []))
        )

        bets = select_bets(
            prediction_result,
            max_bets=MAX_BETS_PER_RACE
        )
        print("bet_count:", context["race_id"], len(bets))

        adopt, reason = judge_race_adoption(context, prediction_result, bets)
        print("adopt:", context["race_id"], adopt, reason)

        if not adopt:
            continue

        race_score = _calc_race_score(prediction_result, bets)
        print("race_score:", context["race_id"], race_score)

        if race_score < RACE_SCORE_THRESHOLD:
            print("skip by race_score:", context["race_id"], race_score)
            continue

        candidate_results.append({
            "race_id": context["race_id"],
            "venue_id": venue_id,
            "race_no": race_no,
            "bets": bets,
            "weather": context.get("weather", {}),
            "odds_available": len(context.get("odds", {})) > 0,
            "race_score": race_score
        })

    candidate_results = sorted(
        candidate_results,
        key=lambda x: x["race_score"],
        reverse=True
    )

    all_results = candidate_results[:MAX_RECOMMEND_RACES]

    print("採用レース数:", len(all_results))

    if not all_results:
        msg = "【夜開催予想】\n推奨レースなし\nModel: " + MODEL_VERSION
        print(msg)

        res = send_line_message(msg)
        print(res)

        save_notification_log(
            race_date,
            msg,
            "night_prediction",
            res
        )
        return

    msg = format_batch_prediction_message(
        all_results,
        title="夜開催 推奨レース",
        model_version=MODEL_VERSION
    )

    print(msg)

    res = send_line_message(msg)
    print(res)

    save_notification_log(
        race_date,
        msg,
        "night_prediction",
        res
    )
