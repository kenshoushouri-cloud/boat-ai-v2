# -*- coding: utf-8 -*-
"""
audit_motor_boat_data_quality_pg.py

モーター・ボート2連率のデータ品質を確認します。
同一会場×番号について、日付順の値変化、0/100、番号0、急変を検出します。

読み取り専用。LINE送信・DB更新なし。

Railway Start Command:
    python -u audit_motor_boat_data_quality_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    ANALYZE_START_DATE=YYYY-MM-DD
    ANALYZE_END_DATE=YYYY-MM-DD
    AUDIT_SAMPLE_LIMIT=50
    RATE_JUMP_THRESHOLD=15
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))
END_DATE = os.getenv("ANALYZE_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("ANALYZE_START_DATE") or (
    datetime.strptime(END_DATE, "%Y-%m-%d") - timedelta(days=60)
).strftime("%Y-%m-%d")
SAMPLE_LIMIT = max(1, int(os.getenv("AUDIT_SAMPLE_LIMIT", "50")))
JUMP_THRESHOLD = float(os.getenv("RATE_JUMP_THRESHOLD", "15"))


def sf(v: Any, d: Optional[float] = None) -> Optional[float]:
    try:
        if v is None or v == "":
            return d
        return float(str(v).replace(",", ""))
    except Exception:
        return d


def pct(n: int, d: int) -> str:
    return "-" if d <= 0 else f"{n / d * 100:.1f}%"


def audit(kind: str, no_col: str, rate_col: str) -> None:
    rows = fetch_all(
        f"""
        select
            e.race_id,
            r.race_date,
            coalesce(r.venue_id, r.venue_code) as venue_id,
            e.lane,
            e.{no_col} as unit_no,
            e.{rate_col} as rate
        from v2_race_entries e
        join v2_races r on r.race_id = e.race_id
        where r.race_date >= %s
          and r.race_date <= %s
        order by venue_id, unit_no, r.race_date, e.race_id, e.lane;
        """,
        (START_DATE, END_DATE),
    )

    total = len(rows)
    invalid_no = []
    invalid_rate = []
    zero_rate = []
    hundred_rate = []

    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)

    for r in rows:
        venue = str(r.get("venue_id") or "").zfill(2)
        no = str(r.get("unit_no") or "").strip()
        rate = sf(r.get("rate"))

        if not no or no == "0":
            invalid_no.append(r)
        if rate is None or rate < 0 or rate > 100:
            invalid_rate.append(r)
        elif rate == 0:
            zero_rate.append(r)
        elif rate == 100:
            hundred_rate.append(r)

        if venue and no and no != "0" and rate is not None and 0 <= rate <= 100:
            grouped[(venue, no)].append(
                {
                    "race_id": str(r.get("race_id") or ""),
                    "date": str(r.get("race_date") or ""),
                    "lane": r.get("lane"),
                    "rate": rate,
                }
            )

    # 同一日の同一番号は同じ累積率であるべきなので、日単位にまとめる
    same_day_conflicts = []
    transitions = []
    reset_candidates = []

    for (venue, no), xs in grouped.items():
        by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for x in xs:
            by_date[x["date"]].append(x)

        daily: List[Tuple[str, float]] = []
        for d in sorted(by_date):
            values = sorted({round(float(x["rate"]), 4) for x in by_date[d]})
            if len(values) > 1:
                same_day_conflicts.append(
                    {
                        "venue": venue,
                        "no": no,
                        "date": d,
                        "values": values,
                        "race_ids": [x["race_id"] for x in by_date[d]][:12],
                    }
                )
            # 代表値はその日の最終レコードの値
            daily.append((d, float(by_date[d][-1]["rate"])))

        for i in range(1, len(daily)):
            prev_date, prev_rate = daily[i - 1]
            cur_date, cur_rate = daily[i]
            delta = cur_rate - prev_rate
            rec = {
                "venue": venue,
                "no": no,
                "prev_date": prev_date,
                "date": cur_date,
                "prev_rate": prev_rate,
                "rate": cur_rate,
                "delta": delta,
            }
            if abs(delta) >= JUMP_THRESHOLD:
                transitions.append(rec)
            # 高率から極端な低率、または低率から高率への急変を番号更新候補とする
            if (
                (prev_rate >= 20 and cur_rate <= 10)
                or (prev_rate <= 10 and cur_rate >= 30)
                or abs(delta) >= 30
            ):
                reset_candidates.append(rec)

    print("\n" + "=" * 80, flush=True)
    print(f"{kind} DATA QUALITY", flush=True)
    print(f"rows={total} unique_venue_units={len(grouped)}", flush=True)
    print(f"invalid/zero unit_no={len(invalid_no)} ({pct(len(invalid_no), total)})", flush=True)
    print(f"invalid rate={len(invalid_rate)} ({pct(len(invalid_rate), total)})", flush=True)
    print(f"rate=0 rows={len(zero_rate)} ({pct(len(zero_rate), total)})", flush=True)
    print(f"rate=100 rows={len(hundred_rate)} ({pct(len(hundred_rate), total)})", flush=True)
    print(f"same-day conflicting rates={len(same_day_conflicts)}", flush=True)
    print(f"day-to-day jumps >= {JUMP_THRESHOLD:g}pt={len(transitions)}", flush=True)
    print(f"reset/update candidates={len(reset_candidates)}", flush=True)

    print(f"\n{kind} invalid unit samples", flush=True)
    for r in invalid_no[:SAMPLE_LIMIT]:
        print(
            f"  race_id={r.get('race_id')} venue={r.get('venue_id')} "
            f"lane={r.get('lane')} no={r.get('unit_no')} rate={r.get('rate')}",
            flush=True,
        )

    print(f"\n{kind} same-day conflict samples", flush=True)
    for x in same_day_conflicts[:SAMPLE_LIMIT]:
        print(
            f"  venue={x['venue']} no={x['no']} date={x['date']} "
            f"values={x['values']} race_ids={x['race_ids']}",
            flush=True,
        )

    print(f"\n{kind} reset/update candidate samples", flush=True)
    for x in sorted(reset_candidates, key=lambda z: abs(z["delta"]), reverse=True)[:SAMPLE_LIMIT]:
        print(
            f"  venue={x['venue']} no={x['no']} "
            f"{x['prev_date']}:{x['prev_rate']:.2f} -> "
            f"{x['date']}:{x['rate']:.2f} delta={x['delta']:+.2f}",
            flush=True,
        )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ audit_motor_boat_data_quality_pg.py VERSION 2026-07-14", flush=True)
    print(
        f"PERIOD={START_DATE}..{END_DATE} "
        f"RATE_JUMP_THRESHOLD={JUMP_THRESHOLD:g}",
        flush=True,
    )
    print("読み取り専用です。LINE送信・DB更新は行いません。", flush=True)

    audit("MOTOR", "motor_no", "motor_place2_rate")
    audit("BOAT", "boat_no", "boat_place2_rate")

    print("\n判定目安", flush=True)
    print("- 同一日・同一番号で率が複数なら、取得または列マッピングの問題", flush=True)
    print("- 日をまたいで30pt以上急変なら、番号更新・交換時期または誤取得の可能性", flush=True)
    print("- unit_no=0は予想特徴量から除外", flush=True)
    print("- 品質確認が終わるまで、モーター実値は本番ロジックへ直接入れない", flush=True)
    print("=== motor/boat data quality audit finished ===", flush=True)


if __name__ == "__main__":
    main()