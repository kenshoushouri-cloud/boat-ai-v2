# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from data_pipeline.load_race_list import load_race_list
from data_pipeline.load_race import load_race_context
from models.predictor_v2 import predict_race
from betting.bet_selector_v2 import select_bets
from models.risk_manager import judge_race_adoption


def daterange(start, end):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def run_backtest(start_date, end_date):
    print("=== バックテスト開始 ===")
    print("期間:", start_date, "→", end_date)

    total_bets = 0
    total_hits = 0
    total_races = 0

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    for d in daterange(start, end):
        date_str = d.strftime("%Y-%m-%d")
        print("\n---", date_str, "---")

        races = load_race_list(date_str, session_type="day")

        day_bets = 0
        day_hits = 0

        for r in races:
            context = load_race_context(
                r["venue_id"],
                r["race_no"],
                date_str
            )

            if not context:
                continue

            pred = predict_race(context)
            bets = select_bets(pred, max_bets=2)

            adopt, _ = judge_race_adoption(context, pred, bets)
            if not adopt:
                continue

            race_score = pred.get("race_score", 0)
            if race_score < 0.06:
                continue

            result = context.get("result")

            for b in bets:
                day_bets += 1
                total_bets += 1

                if result and b["ticket"] == result:
                    day_hits += 1
                    total_hits += 1

        total_races += 1

        hit_rate = (day_hits / day_bets * 100) if day_bets else 0
        print(f"日次: {day_bets}点 的中{day_hits} 的中率{hit_rate:.1f}%")

    overall = (total_hits / total_bets * 100) if total_bets else 0

    print("\n=== 総合結果 ===")
    print("総投資:", total_bets)
    print("総的中:", total_hits)
    print(f"的中率: {overall:.1f}%")
