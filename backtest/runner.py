# -*- coding: utf-8 -*-
"""
バックテストランナー

2モード対応:
- stable: 安定モード
- ana:    馬王モード・穴狙い

今回の修正版:
- models/bet_selector_ev.py の EVセレクターを使用
- mode / model_version / bets_json を保存
- on_conflict は race_id,run_id,mode
- トリガミ判定を「払戻 < 投資額」に修正
- stable / ana は個別実行のまま維持
"""

import json
import urllib.parse
import requests as http_requests
from datetime import datetime, timedelta

from data_pipeline.load_race import load_race_context
from models.predictor_v2 import predict_race
from models.bet_selector_ev import select_bets_ev_mode
from backtest.scenario import detect_scenario_type
from db.client import upsert
from config.settings import SUPABASE_URL, SUPABASE_KEY, MODEL_VERSION


HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

TARGET_VENUES = ["01", "06", "12", "18", "24"]
UNIT_YEN = 100


# ============================================================
# モード別パラメータ
# ============================================================

MODE_PARAMS = {
    "stable": {
        "mode": "stable",

        # シナリオ別の採用条件
        "scenario_thresholds": {
            "attack":  {"race_score_min": 0.14, "exacta_top1_min": 0.050},
            "mixed":   {"race_score_min": 0.22, "exacta_top1_min": 0.065},
            "escape":  {"race_score_min": 0.16, "exacta_top1_min": 0.055},
            "hole":    {"race_score_min": 0.20, "exacta_top1_min": 0.060},
            "unknown": {"race_score_min": 0.99, "exacta_top1_min": 0.99},
        },

        # stable 単体検証時の上限
        "max_bets_per_race": 2,
        "max_points_per_day": 7,

        # 直前EV条件
        "ev_rule": {
            "min_ev": 1.10,
            "min_odds": 3.5,
            "max_odds": 25.0,
            "min_prob": 0.015,
            "max_bets": 2,
            "same_first_only": True,
        },

        "description": "安定モード",
    },

    "ana": {
        "mode": "ana",

        "scenario_thresholds": {
            "attack":  {"race_score_min": 0.10, "exacta_top1_min": 0.035},
            "mixed":   {"race_score_min": 0.15, "exacta_top1_min": 0.045},
            "escape":  {"race_score_min": 0.12, "exacta_top1_min": 0.040},
            "hole":    {"race_score_min": 0.10, "exacta_top1_min": 0.035},
            "unknown": {"race_score_min": 0.99, "exacta_top1_min": 0.99},
        },

        # ana 単体検証時の上限
        "max_bets_per_race": 1,
        "max_points_per_day": 5,

        # 馬王モードは高EV・中穴以上だけ
        "ev_rule": {
            "min_ev": 1.35,
            "min_odds": 12.0,
            "max_odds": 80.0,
            "min_prob": 0.008,
            "max_bets": 1,
            "same_first_only": False,
        },

        "description": "馬王モード・穴狙い",
    },
}


# ============================================================
# utility
# ============================================================

def _safe_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _safe_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _race_id(race_date, venue_id, race_no):
    return f"{race_date.replace('-', '')}_{str(venue_id).zfill(2)}_{int(race_no):02d}"


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
        res = http_requests.get(url, headers=HEADERS, timeout=20)
        if not res.ok:
            print(f"race list fetch error: {race_date} {res.status_code} {res.text[:200]}")
            return []
        return res.json()
    except Exception as e:
        print(f"race list fetch exception: {race_date} {e}")
        return []


def _fetch_result(race_id):
    url = (
        f"{SUPABASE_URL}/rest/v1/v2_results"
        f"?select=trifecta_ticket,trifecta_payout_yen,result_status"
        f"&race_id=eq.{urllib.parse.quote(race_id)}"
        f"&limit=1"
    )

    try:
        res = http_requests.get(url, headers=HEADERS, timeout=20)
        if not res.ok:
            print(f"result fetch error: {race_id} {res.status_code} {res.text[:200]}")
            return None

        rows = res.json()
        return rows[0] if rows else None

    except Exception as e:
        print(f"result fetch exception: {race_id} {e}")
        return None


def _daterange(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")

    cur = start
    while cur <= end:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)


# ============================================================
# シナリオ別 + EV 買い目選択
# ============================================================

def _select_bets(prediction_result, scenario, params):
    """
    バックテスト用の買い目選択。

    注意:
    最終的な買い目選択は models/bet_selector_ev.py に統一する。
    ここではシナリオ別の最低条件だけ確認する。
    """
    candidates = prediction_result.get("candidates", [])
    exacta_candidates = prediction_result.get("exacta_candidates", [])
    race_score = _safe_float(prediction_result.get("race_score"), 0.0)

    if not candidates:
        return []

    if not exacta_candidates:
        return []

    sc_params = params["scenario_thresholds"].get(
        scenario,
        params["scenario_thresholds"]["unknown"]
    )

    exacta_top1 = _safe_float(exacta_candidates[0].get("probability"), 0.0)

    if race_score < sc_params["race_score_min"]:
        return []

    if exacta_top1 < sc_params["exacta_top1_min"]:
        return []

    mode = params.get("mode", "stable")
    ev_rule = params.get("ev_rule")

    bets, reason = select_bets_ev_mode(
        prediction_result,
        mode=mode,
        override_rule=ev_rule,
    )

    if not bets:
        return []

    return bets[:params["max_bets_per_race"]]


# ============================================================
# 1レースのバックテスト
# ============================================================

def _backtest_one_race(race_date, venue_id, race_no, session_type, run_id, params):
    race_id = _race_id(race_date, venue_id, race_no)

    context = load_race_context(venue_id, race_no, race_date)
    if not context:
        return None

    entries = context.get("entries", [])
    odds = context.get("odds", {}) or context.get("odds_trifecta", {})

    if len(entries) < 6:
        return None

    # 現在のrunnerは「直前オッズあり」のバックテスト用。
    # 朝候補/直前精査の完全分離は portfolio_runner 追加後に別STEPで対応。
    if not odds:
        return None

    try:
        prediction_result = predict_race(context)
    except Exception as e:
        print(f"  predict error: {race_id} {e}")
        return None

    scenario = detect_scenario_type(context, prediction_result)

    bets = _select_bets(prediction_result, scenario, params)
    adopt = len(bets) > 0
    reason = None if adopt else f"閾値/EV条件未達({scenario})"

    actual = _fetch_result(race_id)
    if not actual:
        return None

    actual_ticket = actual.get("trifecta_ticket")
    actual_payout = _safe_int(actual.get("trifecta_payout_yen"), 0)
    result_status = actual.get("result_status", "")

    if result_status != "official":
        return None

    stake_yen = len(bets) * UNIT_YEN if adopt else 0
    payout_yen = 0
    hit = False
    trigami = False

    if adopt and bets:
        for bet in bets:
            if bet.get("ticket") == actual_ticket:
                payout_yen = actual_payout
                hit = True

                # 投資額より払戻が少なければトリガミ
                if actual_payout < stake_yen:
                    trigami = True

                break

    profit = payout_yen - stake_yen

    candidates = prediction_result.get("candidates", [])
    top1_prob = _safe_float(candidates[0].get("probability"), 0.0) if candidates else 0.0
    top2_prob = _safe_float(candidates[1].get("probability"), 0.0) if len(candidates) >= 2 else 0.0

    return {
        "run_id": run_id,
        "model_version": MODEL_VERSION,
        "mode": params.get("mode"),

        "race_id": race_id,
        "race_date": race_date,
        "race_no": int(race_no),
        "venue_id": str(venue_id).zfill(2),
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

        "race_score": _safe_float(prediction_result.get("race_score"), 0.0),
        "top1_ticket": bets[0]["ticket"] if bets else None,
        "top1_prob": top1_prob,
        "top2_prob": top2_prob,
        "prob_gap": round(top1_prob - top2_prob, 6),
        "max_ev": bets[0].get("ev") if bets else None,
        "top1_odds": bets[0].get("odds") if bets else None,

        "bets_json": json.dumps(bets, ensure_ascii=False) if bets else None,
    }


# ============================================================
# サマリー集計
# ============================================================

def _calc_max_losing_streak(adopted):
    max_streak = 0
    cur = 0

    for r in adopted:
        if r.get("hit_flag"):
            cur = 0
        else:
            cur += 1
            max_streak = max(max_streak, cur)

    return max_streak


def _calc_max_drawdown(adopted):
    equity = 0
    peak = 0
    max_dd = 0

    for r in adopted:
        equity += _safe_int(r.get("profit_yen"), 0)
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)

    return max_dd


def _summarize(results, run_id, start_date, end_date, mode):
    adopted = [r for r in results if r["buy_flag"]]
    hits = [r for r in adopted if r["hit_flag"]]
    trigamis = [r for r in hits if r["trigami"]]

    total_races = len(results)
    adopted_races = len(adopted)
    total_points = sum(_safe_int(r.get("predicted_ticket_count"), 0) for r in adopted)
    total_stake = sum(_safe_int(r["stake_yen"], 0) for r in adopted)
    total_payout = sum(_safe_int(r["payout_yen"], 0) for r in adopted)
    profit = total_payout - total_stake

    roi = (total_payout / total_stake * 100) if total_stake > 0 else 0.0
    hit_rate = (len(hits) / adopted_races * 100) if adopted_races > 0 else 0.0
    trigami_rate = (len(trigamis) / len(hits) * 100) if hits else 0.0

    days = len(set(r["race_date"] for r in adopted)) if adopted else 1
    avg_points_per_day = total_points / days if days > 0 else 0.0
    avg_stake_per_day = total_stake / days if days > 0 else 0.0
    avg_profit_per_day = profit / days if days > 0 else 0.0

    max_losing_streak = _calc_max_losing_streak(adopted)
    max_drawdown = _calc_max_drawdown(adopted)

    scenario_stats = {}
    for r in adopted:
        sc = r["scenario_type"]
        if sc not in scenario_stats:
            scenario_stats[sc] = {"count": 0, "hit": 0, "stake": 0, "payout": 0, "points": 0}

        scenario_stats[sc]["count"] += 1
        scenario_stats[sc]["points"] += _safe_int(r.get("predicted_ticket_count"), 0)
        scenario_stats[sc]["stake"] += _safe_int(r["stake_yen"], 0)
        scenario_stats[sc]["payout"] += _safe_int(r["payout_yen"], 0)

        if r["hit_flag"]:
            scenario_stats[sc]["hit"] += 1

    print("\n" + "=" * 60)
    print(f"バックテスト結果: {start_date} -> {end_date} [{mode}]")
    print("=" * 60)
    print(f"対象レース数:       {total_races}")
    print(f"採用レース数:       {adopted_races}")
    print(f"採用点数:           {total_points}点")
    print(f"的中レース数:       {len(hits)}")
    print(f"的中率:             {hit_rate:.1f}%")
    print(f"投資額:             {total_stake:,}円")
    print(f"回収額:             {total_payout:,}円")
    print(f"損益:               {profit:+,}円")
    print(f"回収率:             {roi:.1f}%")
    print(f"トリガミ率:         {trigami_rate:.1f}%")
    print(f"最大連敗:           {max_losing_streak}")
    print(f"最大DD:             {max_drawdown:,}円")
    print(f"1日平均点数:        {avg_points_per_day:.1f}点")
    print(f"1日平均投資:        {avg_stake_per_day:.0f}円")
    print(f"1日平均損益:        {avg_profit_per_day:+.0f}円")

    print("\n--- シナリオ別 ---")
    for sc, s in sorted(scenario_stats.items()):
        sc_roi = (s["payout"] / s["stake"] * 100) if s["stake"] > 0 else 0.0
        sc_hit = (s["hit"] / s["count"] * 100) if s["count"] > 0 else 0.0
        sc_profit = s["payout"] - s["stake"]

        print(
            f"  {sc}: {s['count']}レース/{s['points']}点 "
            f"的中{sc_hit:.1f}% ROI{sc_roi:.1f}% "
            f"損益{sc_profit:+,}円"
        )

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

        "scenario_stats": json.dumps(scenario_stats, ensure_ascii=False),
        "note": (
            f"mode={mode} "
            f"points={total_points} "
            f"avg_points={avg_points_per_day:.1f}/day "
            f"max_losing_streak={max_losing_streak} "
            f"max_drawdown={max_drawdown}"
        ),
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

    print("=== バックテスト開始 ===")
    print(f"モード: {params['description']}")
    print(f"期間: {start_date} -> {end_date}")
    print(f"run_id: {run_id}")
    print(f"保存キー: race_id, run_id, mode")
    print(f"1点単価: {UNIT_YEN}円")

    all_results = []

    for race_date in _daterange(start_date, end_date):
        races = _fetch_race_list_for_date(race_date)
        if not races:
            continue

        day_points = 0
        day_candidates = []

        for r in races:
            venue_id = str(r.get("venue_id", "")).zfill(2)
            if venue_id not in TARGET_VENUES:
                continue

            race_no = r.get("race_no")
            session_type = r.get("session_type", "")

            result = _backtest_one_race(
                race_date=race_date,
                venue_id=venue_id,
                race_no=race_no,
                session_type=session_type,
                run_id=run_id,
                params=params,
            )

            if result:
                day_candidates.append(result)

        # そのモード単体での日次上限。
        # stable/ana 合算の1,000円制限は portfolio_runner.py 側で行う。
        scenario_priority = {
            "attack": 0,
            "escape": 1,
            "hole": 2,
            "mixed": 3,
            "unknown": 4,
        }

        day_candidates.sort(
            key=lambda x: (
                scenario_priority.get(x["scenario_type"], 5),
                -_safe_float(x.get("race_score"), 0.0),
                -_safe_float(x.get("max_ev"), 0.0),
            )
        )

        for result in day_candidates:
            if result["buy_flag"]:
                points = _safe_int(result.get("predicted_ticket_count"), 0)

                if day_points + points > params["max_points_per_day"]:
                    result["buy_flag"] = False
                    result["skip_reason"] = "1日点数上限"
                    result["stake_yen"] = 0
                    result["payout_yen"] = 0
                    result["profit_yen"] = 0
                    result["hit_flag"] = False
                    result["trigami"] = False
                else:
                    day_points += points

            upsert(
                "v2_backtest_races",
                result,
                on_conflict="race_id,run_id,mode",
            )

            all_results.append(result)

            if result["buy_flag"]:
                status = "HIT" if result["hit_flag"] else "採用"
                print(
                    f"  {result['race_id']} "
                    f"[{result['mode']}:{result['scenario_type']}] "
                    f"{status} "
                    f"{result.get('top1_ticket')} "
                    f"odds={result.get('top1_odds')} "
                    f"ev={result.get('max_ev')} "
                    f"profit={_safe_int(result.get('profit_yen'), 0):+d}円"
                )

        if day_points > 0:
            print(f"{race_date}: {day_points}点 / {day_points * UNIT_YEN}円 採用")

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