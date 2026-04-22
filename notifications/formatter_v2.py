# -*- coding: utf-8 -*-

def _format_weather_text(weather):
    if not weather:
        return None

    weather_name = weather.get("weather_name") or weather.get("weather") or ""
    wind = weather.get("wind_speed") or weather.get("wind") or ""
    wave = weather.get("wave_height") or weather.get("wave") or ""

    parts = []

    if weather_name:
        parts.append(str(weather_name))

    if wind != "":
        parts.append(f"風{wind}")

    if wave != "":
        parts.append(f"波{wave}")

    if not parts:
        return None

    return " / ".join(parts)


def format_prediction_message(context, bets, model_version="v2.0.0"):
    lines = []
    lines.append("【3連単AI v2】")
    lines.append(f"Race: {context.get('race_id', '')}")

    race = context.get("race", {})
    venue_id = race.get("venue_id") or context.get("venue_id", "")
    race_no = race.get("race_no") or context.get("race_no", "")
    if venue_id or race_no:
        lines.append(f"場: {venue_id}  {race_no}R")

    weather_text = _format_weather_text(context.get("weather", {}))
    if weather_text:
        lines.append(weather_text)

    lines.append("買い目:")
    for i, bet in enumerate(bets, 1):
        ticket = bet.get("ticket", "")
        prob = bet.get("prob", 0)

        odds = bet.get("odds")
        ev = bet.get("ev")

        if odds is not None and ev is not None:
            lines.append(f"{i}. {ticket}  {odds}倍  EV {ev}")
        else:
            lines.append(f"{i}. {ticket}  確率 {round(prob * 100, 1)}%")

    lines.append(f"点数: {len(bets)}点 / {len(bets) * 100}円")
    lines.append(f"Model: {model_version}")

    return "\n".join(lines)


def format_skip_message(context, reason="見送り", model_version="v2.0.0"):
    lines = []
    lines.append("【3連単AI v2】")
    lines.append(f"Race: {context.get('race_id', '')}")

    race = context.get("race", {})
    venue_id = race.get("venue_id") or context.get("venue_id", "")
    race_no = race.get("race_no") or context.get("race_no", "")
    if venue_id or race_no:
        lines.append(f"場: {venue_id}  {race_no}R")

    weather_text = _format_weather_text(context.get("weather", {}))
    if weather_text:
        lines.append(weather_text)

    lines.append(f"判定: {reason}")
    lines.append(f"Model: {model_version}")

    return "\n".join(lines)


def format_batch_prediction_message(all_results, title="推奨レース", model_version="v2.0.0"):
    lines = []
    lines.append(f"【{title}】")
    lines.append(f"Model: {model_version}")
    lines.append("")

    total_points = 0

    for result in all_results:
        venue_id = result.get("venue_id", "")
        race_no = result.get("race_no", "")
        race_id = result.get("race_id", "")
        weather = result.get("weather", {})
        bets = result.get("bets", [])

        lines.append(f"{venue_id} {race_no}R")
        lines.append(f"Race: {race_id}")

        weather_text = _format_weather_text(weather)
        if weather_text:
            lines.append(weather_text)

        for i, bet in enumerate(bets, 1):
            ticket = bet.get("ticket", "")
            prob = bet.get("prob", 0)

            odds = bet.get("odds")
            ev = bet.get("ev")

            if odds is not None and ev is not None:
                lines.append(f"{i}. {ticket} {odds}倍 EV{ev}")
            else:
                lines.append(f"{i}. {ticket} 確率{round(prob * 100, 1)}%")

        lines.append("")
        total_points += len(bets)

    lines.append(f"合計点数: {total_points}点")

    return "\n".join(lines)


def format_daily_report_message(summary, model_version="v2.0.0"):
    lines = []
    lines.append("【前日レポート】")
    lines.append(f"日付: {summary.get('date', '')}")
    lines.append(f"Model: {model_version}")
    lines.append("")
    lines.append(f"予想レース数: {summary.get('predicted_races', 0)}")
    lines.append(f"的中レース数: {summary.get('hit_races', 0)}")
    lines.append(f"的中率: {summary.get('hit_rate_pct', 0)}%")
    lines.append(f"投資: {summary.get('total_stake_yen', 0)}円")
    lines.append(f"回収: {summary.get('total_payout_yen', 0)}円")
    lines.append(f"回収率: {summary.get('roi_pct', 0)}%")
    lines.append(f"トリガミ率: {summary.get('trigami_rate_pct', 0)}%")
    lines.append(f"買い目点数: {summary.get('total_points', 0)}点")

    hit_details = summary.get("hit_details", [])
    if hit_details:
        lines.append("")
        lines.append("的中:")
        for item in hit_details[:5]:
            race_id = item.get("race_id", "")
            ticket = item.get("ticket", "")
            payout = item.get("payout_yen", 0)
            lines.append(f"- {race_id} {ticket} {payout}円")

    return "\n".join(lines)
