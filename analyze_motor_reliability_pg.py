# -*- coding: utf-8 -*-
"""
analyze_motor_reliability_pg.py

v2_race_entries を使い、会場×モーター番号ごとの蓄積量と
モーター2連率の信頼度候補を集計します。

目的:
- 交換・番号更新直後の少サンプルを平均値へ縮約するための基礎確認
- v24 の固定 motor=33%, boat=34% を実値へ置き換える準備

読み取り専用。LINE送信・DB更新なし。

Railway Start Command:
    python -u analyze_motor_reliability_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    ANALYZE_START_DATE=YYYY-MM-DD
    ANALYZE_END_DATE=YYYY-MM-DD
    MOTOR_SAMPLE_LIMIT=30
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from typing import Any, Dict, List, Optional, Tuple

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))
END_DATE = os.getenv("ANALYZE_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("ANALYZE_START_DATE") or (
    datetime.strptime(END_DATE, "%Y-%m-%d") - timedelta(days=60)
).strftime("%Y-%m-%d")
SAMPLE_LIMIT = max(1, int(os.getenv("MOTOR_SAMPLE_LIMIT", "30")))


def sf(v: Any, d: Optional[float] = None) -> Optional[float]:
    try:
        if v is None or v == "":
            return d
        return float(str(v).replace(",", ""))
    except Exception:
        return d


def si(v: Any, d: int = 0) -> int:
    try:
        if v is None or v == "":
            return d
        return int(float(str(v).replace(",", "")))
    except Exception:
        return d


def reliability_from_appearances(n: int) -> float:
    """
    初期の仮信頼度。
    これは本採用係数ではなく、分布確認用。
      1-5  : 0.20
      6-15 : 0.50
      16-30: 0.80
      31+  : 1.00
    """
    if n <= 5:
        return 0.20
    if n <= 15:
        return 0.50
    if n <= 30:
        return 0.80
    return 1.00


def bucket(n: int) -> str:
    if n <= 5:
        return "1-5"
    if n <= 15:
        return "6-15"
    if n <= 30:
        return "16-30"
    return "31+"


def pct(n: int, d: int) -> str:
    return "-" if d <= 0 else f"{n / d * 100:.1f}%"


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ analyze_motor_reliability_pg.py VERSION 2026-07-14", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("読み取り専用です。LINE送信・DB更新は行いません。", flush=True)

    rows = fetch_all(
        """
        select
            e.race_id,
            r.race_date,
            coalesce(r.venue_id, r.venue_code) as venue_id,
            e.lane,
            e.motor_no,
            e.motor_place2_rate,
            e.boat_no,
            e.boat_place2_rate
        from v2_race_entries e
        join v2_races r on r.race_id = e.race_id
        where r.race_date >= %s
          and r.race_date <= %s
        order by r.race_date, venue_id, e.motor_no, e.race_id, e.lane;
        """,
        (START_DATE, END_DATE),
    )

    print(f"entry_rows={len(rows)}", flush=True)

    motor: Dict[Tuple[str, str], Dict[str, Any]] = {}
    boat: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for r in rows:
        venue = str(r.get("venue_id") or "").zfill(2)
        race_date = str(r.get("race_date") or "")
        race_id = str(r.get("race_id") or "")

        mno = str(r.get("motor_no") or "").strip()
        mrate = sf(r.get("motor_place2_rate"))
        if venue and mno:
            key = (venue, mno)
            x = motor.setdefault(
                key,
                {
                    "venue": venue,
                    "no": mno,
                    "rows": 0,
                    "race_ids": set(),
                    "dates": set(),
                    "rates": [],
                    "first_date": race_date,
                    "last_date": race_date,
                },
            )
            x["rows"] += 1
            x["race_ids"].add(race_id)
            x["dates"].add(race_date)
            if mrate is not None:
                x["rates"].append(mrate)
            x["first_date"] = min(x["first_date"], race_date)
            x["last_date"] = max(x["last_date"], race_date)

        bno = str(r.get("boat_no") or "").strip()
        brate = sf(r.get("boat_place2_rate"))
        if venue and bno:
            key = (venue, bno)
            x = boat.setdefault(
                key,
                {
                    "venue": venue,
                    "no": bno,
                    "rows": 0,
                    "race_ids": set(),
                    "dates": set(),
                    "rates": [],
                    "first_date": race_date,
                    "last_date": race_date,
                },
            )
            x["rows"] += 1
            x["race_ids"].add(race_id)
            x["dates"].add(race_date)
            if brate is not None:
                x["rates"].append(brate)
            x["first_date"] = min(x["first_date"], race_date)
            x["last_date"] = max(x["last_date"], race_date)

    def summarize(name: str, items: Dict[Tuple[str, str], Dict[str, Any]], prior: float) -> None:
        counts = Counter()
        appearances: List[int] = []
        all_rates: List[float] = []
        details: List[Dict[str, Any]] = []

        for x in items.values():
            n = len(x["race_ids"])
            counts[bucket(n)] += 1
            appearances.append(n)
            rates = x["rates"]
            avg_rate = mean(rates) if rates else prior
            rel = reliability_from_appearances(n)
            shrunk = avg_rate * rel + prior * (1.0 - rel)
            all_rates.extend(rates)
            details.append(
                {
                    **x,
                    "appearances": n,
                    "active_days": len(x["dates"]),
                    "avg_rate": avg_rate,
                    "reliability": rel,
                    "shrunk_rate": shrunk,
                    "rate_spread": (max(rates) - min(rates)) if rates else 0.0,
                }
            )

        print("\n" + "=" * 72, flush=True)
        print(f"{name} SUMMARY", flush=True)
        print(f"unique_units={len(items)}", flush=True)
        if appearances:
            print(
                f"appearances min={min(appearances)} median={median(appearances):.1f} "
                f"mean={mean(appearances):.1f} max={max(appearances)}",
                flush=True,
            )
        if all_rates:
            print(
                f"reported_2rate min={min(all_rates):.2f} median={median(all_rates):.2f} "
                f"mean={mean(all_rates):.2f} max={max(all_rates):.2f}",
                flush=True,
            )
        for k in ("1-5", "6-15", "16-30", "31+"):
            print(f"  appearances {k}: {counts[k]} ({pct(counts[k], len(items))})", flush=True)

        # 率の値が期間内に大きく変わるものは番号更新や母数増加の観察対象
        unstable = sorted(details, key=lambda x: x["rate_spread"], reverse=True)
        print(f"\n{name} rate-change samples", flush=True)
        for x in unstable[:SAMPLE_LIMIT]:
            print(
                f"  venue={x['venue']} no={x['no']} appearances={x['appearances']} "
                f"days={x['active_days']} first={x['first_date']} last={x['last_date']} "
                f"avg={x['avg_rate']:.2f} spread={x['rate_spread']:.2f} "
                f"rel={x['reliability']:.2f} shrunk={x['shrunk_rate']:.2f}",
                flush=True,
            )

        low_sample = sorted(
            [x for x in details if x["appearances"] <= 5],
            key=lambda x: (x["first_date"], x["venue"], x["no"]),
            reverse=True,
        )
        print(f"\n{name} low-sample recent units", flush=True)
        for x in low_sample[:SAMPLE_LIMIT]:
            print(
                f"  venue={x['venue']} no={x['no']} appearances={x['appearances']} "
                f"first={x['first_date']} last={x['last_date']} "
                f"raw={x['avg_rate']:.2f} rel={x['reliability']:.2f} "
                f"shrunk={x['shrunk_rate']:.2f}",
                flush=True,
            )

    summarize("MOTOR", motor, 33.0)
    summarize("BOAT", boat, 34.0)

    print("\n判定目安", flush=True)
    print("- appearancesが少ない単位が多ければ、実2連率の完全反映は危険", flush=True)
    print("- 同一番号の2連率spreadが大きいのは、母数増加による変化または番号更新の要確認対象", flush=True)
    print("- 最初は縮約値を裏側特徴量として保存し、現行固定値とのA/B比較を行う", flush=True)
    print("=== motor reliability analysis finished ===", flush=True)


if __name__ == "__main__":
    main()