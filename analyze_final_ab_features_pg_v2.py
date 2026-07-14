# -*- coding: utf-8 -*-
"""
analyze_final_ab_features_pg_v2.py

final_ab特徴量分析・結果照合修正版。
結果の3連単は first_lane / second_lane / third_lane を最優先で使用し、
trifecta_ticket文字列は補助として使います。

読み取り専用。LINE送信・DB更新なし。
"""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from db_pg import fetch_all, fetch_one

JST = timezone(timedelta(hours=9))
END_DATE = os.getenv("ANALYZE_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("ANALYZE_START_DATE") or (
    datetime.strptime(END_DATE, "%Y-%m-%d") - timedelta(days=30)
).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SAMPLE_LIMIT = max(1, int(os.getenv("ANALYZE_SAMPLE_LIMIT", "20")))


def si(v: Any, d: int = 0) -> int:
    try:
        if v is None or v == "":
            return d
        return int(float(str(v).replace(",", "")))
    except Exception:
        return d


def sf(v: Any, d: Optional[float] = None) -> Optional[float]:
    try:
        if v is None or v == "":
            return d
        return float(str(v).replace(",", ""))
    except Exception:
        return d


def normalize_ticket(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    nums = re.findall(r"(?<!\d)([1-6])(?!\d)", s)
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    # "123" のように区切り無しの可能性
    compact = re.sub(r"\D", "", s)
    if len(compact) >= 3 and all(c in "123456" for c in compact[:3]):
        return f"{compact[0]}-{compact[1]}-{compact[2]}"
    return ""


def table_exists(table: str) -> bool:
    r = fetch_one(
        """select exists (
               select 1 from information_schema.tables
               where table_schema='public' and table_name=%s
           ) as ok;""",
        (table,),
    )
    return bool(r and r.get("ok"))


def columns(table: str) -> List[str]:
    rows = fetch_all(
        """select column_name from information_schema.columns
           where table_schema='public' and table_name=%s
           order by ordinal_position;""",
        (table,),
    )
    return [str(r.get("column_name")) for r in rows]


def first_col(cols: Sequence[str], names: Iterable[str]) -> Optional[str]:
    s = set(cols)
    for n in names:
        if n in s:
            return n
    return None


def pct(n: int, d: int) -> str:
    return "-" if d <= 0 else f"{n/d*100:.1f}%"


def wind_bucket(v: Optional[float]) -> str:
    if v is None:
        return "missing"
    if v <= 2:
        return "0-2m"
    if v <= 4:
        return "3-4m"
    return "5m+"


def wave_bucket(v: Optional[float]) -> str:
    if v is None:
        return "missing"
    if v <= 2:
        return "0-2cm"
    if v <= 5:
        return "3-5cm"
    return "6cm+"


def rank_bucket(v: int) -> str:
    if v <= 0:
        return "missing"
    if v <= 2:
        return "1-2位"
    if v <= 4:
        return "3-4位"
    return "5-6位"


def odds_bucket(v: Optional[float]) -> str:
    if v is None or v <= 0:
        return "missing"
    if v < 3:
        return "<3"
    if v < 5:
        return "3-5"
    if v < 10:
        return "5-10"
    return "10+"


def load_results() -> Dict[str, Dict[str, Any]]:
    if not table_exists("v2_results"):
        return {}

    cs = columns("v2_results")
    tc = first_col(cs, ["trifecta_ticket", "result_ticket", "ticket"])
    pc = first_col(cs, ["trifecta_payout_yen", "trifecta_payout", "payout_yen"])
    f1 = first_col(cs, ["first_lane"])
    f2 = first_col(cs, ["second_lane"])
    f3 = first_col(cs, ["third_lane"])

    select_parts = ["race_id"]
    select_parts.append(f"{tc} as ticket_raw" if tc else "null::text as ticket_raw")
    select_parts.append(f"{pc} as payout" if pc else "0::numeric as payout")
    select_parts.append(f"{f1} as first_lane" if f1 else "null::integer as first_lane")
    select_parts.append(f"{f2} as second_lane" if f2 else "null::integer as second_lane")
    select_parts.append(f"{f3} as third_lane" if f3 else "null::integer as third_lane")

    end_ex = (datetime.strptime(END_DATE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
    rows = fetch_all(
        f"""select {", ".join(select_parts)}
            from v2_results
            where race_id >= %s and race_id < %s;""",
        (START_DATE.replace("-", ""), end_ex),
    )

    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        rid = str(r.get("race_id") or "")
        if not rid:
            continue

        a = si(r.get("first_lane"))
        b = si(r.get("second_lane"))
        c = si(r.get("third_lane"))

        if 1 <= a <= 6 and 1 <= b <= 6 and 1 <= c <= 6:
            ticket = f"{a}-{b}-{c}"
            source = "finish_lanes"
        else:
            ticket = normalize_ticket(r.get("ticket_raw"))
            source = "ticket_text"

        out[rid] = {
            "ticket": ticket,
            "ticket_raw": r.get("ticket_raw"),
            "ticket_source": source,
            "payout": si(r.get("payout")),
            "first_lane": a or (si(ticket.split("-")[0]) if ticket else 0),
        }
    return out


def load_weather() -> Dict[str, Dict[str, Any]]:
    rows = fetch_all(
        """select race_id, weather, temperature_c, water_temperature_c,
                  wind_speed_m, wind_direction, wave_height_cm
           from v2_realtime_weather_snapshots
           where race_date >= %s and race_date <= %s
             and snapshot_label=%s;""",
        (START_DATE, END_DATE, SNAPSHOT_LABEL),
    )
    return {str(r.get("race_id")): r for r in rows if r.get("race_id")}


def load_exhibition() -> Dict[str, Dict[int, Dict[str, Any]]]:
    rows = fetch_all(
        """select race_id, lane, exhibition_time, exhibition_time_rank,
                  start_timing, start_timing_rank
           from v2_realtime_exhibition_snapshots
           where race_date >= %s and race_date <= %s
             and snapshot_label=%s;""",
        (START_DATE, END_DATE, SNAPSHOT_LABEL),
    )
    out: Dict[str, Dict[int, Dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        rid = str(r.get("race_id") or "")
        lane = si(r.get("lane"))
        if rid and 1 <= lane <= 6:
            out[rid][lane] = r
    return dict(out)


def load_entries() -> Dict[str, Dict[int, Dict[str, Any]]]:
    rows = fetch_all(
        """select race_id, lane, is_course_changed
           from v2_realtime_entry_snapshots
           where race_date >= %s and race_date <= %s
             and snapshot_label=%s;""",
        (START_DATE, END_DATE, SNAPSHOT_LABEL),
    )
    out: Dict[str, Dict[int, Dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        rid = str(r.get("race_id") or "")
        lane = si(r.get("lane"))
        if rid and 1 <= lane <= 6:
            out[rid][lane] = r
    return dict(out)


def load_favorites() -> Dict[str, Dict[str, Any]]:
    rows = fetch_all(
        """select race_id, ticket, odds, odds_delta_pct,
                  is_odds_drift, is_odds_steam
           from v2_realtime_odds_snapshots
           where race_date >= %s and race_date <= %s
             and snapshot_label=%s
             and market_rank=1;""",
        (START_DATE, END_DATE, SNAPSHOT_LABEL),
    )
    out = {}
    for r in rows:
        rid = str(r.get("race_id") or "")
        if rid:
            x = dict(r)
            x["ticket_norm"] = normalize_ticket(r.get("ticket"))
            out[rid] = x
    return out


def add(agg: Dict[str, Counter], key: str, first_lane: int, favorite_hit: bool) -> None:
    c = agg.setdefault(key, Counter())
    c["races"] += 1
    c["lane1"] += int(first_lane == 1)
    c["favorite_hit"] += int(favorite_hit)


def show(title: str, agg: Dict[str, Counter]) -> None:
    print("\n" + title, flush=True)
    for key in sorted(agg):
        c = agg[key]
        print(
            f"  {key}: races={c['races']} "
            f"1号艇1着={c['lane1']} ({pct(c['lane1'], c['races'])}) "
            f"1番人気的中={c['favorite_hit']} ({pct(c['favorite_hit'], c['races'])})",
            flush=True,
        )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ analyze_final_ab_features_pg_v2.py VERSION 2026-07-14 ticket-fix", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL}", flush=True)
    print("読み取り専用です。LINE送信・DB更新は行いません。", flush=True)

    results = load_results()
    weather = load_weather()
    exhibition = load_exhibition()
    entries = load_entries()
    favorites = load_favorites()

    print(
        f"loaded results={len(results)} weather={len(weather)} "
        f"exhibition_races={len(exhibition)} entry_races={len(entries)} "
        f"favorite_odds={len(favorites)}",
        flush=True,
    )

    ids = sorted(set(results) & set(weather) & set(favorites))
    print(f"joined_base_races={len(ids)}", flush=True)

    aggs = [{} for _ in range(8)]
    full_ex = 0
    hit_total = 0
    mismatch_samples = []
    hit_samples = []

    for rid in ids:
        r = results[rid]
        w = weather[rid]
        f = favorites[rid]
        ex = exhibition.get(rid, {})
        en = entries.get(rid, {})

        result_ticket = str(r.get("ticket") or "")
        fav_ticket = str(f.get("ticket_norm") or "")
        hit = bool(result_ticket and fav_ticket and result_ticket == fav_ticket)
        hit_total += int(hit)

        if hit and len(hit_samples) < SAMPLE_LIMIT:
            hit_samples.append((rid, result_ticket, fav_ticket, r.get("ticket_raw")))
        if not hit and len(mismatch_samples) < SAMPLE_LIMIT:
            mismatch_samples.append((rid, result_ticket, fav_ticket, r.get("ticket_raw"), f.get("ticket")))

        first_lane = si(r.get("first_lane"))
        add(aggs[0], wind_bucket(sf(w.get("wind_speed_m"))), first_lane, hit)
        add(aggs[1], wave_bucket(sf(w.get("wave_height_cm"))), first_lane, hit)
        add(aggs[2], str(w.get("wind_direction") or "missing"), first_lane, hit)
        add(aggs[5], odds_bucket(sf(f.get("odds"))), first_lane, hit)

        move = (
            "steam(-15%以上)" if f.get("is_odds_steam")
            else "drift(+15%以上)" if f.get("is_odds_drift")
            else "stable"
        )
        add(aggs[7], move, first_lane, hit)

        changed = any(bool(x.get("is_course_changed")) for x in en.values())
        add(aggs[6], "進入変更あり" if changed else "進入変更なし", first_lane, hit)

        if ex:
            full_ex += int(len(ex) == 6)
            add(aggs[3], rank_bucket(si((ex.get(1) or {}).get("exhibition_time_rank"))), first_lane, hit)
            head = si(fav_ticket.split("-")[0]) if fav_ticket else 0
            add(aggs[4], rank_bucket(si((ex.get(head) or {}).get("exhibition_time_rank"))), first_lane, hit)

    print(f"favorite_hit_total={hit_total}/{len(ids)} ({pct(hit_total, len(ids))})", flush=True)
    print(f"full_6_lane_exhibition={full_ex}", flush=True)

    titles = [
        "【風速別】",
        "【波高別】",
        "【風向別】",
        "【1号艇 展示タイム順位別】",
        "【1番人気の頭艇 展示タイム順位別】",
        "【1番人気オッズ帯別】",
        "【進入変更有無】",
        "【1番人気オッズ変動別】",
    ]
    for title, agg in zip(titles, aggs):
        show(title, agg)

    print("\n【的中サンプル】", flush=True)
    for x in hit_samples:
        print(" ", x, flush=True)

    print("\n【不一致サンプル】", flush=True)
    for x in mismatch_samples:
        print(" ", x, flush=True)

    print("\n注意: 全対象レースの傾向であり、BUY候補限定ROIではありません。", flush=True)
    print("=== final_ab feature analysis v2 finished ===", flush=True)


if __name__ == "__main__":
    main()