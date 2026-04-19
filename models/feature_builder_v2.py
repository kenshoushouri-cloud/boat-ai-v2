# -*- coding: utf-8 -*-

LANE_BASE = {
    1: 1.00,
    2: 0.82,
    3: 0.76,
    4: 0.70,
    5: 0.56,
    6: 0.48,
}

CLASS_SCORE = {
    1: 1.00,  # A1
    2: 0.90,  # A2
    3: 0.78,  # B1
    4: 0.65,  # B2
}

def nz(value, default=0.0):
    return float(value) if value is not None else float(default)

def build_entry_features(entry, weather):
    lane = int(entry.get("lane", 6))
    racer_class = int(entry.get("racer_class") or 4)

    national_win = nz(entry.get("national_win_rate"), 5.0)
    local_win = nz(entry.get("local_win_rate"), 5.0)
    motor_rate = nz(entry.get("motor_place2_rate"), 30.0)
    boat_rate = nz(entry.get("boat_place2_rate"), 30.0)

    exhibition_time = entry.get("exhibition_time")
    start_timing = entry.get("start_timing")

    ex_score = 0.55
    if exhibition_time is not None:
        ex_score = max(0.0, min(1.0, (7.2 - float(exhibition_time)) / 0.7))

    st_score = 0.55
    if start_timing is not None:
        st_score = max(0.0, min(1.0, (0.30 - float(start_timing)) / 0.20))

    wind_speed = nz(weather.get("wind_speed"), 0.0)
    wave_height = nz(weather.get("wave_height"), 0.0)

    weather_risk = min(1.0, (wind_speed / 10.0) * 0.6 + (wave_height / 10.0) * 0.4)

    strength = (
        LANE_BASE.get(lane, 0.45) * 0.30 +
        CLASS_SCORE.get(racer_class, 0.60) * 0.15 +
        min(1.0, national_win / 8.0) * 0.15 +
        min(1.0, local_win / 8.0) * 0.10 +
        min(1.0, motor_rate / 60.0) * 0.12 +
        min(1.0, boat_rate / 60.0) * 0.08 +
        ex_score * 0.05 +
        st_score * 0.05
    )

    return {
        "lane": lane,
        "course": int(entry.get("course") or lane),
        "racer_name": entry.get("racer_name", ""),
        "racer_number": entry.get("racer_number"),
        "strength": round(strength, 6),
        "weather_risk": round(weather_risk, 6),
        "ex_score": round(ex_score, 6),
        "st_score": round(st_score, 6),
    }
