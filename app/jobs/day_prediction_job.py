from collections import defaultdict

from models.predictor_v2 import predict_race


MAX_RACES_PER_DAY = 5   # ←ここが超重要
MIN_RACES_PER_DAY = 3   # 最低ライン


def run_day_prediction_job(target_date, race_contexts):
    results = []

    # =========================
    # 1 全レース予想
    # =========================
    for context in race_contexts:
        try:
            res = predict_race(context)

            if not res:
                continue

            results.append(res)

        except Exception as e:
            print("predict error:", context.get("race_id"), e)

    if not results:
        return []

    # =========================
    # 2 race_scoreで並び替え
    # =========================
    results.sort(key=lambda x: x["race_score"], reverse=True)

    # =========================
    # 3 上位だけ採用
    # =========================
    adopted = results[:MAX_RACES_PER_DAY]

    # 最低件数を満たす(データ薄い日の保険)
    if len(adopted) < MIN_RACES_PER_DAY:
        adopted = results[:MIN_RACES_PER_DAY]

    # =========================
    # 4 デバッグログ
    # =========================
    print("=== 採用レースランキング ===")
    for r in adopted:
        print(
            "adopt:",
            r["race_id"],
            "score=", round(r["race_score"], 6)
        )

    return adopted
