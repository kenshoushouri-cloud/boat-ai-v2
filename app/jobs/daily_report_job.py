# -*- coding: utf-8 -*-
import urllib.parse
import requests as http_requests
from db.client import upsert
from notifications.formatter_v2 import format_daily_report_message
from notifications.notifier import send_line_message
from config.settings import MODEL_VERSION, SUPABASE_URL, SUPABASE_KEY

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def _safe_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _safe_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "t", "yes")
    if isinstance(v, int):
        return v != 0
    return False


def _fetch_predictions_for_date(race_date_compact):
    """対象日のv2_predictionsをrace_idプレフィックスで取得"""
    prefix_start = f"{race_date_compact}_"
    prefix_end = f"{race_date_compact}`"
    url = (
        f"{SUPABASE_URL}/rest/v1/v2_predictions"
        f"?select=*"
        f"&race_id=gte.{urllib.parse.quote(prefix_start)}"
        f"&race_id=lt.{urllib.parse.quote(prefix_end)}"
        f"&limit=10000"
    )
    try:
        res = http_requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            print(f"❌ predictions取得失敗: {res.status_code}")
            return []
        return res.json()
    except Exception as e:
        print(f"❌ predictions例外: {e}")
        return []


def _fetch_results_for_date(race_date_compact):
    """対象日のv2_resultsをrace_idプレフィックスで取得"""
    prefix_start = f"{race_date_compact}_"
    prefix_end = f"{race_date_compact}`"
    url = (
        f"{SUPABASE_URL}/rest/v1/v2_results"
        f"?select=race_id,trifecta_ticket,trifecta_payout_yen"
        f"&race_id=gte.{urllib.parse.quote(prefix_start)}"
        f"&race_id=lt.{urllib.parse.quote(prefix_end)}"
        f"&limit=10000"
    )
    try:
        res = http_requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            print(f"❌ results取得失敗: {res.status_code}")
            return []
        return res.json()
    except Exception as e:
        print(f"❌ results例外: {e}")
        return []


def build_daily_report(target_date):
    race_date_compact = target_date.replace("-", "")

    all_predictions = _fetch_predictions_for_date(race_date_compact)
    all_results = _fetch_results_for_date(race_date_compact)

    # 結果をrace_idでマップ化
    results_map = {r["race_id"]: r for r in all_results}

    # buy_flag=True の買い目のみ対象
    bought = [p for p in all_predictions if _safe_bool(p.get("buy_flag")) and p.get("ticket")]

    predicted_race_ids = set(p["race_id"] for p in bought)
    predicted_races = len(predicted_race_ids)
    total_points = len(bought)
    total_stake_yen = total_points * 100

    total_payout_yen = 0
    hit_races_set = set()
    trigami_count = 0
    hit_details = []

    for p in bought:
        race_id = p.get("race_id")
        ticket = p.get("ticket")
        actual = results_map.get(race_id)
        if not actual:
            continue

        actual_ticket = actual.get("trifecta_ticket")
        payout_yen = _safe_int(actual.get("trifecta_payout_yen"), 0)

        if ticket == actual_ticket:
            total_payout_yen += payout_yen
            hit_races_set.add(race_id)

            if payout_yen < 100:
                trigami_count += 1

            hit_details.append({
                "race_id": race_id,
                "ticket": ticket,
                "payout_yen": payout_yen,
            })

    hit_races = len(hit_races_set)
    hit_rate = (hit_races / predicted_races) if predicted_races > 0 else 0
    roi = (total_payout_yen / total_stake_yen) if total_stake_yen > 0 else 0
    trigami_rate = (trigami_count / len(hit_details)) if hit_details else 0

    return {
        "date": target_date,
        "predicted_races": predicted_races,
        "hit_races": hit_races,
        "hit_rate_pct": round(hit_rate * 100, 1),
        "total_points": total_points,
        "total_stake_yen": total_stake_yen,
        "total_payout_yen": total_payout_yen,
        "roi_pct": round(roi * 100, 1),
        "trigami_rate_pct": round(trigami_rate * 100, 1),
        "hit_details": hit_details,
    }


def save_daily_stats(report):
    hit_count = len(report["hit_details"])
    trigami_bets = int(round(report["trigami_rate_pct"] * hit_count / 100.0)) if hit_count else 0

    upsert("v2_daily_stats", {
        "stat_date": report["date"],
        "model_version": MODEL_VERSION,
        "predicted_races": report["predicted_races"],
        "hit_races": report["hit_races"],
        "total_points": report["total_points"],
        "total_bets": report["total_points"],
        "hit_bets": hit_count,
        "trigami_bets": trigami_bets,
        "total_stake_yen": report["total_stake_yen"],
        "total_payout_yen": report["total_payout_yen"],
        "roi": report["roi_pct"] / 100.0,
        "hit_rate": report["hit_rate_pct"] / 100.0,
        "trigami_rate": report["trigami_rate_pct"] / 100.0,
        "avg_payout_yen": (report["total_payout_yen"] / hit_count) if hit_count else 0,
    }, on_conflict="stat_date")


def run_daily_report_job(target_date):
    print("=== 前日レポートジョブ開始 ===")

    report = build_daily_report(target_date)
    print("集計:", report)

    save_daily_stats(report)

    msg = format_daily_report_message(report, model_version=MODEL_VERSION)
    print(msg)

    try:
        line_res = send_line_message(msg)
        print(line_res)
    except Exception as e:
        print("LINE送信エラー:", repr(e))

    return report