# -*- coding: utf-8 -*-
from db.client import select, upsert
from notifications.formatter_v2 import format_daily_report_message
from notifications.notifier import send_line_message
from config.settings import MODEL_VERSION


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


def build_daily_report(target_date):
    race_date_compact = target_date.replace("-", "")

    all_predictions = select("v2_predictions")
    all_tickets = select("v2_prediction_tickets")
    all_results = select("v2_results")

    # 対象日だけ拾う
    predictions = []
    for p in all_predictions:
        race_id = str(p.get("race_id", ""))
        if not race_id.startswith(race_date_compact + "_"):
            continue
        predictions.append(p)

    # 同一 race_id が複数ある場合、buy_flag=True 優先、次に id 最大
    by_race = {}
    for p in predictions:
        race_id = str(p.get("race_id", ""))
        current = by_race.get(race_id)

        if current is None:
            by_race[race_id] = p
            continue

        current_buy = _safe_bool(current.get("buy_flag"))
        new_buy = _safe_bool(p.get("buy_flag"))

        if new_buy and not current_buy:
            by_race[race_id] = p
            continue

        if new_buy == current_buy:
            if _safe_int(p.get("id"), 0) > _safe_int(current.get("id"), 0):
                by_race[race_id] = p

    predictions = list(by_race.values())

    # buy_flag=True のものを「予想レース」とみなす
    adopted_predictions = [p for p in predictions if _safe_bool(p.get("buy_flag"))]
    adopted_prediction_ids = set(p.get("id") for p in adopted_predictions)

    tickets = [
        t for t in all_tickets
        if t.get("prediction_id") in adopted_prediction_ids
    ]

    results_map = {}
    for r in all_results:
        race_id = str(r.get("race_id", ""))
        if race_id.startswith(race_date_compact + "_"):
            results_map[race_id] = r

    predicted_races = len(adopted_predictions)
    total_points = len(tickets)
    total_stake_yen = 0
    total_payout_yen = 0
    hit_races_set = set()
    trigami_count = 0
    hit_details = []

    for t in tickets:
        stake_yen = _safe_int(t.get("recommended_bet_yen"), 100)
        total_stake_yen += stake_yen

        race_id = t.get("race_id")
        actual = results_map.get(race_id)
        if not actual:
            continue

        actual_ticket = actual.get("trifecta_ticket")
        payout_yen = _safe_int(actual.get("trifecta_payout_yen"), 0)

        if t.get("ticket") == actual_ticket:
            total_payout_yen += payout_yen
            hit_races_set.add(race_id)

            if payout_yen < stake_yen:
                trigami_count += 1

            hit_details.append({
                "race_id": race_id,
                "ticket": t.get("ticket"),
                "payout_yen": payout_yen
            })

    hit_races = len(hit_races_set)
    hit_rate = (hit_races / predicted_races) if predicted_races > 0 else 0
    roi = (total_payout_yen / total_stake_yen) if total_stake_yen > 0 else 0
    trigami_rate = (trigami_count / len(hit_details)) if hit_details else 0

    report = {
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
        "prediction_count_all": len(predictions),
        "prediction_count_buy": len(adopted_predictions),
    }

    return report


def save_daily_stats(report):
    hit_count = len(report["hit_details"])
    trigami_bets = 0
    if hit_count > 0:
        trigami_bets = int(round(report["trigami_rate_pct"] * hit_count / 100.0))

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
        "note": f"daily report generated / all={report['prediction_count_all']} buy={report['prediction_count_buy']}"
    }, on_conflict=["stat_date"])


def run_daily_report_job(target_date):
    print("=== 前日レポートジョブ開始 ===")

    report = build_daily_report(target_date)
    print("集計確認:", report)

    msg = format_daily_report_message(report, model_version=MODEL_VERSION)
    print(msg)

    save_daily_stats(report)

    try:
        line_res = send_line_message(msg)
        print(line_res)
    except Exception as e:
        print("LINE送信エラー:", repr(e))

    return report
