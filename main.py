# -*- coding: utf-8 -*-
import os

# =========================
# Pythonista ローカル用
# 必ず実値に変更
# =========================
os.environ.setdefault("JOB_MODE", "day")
os.environ.setdefault("SUPABASE_URL", "https://dpctymeddnggfolvvcyf.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRwY3R5bWVkZG5nZ2ZvbHZ2Y3lmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjUzNjE1OSwiZXhwIjoyMDkyMTEyMTU5fQ.4ifEIF0LIKqgPOm5jpl7PbXMSflD_IOlBzMlfoQMyzs")
os.environ.setdefault("LINE_CHANNEL_ACCESS_TOKEN", "iGY5wvLuLhTRZFGg8x3dk2T3OIH1XzBnrWNZicMvHGr7oT0RnpErALNchBCZa6GhwEM+FKrzxSLPfB/CT2Mu9r6j3+OQ7dW3s14JzS2cnoa0t9LbXHr0vaPyO0OxvMIIUxNRAYPl6jy4I4fo7don+wdB04t89/1O/w1cDnyilFU=")
os.environ.setdefault("LINE_USER_ID", "U35eae9930b7cc8be77398eb0210e3f15")

from data_pipeline.load_race import load_race_context
from models.predictor_v2 import predict_race
from betting.bet_selector_v2 import select_bets
from db.client import upsert
from notifications.formatter_v2 import format_prediction_message, format_skip_message
from notifications.notifier import send_line_message
from config.settings import MODEL_VERSION

from run_report import main as report_main
from run_results import main as results_main
from run_day_jobs import main as day_main
from run_night_jobs import main as night_main
from run_seed import main as seed_main
from run_odds import main as odds_main


def run_single_test():
    print("=== 3連単AI v2 実データテスト ===")

    venue_id = "01"
    race_no = 1
    race_date = "20260415"

    context = load_race_context(venue_id, race_no, race_date)

    print("race_id:", context["race_id"])
    print("entry件数:", len(context["entries"]))
    print("odds件数:", len(context["odds"]))

    prediction_result = predict_race(context)

    print("上位候補:")
    for row in prediction_result["candidates"][:10]:
        odds = row.get("odds")
        prob = row.get("probability", 0)
        ev = round(prob * odds, 3) if odds else None
        print(row["ticket"], "prob=", round(prob, 6), "odds=", odds, "ev=", ev)

    bets = select_bets(
        prediction_result,
        min_ev=0.90,
        min_odds=4.5,
        max_bets=3
    )

    if not bets:
        print("見送り")

        upsert("v2_predictions", {
            "race_id": context["race_id"],
            "model_version": MODEL_VERSION,
            "buy_flag": False,
            "race_rank": "SKIP",
            "race_score": 0,
            "confidence": 0,
            "expected_value": 0,
            "risk_score": 0.50,
            "inside_confidence": 0.50,
            "venue_score": 0.50,
            "recommended_points": 0,
            "skip_reason": "EV基準未達"
        }, on_conflict=["race_id", "model_version"])

        msg = format_skip_message(
            context,
            reason="EV基準未達",
            model_version=MODEL_VERSION
        )
        print("送信メッセージ:")
        print(msg)

        try:
            line_res = send_line_message(msg)
            print("LINE送信結果:", line_res)
        except Exception as e:
            print("LINE送信エラー:", repr(e))
        return

    print("買い目:")
    for b in bets:
        print(f"{b['ticket']}  オッズ:{b['odds']}  EV:{b['ev']}")

    pred_rows = upsert("v2_predictions", {
        "race_id": context["race_id"],
        "model_version": MODEL_VERSION,
        "buy_flag": True,
        "race_rank": "A" if len(bets) <= 2 else "B",
        "race_score": max(x["prob"] for x in bets),
        "confidence": max(x["prob"] for x in bets),
        "expected_value": max(x["ev"] for x in bets),
        "risk_score": 0.30,
        "inside_confidence": 0.65,
        "venue_score": 0.60,
        "recommended_points": len(bets),
        "skip_reason": None
    }, on_conflict=["race_id", "model_version"])

    print("prediction upsert result:", pred_rows)

    prediction_id = pred_rows[0]["id"]

    for rank, bet in enumerate(bets, 1):
        upsert("v2_prediction_tickets", {
            "prediction_id": prediction_id,
            "race_id": context["race_id"],
            "ticket": bet["ticket"],
            "ticket_rank": rank,
            "probability": bet["prob"],
            "odds": bet["odds"],
            "expected_value": bet["ev"],
            "confidence": bet["prob"],
            "recommended_bet_yen": 100,
            "is_recommended": True
        }, on_conflict=["prediction_id", "ticket"])

    print("Supabase保存完了")

    msg = format_prediction_message(
        context,
        bets,
        model_version=MODEL_VERSION
    )
    print("送信メッセージ:")
    print(msg)

    try:
        line_res = send_line_message(msg)
        print("LINE送信結果:", line_res)
    except Exception as e:
        print("LINE送信エラー:", repr(e))


def main():
    print("MAIN_PY_VERSION_TEST_20260420")
    job_mode = os.environ.get("JOB_MODE", "").strip().lower()

    print("JOB_MODE:", job_mode)
    print("MAIN_HAS_ODDS_BRANCH")

    if job_mode == "report":
        report_main()
    elif job_mode == "results":
        results_main()
    elif job_mode == "day":
        day_main()
    elif job_mode == "night":
        night_main()
    elif job_mode == "seed":
        seed_main()
    elif job_mode == "odds":
        print("RUN_ODDS_BRANCH")
        odds_main()
    else:
        print("RUN_SINGLE_TEST_BRANCH")
        run_single_test()


if __name__ == "__main__":
    main()
