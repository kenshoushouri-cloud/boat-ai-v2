# -*- coding: utf-8 -*-
"""
バックテストランナー

2モード対応:
- stable: 安定モード（1日最大7点）
- ana:    馬王モード・穴狙い（1日最大5点）

使い方:
    from backtest.runner import run_backtest
    run_backtest("2025-03-13", "2026-04-30", mode="stable")
    run_backtest("2025-03-13", "2026-04-30", mode="ana")
"""

import urllib.parse
import requests as http_requests
from datetime import datetime, timedelta

from data_pipeline.load_race import load_race_context
from models.predictor_v2 import predict_race
from backtest.scenario import detect_scenario_type
from db.client import upsert
from config.settings import SUPABASE_URL, SUPABASE_KEY, MODEL_VERSION

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

TARGET_VENUES = ["01", "06", "12", "18", "24"]

# ============================================================
# モード別パラメータ
# ============================================================

MODE_PARAMS = {
    "stable": {
        "race_score_min": 0.18,     # レーススコア足切り
        "exacta_top1_min": 0.055,   # 2連単1位確率の下限
        "max_bets_per_race": 2,     # 1レース最大買い目
        "max_points_per_day": 7,    # 1日最大点数
        "odds_min": None,           # オッズ下限なし（朝時点ではオッズ未確定）
        "description": "安定モード",
    },
    "ana": {
        "race_score_min": 0.12,     # 緩め（穴狙いなのでスコアより確率重視）
        "exacta_top1_min": 0.040,
        "max_bets_per_race": 1,     # 1点勝負
        "max_points_per_day": 5,    # 1日最大5点
        "odds_min": 15.0,           # 15倍以上の穴のみ
        "description": "馬王モード（穴狙い）",
    },
}


# ============================================================
# データ取得
# ============================================================

def _fetch_race_list_for_date(race_date):
    url = (
        f"{SUPABASE_URL}/rest/v1/v2_races"
        f"?select=race_id,venue_id,race_no,session_type"
        f"&race_date=eq.{race_date}"
        f"&limit=1000"
    )
    try:
        res = http_requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            return []
        return res.json()
    except Exception:
        return []


def _fetch_result(race_id):
    url = (
        f"{SUPABASE_URL}/rest/v1/v2_results"
        f"?select=trifecta_ticket,trifecta_payout_yen,result_status"
        f"&race_id=eq.{urllib.parse.quote(race_id)}"
        f"&limit=1"
    )
    try:
        res = http_requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            return None
        rows = res.json()
        return rows[0] if rows else None
    except Exception:
        return None


def _daterange(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    cur = start
    while cur <= end:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)


# ============================================================
# モード別買い目選択
# ============================================================

def _select_bets(prediction_result, params):
    candidates = prediction_result.get("candidates", [])
    exacta_candidates = prediction_result.get("exacta_candidates", [])
    race_score = prediction_result.get("race_score", 0.0)

    if not candidates or not exacta_candidates:
        return []

    exacta_top1 = exacta_candidates[0].get("probability", 0.0)

    if race_score < params["race_score_min"]:
        return []
    if exacta_top1 < params["exacta_top1_min"]:
        return []

    # 穴モードはオッズ下限チェック
    odds_min = params.get("odds_min")
    if odds_min:
        top_odds = candidates[0].get("odds")
        if top_odds is None or top_odds < odds_min:
            return []

    top = candidates[0]
    bets = [{
        "ticket": top["ticket"],
        "prob": top.get("probability", 0.0),
        "odds": top.get("odds"),
        "ev": top.get("ev"),
        "bet_type": "trifecta",
    }]

    if params["max_bets_per_race"] >= 2:
        top_first = top["ticket"].split("-")[0]
        for c in candidates[1:]:
            first = c["ticket"].split("-")[0]
            if first == top_first:
                bets.append({
                    "ticket": c["ticket"],
                    "prob": c.get("probability", 0.0),
                    "odds": c.get("odds"),
                    "ev": c.get("ev"),
                    "bet_type": "trifecta",
                })
                break

    return bets[:params["max_bets_per_race"]]


# ============================================================
# 1レースのバックテスト
# ============================================================

def _backtest_one_race(race_date, venue_id, race_no, session_type, run_id, params):
    race_id = f"{race_date.replace('-', '')}_{venue_id}_{int(race_no):02d}"

    context = load_race_context(venue_id, race_no, race_date)
    if not context:
        return None

    entries = context.get("entries", [])
    odds = context.get("odds", {})

    if len(entries) < 6:
        return None
    if not odds:
        return None

    try:
        prediction_result = predict_race(context)
    except Exception as e:
        print(f"  predict error: {race_id} {e}")
        return None

    bets = _select_bets(prediction_result, params)
    adopt = len(bets) > 0
    reason = None if adopt else "閾値未達"

    scenario = detect_scenario_type(context, prediction_result)

    actual = _fetch_result(race_id)
    if not actual:
        return None

    actual_ticket = actual.get("trifecta_ticket")
    actual_payout = int(actual.get("trifecta_payout_yen") or 0)
    result_status = actual.get("result_status", "")

    if result_status != "official":
        return None

    stake_yen = len(bets) * 100 if adopt else 0
    payout_yen = 0
    hit = False
    trigami = False

    if adopt and bets:
        for bet in bets:
            if bet["ticket"] == actual_ticket:
                payout_yen = actual_payout
                hit = True
                if actual_payout < 100:
                    trigami = True
                break

    profit = payout_yen - stake_yen

    candidates = prediction_result.get("candidates", [])
    top1_prob = candidates[0].get("probability", 0) if candidates else 0
    top2_prob = candidates[1].get("probability", 0) if len(candidates) >= 2 else 0

    return {
        "run_id": run_id,
        "race_id": race_id,
        "race_date": race_date,
        "race_no": race_no,
        "venue_id": venue_id,
        "session_type": session_type,
        "scenario_type": scenario,
        "buy_flag": adopt,
        "skip_reason": reason,
        "predicted_ticket_count": len(bets) if adopt else 0,
        "winning_ticket": actual_ticket,
        "stake_yen": stake_yen,
        "payout_yen": payout_yen,
        "hit_flag": hit,
        "profit_yen": profit,
        "trigami": trigami,
        "race_score": prediction_result.get("race_score", 0.0),
        "top1_ticket": bets[0]["ticket"] if bets else None,
        "top1_prob": top1_prob,
        "top2_prob": top2_prob,
        "prob_gap": round(top1_prob - top2_prob, 6),
        "max_ev": bets[0].get("ev") if bets else None,
        "top1_odds": bets[0].get("odds") if bets else None,
    }


# ============================================================
# サマリー集計
# ============================================================

def _summarize(results, run_id, start_date, end_date, mode):
    adopted = [r for r in results if r["buy_flag"]]
    hits = [r for r in adopted if r["hit_flag"]]
    trigamis = [r for r in hits if r["trigami"]]

    total_races = len(results)
    adopted_races = len(adopted)
    total_stake = sum(r["stake_yen"] for r in adopted)
    total_payout = sum(r["payout_yen"] for r in adopted)
    profit = total_payout - total_stake
    roi = (total_payout / total_stake * 100) if total_stake > 0 else 0.0
    hit_rate = (len(hits) / adopted_races * 100) if adopted_races > 0 else 0.0
    trigami_rate = (len(trigamis) / len(hits) * 100) if hits else 0.0

    # 日数
    days = len(set(r["race_date"] for r in adopted)) if adopted else 1
    avg_points_per_day = len(adopted) / days if days > 0 else 0
    avg_stake_per_day = total_stake / days if days > 0 else 0
    avg_profit_per_day = profit / days if days > 0 else 0

    scenario_stats = {}
    for r in adopted:
        sc = r["scenario_type"]
        if sc not in scenario_stats:
            scenario_stats[sc] = {"count": 0, "hit": 0, "stake": 0, "payout": 0}
        scenario_stats[sc]["count"] += 1
        scenario_stats[sc]["stake"] += r["stake_yen"]
        scenario_stats[sc]["payout"] += r["payout_yen"]
        if r["hit_flag"]:
            scenario_stats[sc]["hit"] += 1

    print("\n" + "=" * 50)
    print(f"バックテスト結果: {start_date} -> {end_date} [{mode}]")
    print("=" * 50)
    print(f"対象レース数:       {total_races}")
    print(f"採用レース数:       {adopted_races}")
    print(f"的中レース数:       {len(hits)}")
    print(f"的中率:             {hit_rate:.1f}%")
    print(f"投資額:             {total_stake:,}円")
    print(f"回収額:             {total_payout:,}円")
    print(f"損益:               {profit:+,}円")
    print(f"回収率:             {roi:.1f}%")
    print(f"トリガミ率:         {trigami_rate:.1f}%")
    print(f"1日平均点数:        {avg_points_per_day:.1f}点")
    print(f"1日平均投資:        {avg_stake_per_day:.0f}円")
    print(f"1日平均損益:        {avg_profit_per_day:+.0f}円")

    print("\n--- シナリオ別 ---")
    for sc, s in sorted(scenario_stats.items()):
        sc_roi = (s["payout"] / s["stake"] * 100) if s["stake"] > 0 else 0
        sc_hit = (s["hit"] / s["count"] * 100) if s["count"] > 0 else 0
        print(f"  {sc}: {s['count']}レース 的中{sc_hit:.0f}% ROI{sc_roi:.0f}%")

    summary = {
        "run_id": run_id,
        "model_version": MODEL_VERSION,
        "target_start_date": start_date,
        "target_end_date": end_date,
        "total_races": total_races,
        "adopted_races": adopted_races,
        "hit_races": len(hits),
        "hit_rate": round(hit_rate, 2),
        "total_stake_yen": total_stake,
        "total_payout_yen": total_payout,
        "profit_yen": profit,
        "roi": round(roi, 2),
        "trigami_rate": round(trigami_rate, 2),
        "scenario_stats": str(scenario_stats),
        "note": f"mode={mode} avg_points={avg_points_per_day:.1f}/day",
    }

    upsert("v2_backtest_runs", summary, on_conflict="run_id")
    return summary


# ============================================================
# メイン
# ============================================================

def run_backtest(start_date, end_date, mode="stable", run_id=None):
    params = MODE_PARAMS.get(mode, MODE_PARAMS["stable"])

    if run_id is None:
        run_id = f"{MODEL_VERSION}_{mode}_{start_date}_{end_date}"

    print(f"=== バックテスト開始 ===")
    print(f"モード: {params['description']}")
    print(f"期間: {start_date} -> {end_date}")
    print(f"run_id: {run_id}")

    all_results = []

    for race_date in _daterange(start_date, end_date):
        races = _fetch_race_list_for_date(race_date)
        if not races:
            continue

        # 日次の点数管理
        day_points = 0
        day_candidates = []

        for r in races:
            venue_id = str(r.get("venue_id", "")).zfill(2)
            if venue_id not in TARGET_VENUES:
                continue
            race_no = r.get("race_no")
            session_type = r.get("session_type", "")

            result = _backtest_one_race(
                race_date, venue_id, race_no, session_type, run_id, params
            )
            if result:
                day_candidates.append(result)

        # race_scoreの高い順に並べて1日の点数上限内で採用
        day_candidates.sort(key=lambda x: x["race_score"], reverse=True)

        for result in day_candidates:
            if result["buy_flag"]:
                if day_points + result["predicted_ticket_count"] > params["max_points_per_day"]:
                    # 上限超えるので見送りに変更
                    result["buy_flag"] = False
                    result["skip_reason"] = "1日点数上限"
                    result["stake_yen"] = 0
                    result["payout_yen"] = 0
                    result["profit_yen"] = 0
                    result["hit_flag"] = False
                else:
                    day_points += result["predicted_ticket_count"]

            upsert("v2_backtest_races", result, on_conflict="race_id,run_id")
            all_results.append(result)

            status = "HIT" if result["hit_flag"] else ("採用" if result["buy_flag"] else "見送")
            if result["buy_flag"] or result["hit_flag"]:
                print(f"  {result['race_id']} {status} profit={result['profit_yen']:+d}円")

        if day_points > 0:
            print(f"{race_date}: {day_points}点採用")

    if not all_results:
        print("結果なし")
        return None

    return _summarize(all_results, run_id, start_date, end_date, mode)


if __name__ == "__main__":
    run_backtest(
        start_date="2025-03-13",
        end_date="2026-04-30",
        mode="stable",
    )