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

# 1日の最大点数
MAX_POINTS_PER_DAY = 10


def run_morning_summary_job(race_date):
    print("=== 朝まとめ予想ジョブ開始 ===")
    print("対象日:", race_date)

    # 昼・夜 全レース取得
    all_races = load_race_list(
        race_date=race_date,
        venue_ids=["01", "06", "12", "18", "24"]
    )
    print("全レース数:", len(all_races))

    candidate_results = []

    for r in all_races:
        venue_id = r.get("venue_id")
        race_no = r.get("race_no")

        context = load_race_context(venue_id, race_no, race_date)
        if not context:
            continue

        try:
            prediction_result = predict_race(context)
        except Exception as e:
            print(f"predict error: {r.get('race_id')} {e}")
            continue

        bets = select_bets(prediction_result)

        adopt, reason = judge_race_adoption(context, prediction_result, bets)
        if not adopt:
            print(f"  skip: {r.get('race_id')} {reason}")
            continue

        candidate_results.append({
            "race_id": context["race_id"],
            "venue_id": venue_id,
            "race_no": race_no,
            "session_type": r.get("session_type", ""),
            "bets": bets,
            "weather": context.get("weather", {}),
            "race_score": prediction_result.get("race_score", 0.0),
            "prediction_result": prediction_result,
        })

    # race_scoreの高い順にソート
    candidate_results.sort(key=lambda x: x["race_score"], reverse=True)

    # 合計点数がMAX_POINTS_PER_DAY以内になるように絞り込む
    adopted = []
    total_points = 0
    for result in candidate_results:
        bet_count = len(result["bets"])
        if total_points + bet_count > MAX_POINTS_PER_DAY:
            continue
        adopted.append(result)
        total_points += bet_count
        if total_points >= MAX_POINTS_PER_DAY:
            break

    print(f"採用レース数: {len(adopted)}レース / {total_points}点")

    # 採用レースをDBに保存
    for result in adopted:
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
                "notification_type": "morning_summary",
            }, on_conflict=["race_id", "model_version"])

    if not adopted:
        msg = f"【朝まとめ予想 {race_date}】\n本日の推奨レースなし\nModel: {MODEL_VERSION}"
        print(msg)
        send_line_message(msg)
        return

    msg = format_batch_prediction_message(
        adopted,
        title=f"朝まとめ予想 {race_date}",
        model_version=MODEL_VERSION
    )
    print(msg)
    res = send_line_message(msg)
    print("LINE送信結果:", res)