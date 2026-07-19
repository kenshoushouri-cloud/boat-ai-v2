# -*- coding: utf-8 -*-
"""
analyze_previous_st_conditions_pg.py

前走STが「どの条件で着順予測に効くか」を調べる読み取り専用診断。
最新の final_ab スナップショットを race_id × lane ごとに1件採用し、
実着順との関係を全体・艇番・級別・レース帯・場別で集計します。

DB更新・LINE送信なし。

Railway Start Command:
    python -u analyze_previous_st_conditions_pg.py

Variables:
    DATABASE_URL
    DIAG_START_DATE=2026-01-01
    DIAG_END_DATE=2026-03-31
    DIAG_SNAPSHOT_LABEL=final_ab
    DIAG_MIN_SAMPLES=100
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all

START = os.getenv("DIAG_START_DATE", "2026-01-01")
END = os.getenv("DIAG_END_DATE", "2026-03-31")
LABEL = os.getenv("DIAG_SNAPSHOT_LABEL", "final_ab")
MIN_N = max(30, int(os.getenv("DIAG_MIN_SAMPLES", "100")))


def sf(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def si(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def st_bucket(v: Any) -> str:
    if v is None:
        return "MISSING"
    x = sf(v, -1)
    if x < 0:
        return "MISSING"
    if x == 0:
        return "00"
    if x <= 0.08:
        return "01_<=0.08"
    if x <= 0.12:
        return "02_0.09-0.12"
    if x <= 0.17:
        return "03_0.13-0.17"
    if x <= 0.22:
        return "04_0.18-0.22"
    if x <= 0.30:
        return "05_0.23-0.30"
    return "06_>0.30"


def class_text(row: Dict[str, Any]) -> str:
    t = str(row.get("racer_class_text") or "").strip().upper()
    if t:
        return t
    return {"4": "A1", "3": "A2", "2": "B1", "1": "B2"}.get(
        str(row.get("racer_class") or ""), "UNKNOWN"
    )


def race_band(race_no: int) -> str:
    if race_no <= 3:
        return "R01-03"
    if race_no <= 6:
        return "R04-06"
    if race_no <= 9:
        return "R07-09"
    return "R10-12"


def finish_for_lane(row: Dict[str, Any], lane: int) -> int | None:
    for pos in range(1, 7):
        if si(row.get(f"p{pos}"), -1) == lane:
            return pos
    return None


class Agg:
    def __init__(self) -> None:
        self.n = 0
        self.win = 0
        self.top2 = 0
        self.top3 = 0
        self.sum_finish = 0

    def add(self, finish: int) -> None:
        self.n += 1
        self.win += int(finish == 1)
        self.top2 += int(finish <= 2)
        self.top3 += int(finish <= 3)
        self.sum_finish += finish

    def line(self) -> str:
        if not self.n:
            return "n=0"
        return (
            f"n={self.n} avg_finish={self.sum_finish/self.n:.3f} "
            f"win={self.win/self.n*100:.2f}% "
            f"top2={self.top2/self.n*100:.2f}% "
            f"top3={self.top3/self.n*100:.2f}%"
        )


def load_rows() -> List[Dict[str, Any]]:
    return fetch_all(
        """
        with latest_st as (
          select *
          from (
            select
              s.race_id,
              s.lane,
              s.previous_st,
              s.previous_finish,
              s.previous_course,
              s.racer_number,
              s.snapshot_label,
              s.snapshot_at,
              row_number() over (
                partition by s.race_id, s.lane
                order by s.snapshot_at desc nulls last, s.id desc
              ) rn
            from v2_realtime_racer_condition_snapshots s
            join v2_races r0 on r0.race_id=s.race_id
            where r0.race_date between %s and %s
              and s.snapshot_label=%s
          ) z
          where rn=1
        )
        select
          r.race_id,
          r.race_date,
          coalesce(r.venue_id, r.venue_code) venue_id,
          r.race_no,
          e.lane,
          e.racer_class,
          e.racer_class_text,
          e.avg_st,
          st.previous_st,
          st.previous_finish,
          st.previous_course,
          rs.first_lane p1,
          rs.second_lane p2,
          rs.third_lane p3,
          rs.fourth_lane p4,
          rs.fifth_lane p5,
          rs.sixth_lane p6
        from v2_races r
        join v2_race_entries e on e.race_id=r.race_id
        join v2_results rs on rs.race_id=r.race_id
        left join latest_st st
          on st.race_id=e.race_id and st.lane=e.lane
        where r.race_date between %s and %s
          and rs.first_lane is not null
          and rs.second_lane is not null
          and rs.third_lane is not null
          and rs.fourth_lane is not null
          and rs.fifth_lane is not null
          and rs.sixth_lane is not null
        order by r.race_date, r.race_id, e.lane;
        """,
        (START, END, LABEL, START, END),
    )


def show_group(title: str, rows: List[Dict[str, Any]], key_fn, min_n: int = 1) -> None:
    groups: Dict[Any, Agg] = {}
    for row in rows:
        finish = finish_for_lane(row, si(row.get("lane")))
        if finish is None:
            continue
        key = key_fn(row)
        groups.setdefault(key, Agg()).add(finish)

    print(f"\n=== {title} ===", flush=True)
    shown = 0
    for key in sorted(groups, key=lambda x: str(x)):
        a = groups[key]
        if a.n < min_n:
            continue
        print(f"{key}: {a.line()}", flush=True)
        shown += 1
    if not shown:
        print("該当なし", flush=True)


def compare_fast_slow(rows: List[Dict[str, Any]], condition_name: str, key_fn) -> None:
    tmp: Dict[Any, Dict[str, Agg]] = {}
    for row in rows:
        pst = row.get("previous_st")
        if pst is None:
            continue
        x = sf(pst)
        band = "FAST_<=0.08" if x <= 0.08 else ("SLOW_>=0.18" if x >= 0.18 else "MID")
        finish = finish_for_lane(row, si(row.get("lane")))
        if finish is None:
            continue
        key = key_fn(row)
        tmp.setdefault(key, {}).setdefault(band, Agg()).add(finish)

    print(f"\n=== FAST/SLOW COMPARISON: {condition_name} ===", flush=True)
    candidates: List[Tuple[float, int, str]] = []
    for key, bands in tmp.items():
        fast = bands.get("FAST_<=0.08")
        slow = bands.get("SLOW_>=0.18")
        if not fast or not slow or fast.n < MIN_N or slow.n < MIN_N:
            continue
        fast_top3 = fast.top3 / fast.n * 100
        slow_top3 = slow.top3 / slow.n * 100
        diff = fast_top3 - slow_top3
        line = (
            f"{key}: FAST[{fast.line()}] SLOW[{slow.line()}] "
            f"top3_diff={diff:+.2f}pt"
        )
        candidates.append((abs(diff), fast.n + slow.n, line))

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if not candidates:
        print(f"比較可能条件なし（各群 MIN_N={MIN_N}）", flush=True)
        return
    for _, _, line in candidates[:40]:
        print(line, flush=True)


def split_validation(rows: List[Dict[str, Any]]) -> None:
    print("\n=== TRAIN / VALIDATION CHECK ===", flush=True)
    for name, pred in [
        ("TRAIN_JAN_FEB", lambda d: str(d.get("race_date"))[:7] in ("2026-01", "2026-02")),
        ("VALID_MARCH", lambda d: str(d.get("race_date"))[:7] == "2026-03"),
    ]:
        subset = [r for r in rows if pred(r)]
        fast = Agg()
        slow = Agg()
        for r in subset:
            if r.get("previous_st") is None:
                continue
            finish = finish_for_lane(r, si(r.get("lane")))
            if finish is None:
                continue
            x = sf(r.get("previous_st"))
            if x <= 0.08:
                fast.add(finish)
            elif x >= 0.18:
                slow.add(finish)
        diff = (
            fast.top3 / fast.n * 100 - slow.top3 / slow.n * 100
            if fast.n and slow.n else 0.0
        )
        print(
            f"{name}: FAST[{fast.line()}] SLOW[{slow.line()}] "
            f"top3_diff={diff:+.2f}pt",
            flush=True,
        )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ analyze_previous_st_conditions_pg.py VERSION 2026-07-20 condition-lab-v1", flush=True)
    print(f"PERIOD={START}..{END} SNAPSHOT_LABEL={LABEL} MIN_N={MIN_N}", flush=True)
    print("読み取り専用です。DB更新・LINE送信は行いません。", flush=True)

    rows = load_rows()
    races = {str(r.get("race_id")) for r in rows}
    st_rows = sum(r.get("previous_st") is not None for r in rows)
    st_races = {str(r.get("race_id")) for r in rows if r.get("previous_st") is not None}
    print(
        f"loaded_entry_rows={len(rows)} races={len(races)} "
        f"previous_st_rows={st_rows} previous_st_races={len(st_races)}",
        flush=True,
    )

    show_group("PREVIOUS ST BUCKET", rows, lambda r: st_bucket(r.get("previous_st")))
    show_group(
        "LANE x PREVIOUS ST BUCKET",
        rows,
        lambda r: f"lane={si(r.get('lane'))} st={st_bucket(r.get('previous_st'))}",
        MIN_N,
    )
    show_group(
        "CLASS x PREVIOUS ST BUCKET",
        rows,
        lambda r: f"class={class_text(r)} st={st_bucket(r.get('previous_st'))}",
        MIN_N,
    )
    show_group(
        "RACE BAND x PREVIOUS ST BUCKET",
        rows,
        lambda r: f"{race_band(si(r.get('race_no')))} st={st_bucket(r.get('previous_st'))}",
        MIN_N,
    )
    show_group(
        "PREVIOUS FINISH x ST BUCKET",
        rows,
        lambda r: f"prev_finish={r.get('previous_finish')} st={st_bucket(r.get('previous_st'))}",
        MIN_N,
    )

    compare_fast_slow(rows, "LANE", lambda r: f"lane={si(r.get('lane'))}")
    compare_fast_slow(rows, "CLASS", lambda r: f"class={class_text(r)}")
    compare_fast_slow(rows, "RACE BAND", lambda r: race_band(si(r.get("race_no"))))
    compare_fast_slow(
        rows,
        "LANE x CLASS",
        lambda r: f"lane={si(r.get('lane'))} class={class_text(r)}",
    )
    compare_fast_slow(
        rows,
        "VENUE",
        lambda r: f"venue={str(r.get('venue_id') or '').zfill(2)}",
    )

    split_validation(rows)

    print("\n判定方針:", flush=True)
    print("- FASTとSLOWの差が大きくても、3月検証で同方向にならなければ採用しません。", flush=True)
    print("- 場別・複合条件は多重比較になるため、件数と再現性を優先します。", flush=True)
    print("- この診断後に、採用候補だけ3連単順位モデルへ限定補正します。", flush=True)
    print("=== previous ST condition lab finished ===", flush=True)


if __name__ == "__main__":
    main()