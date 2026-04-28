# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import urllib.parse
import requests as http_requests

from data_pipeline.load_race import load_race_context
from data_pipeline.fetch_odds import fetch_odds_trifecta
from models.predictor_v2 import predict_race
from betting.bet_selector_v2 import select_bets
from models.risk_manager import judge_race_adoption
from notifications.formatter_v2 import format_prediction_message
from notifications.notifier import send_line_message
from db.client import upsert
from config.settings import SUPABASE_URL, SUPABASE_KEY, MODEL_VERSION

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# レース締切の何分前に配信するか
MINUTES_BEFORE_RACE = 30


def _get_upcoming_races(race_date):
    """
    締切時刻がNow+5分〜Now+MINUTES_BEFORE_RACE分以内のレースを取得
    """
    now_jst = datetime.utcnow() + timedelta(hours=9)
    window_start = now_jst + timedelta(minutes=5)
    window_end = now_jst + timedelta(minutes=MINUTES_BEFORE_RACE)

    url = (
        f"{SUPABASE_URL}/rest/v1/v2_races"
        f"?select=race_id,venue_id,race_no,race_date,race_closed_at,session_type"
        f"&race_date=eq.{race_date}"
        f"&race_closed_at=gte.{window_start.strftime('%Y-%m-%dT%H:%M:%S+09:00')}"
        f"&race_closed_at=lte.{window_end.strftime('%Y-%m-%dT%H:%M:%S+09:00')}"
        f"&status=eq.scheduled"
    )
    try:
        res = http_requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            print(f"❌ upcoming races取得失敗: {res.status_code}")
            return []
        return res.json()
    except Exception as e:
        print(f"❌ upcoming races例外: {e}")
        return []


def _already_notified(race_id):
    """直前通知済みかチェック"""
    url = (
        f"{SUPABASE_URL}/rest/v1/v2_notifications"
        f"?race_id=eq.{urllib.parse.quote(race_id)}"
        f"&notification_type=eq.pre_race"
        f"&limit=1"
    )
    try:
        res = http_requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            return False
        return len(res.json()) > 0
    except Exception:
        return False


def run_pre_race_job(race_date):
    print("=== 直前予想ジョブ開始 ===")
    print("対象日:", race_date)

    upcoming = _get_upcoming_races(race_date)
    print(f"直前レース数: {len(upcoming)}")

    for r in upcoming:
        race_id = r.get("race_id")
        venue_id = r.get("venue_id")
        race_no = r.get("race_no")

        # 通知済みならスキップ
        if _already_notified(race_id):
            print(f"  skip(通知済み): {race_id}")
            continue

        # 最新オッズを取得してコンテキスト構築
        context = load_race_context(venue_id, race_no, race_date)
        if not context:
            print(f"  contextなし: {race_id}")
            continue

        # オッズが入っていない場合はスキップ
        if not context.get("odds"):
            print(f"  オッズなし: {race_id}")
            continue

        try:
            prediction_result = predict_race(context)
        except Exception as e:
            print(f"  predict error: {race_id} {e}")
            continue

        bets = select_bets(prediction_result)
        adopt, reason = judge_race_adoption(context, prediction_result, bets)

        if not adopt:
            print(f"  見送り: {race_id} {reason}")
            upsert("v2_notifications", {
                "notification_type": "pre_race",
                "target_date": race_date,
                "race_id": race_id,
                "venue_id": venue_id,
                "message_body": f"見送り: {reason}",
                "delivery_status": "skipped",
            }, on_conflict=["id"])
            continue

        # 買い目メッセージ送信
        msg = format_prediction_message(
            context,
            bets,
            model_version=MODEL_VERSION
        )
        print(msg)
        res = send_line_message(msg)
        print(f"  LINE送信: {race_id} {res}")

        # 通知ログ保存
        upsert("v2_notifications", {
            "notification_type": "pre_race",
            "target_date": race_date,
            "race_id": race_id,
            "venue_id": venue_id,
            "message_body": msg,
            "delivery_status": "sent" if res.get("ok") else "failed",
            "line_response": res.get("text"),
        }, on_conflict=["id"])

        # 予想保存
        for rank, bet in enumerate(bets, 1):
            upsert("v2_predictions", {
                "race_id": race_id,
                "model_version": MODEL_VERSION,
                "buy_flag": True,
                "race_score": prediction_result.get("race_score", 0.0),
                "ticket": bet["ticket"],
                "ticket_rank": rank,
                "probability": bet["prob"],
                "odds": bet.get("odds"),
                "expected_value": bet.get("ev"),
                "recommended_bet_yen": 100,
                "notification_type": "pre_race",
            }, on_conflict=["race_id", "model_version"])