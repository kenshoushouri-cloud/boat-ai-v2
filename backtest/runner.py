# -*- coding: utf-8 -*-
from db.client import select_where, insert
from data_pipeline.load_race_list import load_race_list
from data_pipeline.load_race import load_race_context
from models.predictor_v2 import predict_race
from betting.bet_selector_v2 import select_bets
from models.risk_manager import judge_race_adoption
from backtest.scenario import detect_scenario_type
from config.settings import MODEL_VERSION


def _find_winning_ticket(race_id):
    rows = select_where("v2_results", {"race_id": race_id}, limit=1)
    if not rows:
        return None, 0

    row = rows[0]
    return row.get("trifecta_ticket"), int(row.get("trifecta_payout_yen") or 0)


def run_backtest_for_date(target_date, venue_ids=None, session_type=None):
    print("=== バックテスト開始 ===")
    print("対象日:", target_date)

    run_rows = insert("v2_backtest_runs", {
        "run_date": target_date,
        "model_version": MODEL_VERSION,
        "target_start_date": target_date,
        "target_end_date": target_date,
        "venue_filter": ",".join(venue_ids) if venue_ids else None,
        "note": "single day backtest"
    })

    run_id = run_rows[0]["id"]
    print("run_id:", run_id)

    races = load_race_list(
        race_date=target_date,
        session_type=session_type,
        venue_ids=venue_ids
    )

    print("対象レース数:", len(races))

    for r in races:
        venue_id = r.get("venue_id")
        race_no = r.get("race_no")

        context = load_race_context(venue_id, race_no, target_date)
        if not context:
            continue

        prediction_result = predict_race(context)
        candidates = prediction_result.get("candidates", [])

        bets = select_bets(
            prediction_result,
            min_ev=1.1,
            min_odds=4.0,
            max_bets=3,
            max_odds=120.0,
            max_ev=6.0
        )

        adopt, reason = judge_race_adoption(context, prediction_result, bets)
        scenario_type = detect_scenario_type(context, prediction_result)

        top1_prob = candidates[0].get("probability", 0) if len(candidates) >= 1 else 0
        top2_prob = candidates[1].get("probability", 0) if len(candidates) >= 2 else 0
        prob_gap = top1_prob - top2_prob

        max_ev = max([b.get("ev", 0) for b in bets], default=0)

        winning_ticket, payout_yen = _find_winning_ticket(context["race_id"])

        buy_flag = bool(adopt and bets)
        hit_flag = False
        stake_yen = 0

        if buy_flag:
            stake_yen = len(bets) * 100
            hit_flag = any(b["ticket"] == winning_ticket for b in bets)

        actual_payout = 0
        if hit_flag:
            actual_payout = payout_yen

        roi = 0
        if stake_yen > 0:
            roi = round(actual_payout / stake_yen, 2)

        race_rows = insert("v2_backtest_races", {
            "run_id": run_id,
            "race_id": context["race_id"],
            "race_date": target_date,
            "venue_id": venue_id,
            "race_no": race_no,
            "session_type": r.get("session_type"),
            "scenario_type": scenario_type,
            "buy_flag": buy_flag,
            "hit_flag": hit_flag,
            "predicted_ticket_count": len(bets),
            "winning_ticket": winning_ticket,
            "stake_yen": stake_yen,
            "payout_yen": actual_payout,
            "roi": roi,
            "top1_prob": round(top1_prob, 6),
            "top2_prob": round(top2_prob, 6),
            "prob_gap": round(prob_gap, 6),
            "max_ev": round(max_ev, 3),
            "adopted_reason": None if buy_flag else None,
            "skip_reason": None if buy_flag else reason
        })

        backtest_race_id = race_rows[0]["id"]

        for rank, bet in enumerate(bets, 1):
            ticket_hit = (bet["ticket"] == winning_ticket)
            ticket_payout = payout_yen if ticket_hit else 0

            insert("v2_backtest_tickets", {
                "backtest_race_id": backtest_race_id,
                "race_id": context["race_id"],
                "ticket": bet["ticket"],
                "ticket_rank": rank,
                "probability": round(bet.get("prob", 0), 6),
                "odds": round(bet.get("odds", 0), 3),
                "expected_value": round(bet.get("ev", 0), 3),
                "hit_flag": ticket_hit,
                "payout_yen": ticket_payout
            })

        print(
            "race:",
            context["race_id"],
            "buy=", buy_flag,
            "bets=", len(bets),
            "win=", winning_ticket,
            "hit=", hit_flag,
            "roi=", roi
        )

    print("=== バックテスト完了 ===")
    print("run_id:", run_id)
