# -*- coding: utf-8 -*-

def format_prediction_message(context, bets, model_version="v2.0.0"):
    race = context.get("race") or {}
    weather = context.get("weather") or {}

    venue_id = race.get("venue_id", "")
    race_no = race.get("race_no", "")
    race_id = context.get("race_id", "")

    wind = weather.get("wind_speed")
    wave = weather.get("wave_height")
    weather_name = weather.get("weather_name")

    lines = []
    lines.append("【3連単AI v2】")
    lines.append(f"Race: {race_id}")
    lines.append(f"場: {venue_id}  {race_no}R")

    if weather_name or wind is not None or wave is not None:
        weather_text = []
        if weather_name:
            weather_text.append(str(weather_name))
        if wind is not None:
            weather_text.append(f"風{wind}")
        if wave is not None:
            weather_text.append(f"波{wave}")
        lines.append(" / ".join(weather_text))

    lines.append("買い目:")
    for i, bet in enumerate(bets, 1):
        lines.append(f"{i}. {bet['ticket']}  {bet['odds']}倍  EV {bet['ev']}")

    total_points = len(bets)
    total_cost = total_points * 100
    lines.append(f"点数: {total_points}点 / {total_cost}円")
    lines.append(f"Model: {model_version}")

    return "\n".join(lines)


def format_skip_message(context, reason="見送り", model_version="v2.0.0"):
    race = context.get("race") or {}
    race_id = context.get("race_id", "")
    venue_id = race.get("venue_id", "")
    race_no = race.get("race_no", "")

    lines = []
    lines.append("【3連単AI v2】")
    lines.append(f"Race: {race_id}")
    lines.append(f"場: {venue_id}  {race_no}R")
    lines.append("判定: 見送り")
    lines.append(f"理由: {reason}")
    lines.append(f"Model: {model_version}")
    return "\n".join(lines)


def format_batch_prediction_message(results, title, model_version="v2.0.0"):
    lines = []
    lines.append(f"【{title}】")
    lines.append(f"Model: {model_version}")
    lines.append("")

    total_points = 0

    for item in results:
        venue_id = item.get("venue_id", "")
        race_no = item.get("race_no", "")
        race_id = item.get("race_id", "")
        bets = item.get("bets", [])

        lines.append(f"{venue_id} {race_no}R")
        lines.append(f"Race: {race_id}")

        for i, bet in enumerate(bets, 1):
            lines.append(f"{i}. {bet['ticket']} {bet['odds']}倍 EV{bet['ev']}")
            total_points += 1

        lines.append("")

    lines.append(f"合計点数: {total_points}点")
    return "\n".join(lines)


def format_daily_report_message(report, model_version="v2.0.0"):
    lines = []
    lines.append("【前日レポート】")
    lines.append(f"日付: {report.get('date')}")
    lines.append(f"Model: {model_version}")
    lines.append("")

    lines.append(f"予想レース数: {report.get('predicted_races', 0)}")
    lines.append(f"的中レース数: {report.get('hit_races', 0)}")
    lines.append(f"的中率: {report.get('hit_rate_pct', 0)}%")
    lines.append(f"投資: {report.get('total_stake_yen', 0)}円")
    lines.append(f"回収: {report.get('total_payout_yen', 0)}円")
    lines.append(f"回収率: {report.get('roi_pct', 0)}%")
    lines.append(f"トリガミ率: {report.get('trigami_rate_pct', 0)}%")
    lines.append(f"買い目点数: {report.get('total_points', 0)}点")

    hit_details = report.get("hit_details", [])
    if hit_details:
        lines.append("")
        lines.append("的中:")
        for row in hit_details[:5]:
            lines.append(
                f"{row['race_id']}  {row['ticket']}  {row['payout_yen']}円"
            )

    return "\n".join(lines)
