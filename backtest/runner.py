# -*- coding: utf-8 -*-
"""
バックテストランナー

過去データ（v2_races・v2_race_entries・v2_odds_trifecta・v2_results）を使って
予測モデルの精度を検証する。

使い方:
    from backtest.runner import run_backtest
    run_backtest("2025-04-01", "2025-12-31")
"""

import urllib.parse
import requests as http_requests
from datetime import datetime, timedelta

from data_pipeline.load_race import load_race_context
from models.predictor_v2 import predict_race
from betting.bet_selector_v2 import select_bets
from models.risk_manager import judge_race_adoption
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
# データ取得
# ============================================================

def _fetch_race_ids_for_date(race_date):
    """対象日の全race_idを取得"""
    url = (
        f"{SUPABASE_URL}/rest/v1/v2_races"
        f"?select=race_id,venue_id,race_no"
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
    """v2_resultsから結果を取得"""
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
# 1レースのバックテスト
# ============================================================

def _backtest_one_race(race_date, venue_id, race_no, run_id):
    race_id = f"{race_date.replace('-', '')}_{venue_id}_{int(race_no):02d}"

    # コンテキスト構築
    context = load_race_context(venue_id, race_no, race_date)
    if not context:
        return None

    entries = context.get("entries", [])
    odds = context.get("odds", {})

    if len(entries) < 6:
        return None
    if not odds:
        return None

    # 予測
    try:
        prediction_result = predict_race(context)
    except Exception as e:
        print(f"  predict error: {race_id} {e}")
        return None

    # 買い目選択
    bets = select_bets(prediction_result)
    adopt, reason = judge_race_adoption(context, prediction_result, bets)

    # シナリオ判定
    scenario = detect_scenario_type(context, prediction_result)

    # 実績取得
    actual = _fetch_result(race_id)
    if not actual:
        return None

    actual_ticket = actual.get("trifecta_ticket")
    actual_payout = int(actual.get("trifecta_payout_yen") or 0)
    result_status = actual.get("result_status", "")

    if result_status != "official":
        return None

    # 結果集計
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

    result = {
        "run_id": run_id,
        "race_id": race_id,
        "venue_id": venue_id,
        "race_no": race_no,
        "race_date": race_date,
        "model_version": MODEL_VERSION,
        "scenario": scenario,
        "adopted": adopt,
        "skip_reason": reason if not adopt else None,
        "bet_count": len(bets) if adopt else 0,
        "stake_yen": stake_yen,
        "actual_ticket": actual_ticket,
        "actual_payout_yen": actual_payout,
        "hit": hit,
        "payout_yen": payout_yen,
        "profit_yen": profit,
        "trigami": trigami,
        "race_score": prediction_result.get("race_score", 0.0),
        "top1_ticket": bets[0]["ticket"] if bets else None,
        "top1_prob": bets[0]["prob"] if bets else None,
        "top1_odds": bets[0]["odds"] if bets else None,
        "top1_ev": bets[0]["ev"] if bets else None,
    }

    # DB保存
    upsert("v2_backtest_races", result, on_conflict="race_id,run_id")

    return result


# ============================================================
# サマリー集計
# ============================================================

def _summarize(results, run_id, start_date, end_date):
    adopted = [r for r in results if r["adopted"]]
    hits = [r for r in adopted if r["hit"]]
    trigamis = [r for r in hits if r["trigami"]]

    total_races = len(results)
    adopted_races = len(adopted)
    total_stake = sum(r["stake_yen"] for r in adopted)
    total_payout = sum(r["payout_yen"] for r in adopted)
    profit = total_payout - total_stake
    roi = (total_payout / total_stake * 100) if total_stake > 0 else 0.0
    hit_rate = (len(hits) / adopted_races * 100) if adopted_races > 0 else 0.0
    trigami_rate = (len(trigamis) / len(hits) * 100) if hits else 0.0

    # シナリオ別集計
    scenario_stats = {}
    for r in adopted:
        sc = r["scenario"]
        if sc not in scenario_stats:
            scenario_stats[sc] = {"count": 0, "hit": 0, "stake": 0, "payout": 0}
        scenario_stats[sc]["count"] += 1
        scenario_stats[sc]["stake"] += r["stake_yen"]
        scenario_stats[sc]["payout"] += r["payout_yen"]
        if r["hit"]:
            scenario_stats[sc]["hit"] += 1

    print("\n" + "=" * 50)
    print(f"バックテスト結果: {start_date} -> {end_date}")
    print("=" * 50)
    print(f"対象レース数:   {total_races}")
    print(f"採用レース数:   {adopted_races}")
    print(f"的中レース数:   {len(hits)}")
    print(f"的中率:         {hit_rate:.1f}%")
    print(f"投資額:         {total_stake:,}円")
    print(f"回収額:         {total_payout:,}円")
    print(f"損益:           {profit:+,}円")
    print(f"回収率:         {roi:.1f}%")
    print(f"トリガミ率:     {trigami_rate:.1f}%")

    print("\n--- シナリオ別 ---")
    for sc, s in sorted(scenario_stats.items()):
        sc_roi = (s["payout"] / s["stake"] * 100) if s["stake"] > 0 else 0
        sc_hit = (s["hit"] / s["count"] * 100) if s["count"] > 0 else 0
        print(f"  {sc}: {s['count']}レース 的中{sc_hit:.0f}% ROI{sc_roi:.0f}%")

    summary = {
        "run_id": run_id,
        "model_version": MODEL_VERSION,
        "start_date": start_date,
        "end_date": end_date,
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
    }

    upsert("v2_backtest_runs", summary, on_conflict="run_id")
    return summary


# ============================================================
# メイン
# ============================================================

def run_backtest(start_date, end_date, run_id=None):
    if run_id is None:
        run_id = f"{MODEL_VERSION}_{start_date}_{end_date}"

    print(f"=== バックテスト開始 ===")
    print(f"期間: {start_date} -> {end_date}")
    print(f"run_id: {run_id}")

    all_results = []

    for race_date in _daterange(start_date, end_date):
        races = _fetch_race_ids_for_date(race_date)
        if not races:
            continue

        print(f"\n{race_date}: {len(races)}レース")

        for r in races:
            venue_id = str(r.get("venue_id", "")).zfill(2)
            if venue_id not in TARGET_VENUES:
                continue
            race_no = r.get("race_no")

            result = _backtest_one_race(race_date, venue_id, race_no, run_id)
            if result:
                all_results.append(result)
                status = "HIT" if result["hit"] else ("採用" if result["adopted"] else "見送")
                print(f"  {result['race_id']} {status} profit={result['profit_yen']:+d}円")

    if not all_results:
        print("結果なし")
        return None

    return _summarize(all_results, run_id, start_date, end_date)


if __name__ == "__main__":
    run_backtest(
        start_date="2025-04-01",
        end_date="2025-06-30",
    )