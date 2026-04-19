# -*- coding: utf-8 -*-
from data_pipeline.load_race_list import load_race_list
from data_pipeline.load_race import load_race_context
from models.predictor_v2 import predict_race
from betting.bet_selector_v2 import select_bets
from models.risk_manager import judge_race_adoption
from notifications.formatter_v2 import format_batch_prediction_message
from notifications.notifier import send_line_message
from db.client import upsert
from config.settings import MODEL_VERSION


def save_notification_log(target_date, message_body, notification_type, delivery_result, race_id=None, venue_id=None):
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


def run_day_prediction_job(race_date):
    print("=== 昼予想ジョブ開始 ===")

    races = load_race_list(
        race_date=race_date,
        session_type="day",
        venue_ids=["01", "06", "12", "18", "24"]
    )

    print("対象レース数:", len(races))

    all_results = []

    for r in races:
        venue_id = r.get("venue_id")
        race_no = r.get("race_no")

        context = load_race_context(venue_id, race_no, race_date)

        if not context:
            continue

        prediction_result = predict_race(context)

        bets = select_bets(
            prediction_result,
            min_ev=1.2,
            min_odds=6.0,
            max_bets=3
        )

        adopt, reason = judge_race_adoption(context, prediction_result, bets)

        if not adopt:
            continue

        all_results.append({
            "race_id": context["race_id"],
            "venue_id": venue_id,
            "race_no": race_no,
            "bets": bets,
            "weather": context.get("weather", {})
        })

    if not all_results:
        msg = "【昼開催予想】\n推奨レースなし\nModel: " + MODEL_VERSION
        print(msg)

        res = send_line_message(msg)
        print(res)

        save_notification_log(
            race_date,
            msg,
            "day_prediction",
            res
        )
        return

    msg = format_batch_prediction_message(
        all_results,
        title="昼開催 推奨レース",
        model_version=MODEL_VERSION
    )

    print(msg)

    res = send_line_message(msg)
    print(res)

    save_notification_log(
        race_date,
        msg,
        "day_prediction",
        res
    )
