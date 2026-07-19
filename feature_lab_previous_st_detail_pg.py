# -*- coding: utf-8 -*-
"""
feature_lab_previous_st_detail_pg.py

前走STの「効く条件」を探索する読み取り専用診断。
本番判定・LINE通知・購入処理・DB更新は行いません。

Railway Start Command:
    python -u feature_lab_previous_st_detail_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    FEATURE_LAB_START_DATE=2026-01-01
    FEATURE_LAB_END_DATE=2026-03-31
    ST_DETAIL_MIN_SAMPLES=100
    ST_DETAIL_MIN_LIFT_PT=1.0
    ST_DETAIL_TOP_N=40
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db_pg import fetch_all, fetch_one

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("FEATURE_LAB_START_DATE") or os.getenv("DIAG_START_DATE") or TODAY
END_DATE = os.getenv("FEATURE_LAB_END_DATE") or os.getenv("DIAG_END_DATE") or TODAY
MIN_SAMPLES = max(20, int(os.getenv("ST_DETAIL_MIN_SAMPLES", "100")))
MIN_LIFT_PT = float(os.getenv("ST_DETAIL_MIN_LIFT_PT", "1.0"))
TOP_N = max(10, int(os.getenv("ST_DETAIL_TOP_N", "40")))

ENTRY_TABLE = "v2_race_entries"
RESULT_TABLE = "v2_results"
RACE_TABLE = "v2_races"
EXHIBITION_TABLE = "v2_exhibition"


def table_exists(table: str) -> bool:
    row = fetch_one(
        """select exists (
               select 1 from information_schema.tables
               where table_schema='public' and table_name=%s
           ) as ok;""",
        (table,),
    )
    return bool(row and row.get("ok"))


def columns(table: str) -> List[str]:
    rows = fetch_all(
        """select column_name from information_schema.columns
           where table_schema='public' and table_name=%s
           order by ordinal_position;""",
        (table,),
    )
    return [str(r["column_name"]) for r in rows]


def pick(cols: Sequence[str], names: Sequence[str]) -> Optional[str]:
    available = set(cols)
    return next((name for name in names if name in available), None)


def qi(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        text = str(v).strip().replace("F", "").replace("L", "")
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def safe_int(v: Any) -> Optional[int]:
    try:
        return int(float(str(v).strip())) if v is not None else None
    except (TypeError, ValueError):
        return None


def st_bucket(v: Optional[float]) -> str:
    if v is None:
        return "ST_MISSING"
    if v < 0.00:
        return "ST<0.00"
    if v <= 0.03:
        return "0.00-0.03"
    if v <= 0.06:
        return "0.04-0.06"
    if v <= 0.09:
        return "0.07-0.09"
    if v <= 0.12:
        return "0.10-0.12"
    if v <= 0.15:
        return "0.13-0.15"
    if v <= 0.18:
        return "0.16-0.18"
    if v <= 0.22:
        return "0.19-0.22"
    return "0.23+"


ST_ORDER = [
    "ST<0.00", "0.00-0.03", "0.04-0.06", "0.07-0.09",
    "0.10-0.12", "0.13-0.15", "0.16-0.18", "0.19-0.22",
    "0.23+", "ST_MISSING",
]


def delta_bucket(v: Optional[float]) -> str:
    if v is None:
        return "DELTA_MISSING"
    if v <= -0.10:
        return "<=-0.10"
    if v <= -0.05:
        return "-0.09--0.05"
    if v <= -0.02:
        return "-0.04--0.02"
    if v < 0.02:
        return "-0.01-+0.01"
    if v < 0.05:
        return "+0.02-+0.04"
    if v < 0.10:
        return "+0.05-+0.09"
    return ">=+0.10"


@dataclass
class Schema:
    entry_race_id: str
    entry_lane: str
    entry_previous_st: str
    entry_class: Optional[str]
    entry_racer_id: Optional[str]
    race_date: str
    race_venue: str
    result_mode: str
    result_lane: Optional[str]
    result_finish: Optional[str]
    result_first: Optional[str]
    result_second: Optional[str]
    result_third: Optional[str]
    exhibition_lane: Optional[str]
    exhibition_st: Optional[str]


def detect_schema() -> Schema:
    for table in (ENTRY_TABLE, RESULT_TABLE, RACE_TABLE):
        if not table_exists(table):
            raise RuntimeError(f"必要テーブルがありません: {table}")

    ec = columns(ENTRY_TABLE)
    rc = columns(RESULT_TABLE)
    rac = columns(RACE_TABLE)
    xc = columns(EXHIBITION_TABLE) if table_exists(EXHIBITION_TABLE) else []

    entry_race_id = pick(ec, ["race_id"])
    entry_lane = pick(ec, ["lane", "course", "boat_no"])
    entry_previous_st = pick(ec, [
        "previous_st", "prev_st", "previous_start_timing",
        "prev_start_timing", "last_st", "previous_race_st", "prior_st",
    ])
    entry_class = pick(ec, ["racer_class", "class", "class_code", "grade", "racer_grade"])
    entry_racer_id = pick(ec, ["racer_id", "registration_no", "registration_number", "racer_no"])
    race_date = pick(rac, ["race_date", "target_date", "date"])
    race_venue = pick(rac, ["venue_id", "venue_code", "stadium_code", "place_code"])

    if not entry_race_id or not entry_lane or not entry_previous_st:
        raise RuntimeError(
            "v2_race_entries の必要列を特定できません。\n"
            f"columns={', '.join(ec)}"
        )
    if not race_date or not race_venue:
        raise RuntimeError(
            "v2_races の日付・場コード列を特定できません。\n"
            f"columns={', '.join(rac)}"
        )

    result_lane = pick(rc, ["lane", "course", "boat_no"])
    result_finish = pick(rc, ["finish_order", "rank", "arrival_order", "place", "result_rank"])

    if result_lane and result_finish:
        result_mode = "entrant_rows"
        result_first = result_second = result_third = None
    else:
        result_first = pick(rc, [
            "first_lane", "first", "winner_lane", "rank1_lane",
            "arrival_1", "result_1", "first_place",
        ])
        result_second = pick(rc, [
            "second_lane", "second", "rank2_lane",
            "arrival_2", "result_2", "second_place",
        ])
        result_third = pick(rc, [
            "third_lane", "third", "rank3_lane",
            "arrival_3", "result_3", "third_place",
        ])
        if not result_first:
            raise RuntimeError(
                "v2_results の着順列を特定できません。\n"
                f"columns={', '.join(rc)}"
            )
        result_mode = "race_row"

    return Schema(
        entry_race_id=entry_race_id,
        entry_lane=entry_lane,
        entry_previous_st=entry_previous_st,
        entry_class=entry_class,
        entry_racer_id=entry_racer_id,
        race_date=race_date,
        race_venue=race_venue,
        result_mode=result_mode,
        result_lane=result_lane,
        result_finish=result_finish,
        result_first=result_first,
        result_second=result_second,
        result_third=result_third,
        exhibition_lane=pick(xc, ["lane", "course", "boat_no"]) if xc else None,
        exhibition_st=pick(xc, ["start_timing", "exhibition_st", "tenji_st"]) if xc else None,
    )


def load_rows(s: Schema) -> List[Dict[str, Any]]:
    e_rid = f"e.{qi(s.entry_race_id)}"
    e_lane = f"e.{qi(s.entry_lane)}"
    e_prev = f"e.{qi(s.entry_previous_st)}"
    e_class = f"e.{qi(s.entry_class)}" if s.entry_class else "null"
    e_racer = f"e.{qi(s.entry_racer_id)}" if s.entry_racer_id else "null"
    r_date = f"ra.{qi(s.race_date)}"
    r_venue = f"ra.{qi(s.race_venue)}"

    exhibition_select = "null as exhibition_st"
    exhibition_join = ""
    if s.exhibition_lane and s.exhibition_st:
        x_lane = qi(s.exhibition_lane)
        x_st = qi(s.exhibition_st)
        exhibition_join = f"""
        left join (
            select race_id, {x_lane} as lane_key,
                   avg(nullif({x_st}::text, '')::numeric) as exhibition_st
            from {EXHIBITION_TABLE}
            group by race_id, {x_lane}
        ) x on x.race_id={e_rid} and x.lane_key::text={e_lane}::text
        """
        exhibition_select = "x.exhibition_st as exhibition_st"

    if s.result_mode == "entrant_rows":
        result_join = f"""
        join {RESULT_TABLE} rs
          on rs.race_id={e_rid}
         and rs.{qi(s.result_lane or '')}::text={e_lane}::text
        """
        finish_expr = f"rs.{qi(s.result_finish or '')}"
    else:
        parts = [f"when rs.{qi(s.result_first or '')}::text={e_lane}::text then 1"]
        if s.result_second:
            parts.append(f"when rs.{qi(s.result_second)}::text={e_lane}::text then 2")
        if s.result_third:
            parts.append(f"when rs.{qi(s.result_third)}::text={e_lane}::text then 3")
        finish_expr = "case " + " ".join(parts) + " else 6 end"
        result_join = f"join {RESULT_TABLE} rs on rs.race_id={e_rid}"

    sql = f"""
    select
        {e_rid} as race_id,
        {r_date} as race_date,
        {r_venue} as venue_id,
        {e_lane} as lane,
        {e_prev} as previous_st,
        {e_class} as racer_class,
        {e_racer} as racer_id,
        {exhibition_select},
        {finish_expr} as finish_order
    from {ENTRY_TABLE} e
    join {RACE_TABLE} ra on ra.race_id={e_rid}
    {result_join}
    {exhibition_join}
    where {r_date} >= %s and {r_date} <= %s
    order by {r_date}, {e_rid}, {e_lane};
    """
    return fetch_all(sql, (START_DATE, END_DATE))


@dataclass
class Agg:
    n: int = 0
    wins: int = 0
    top2: int = 0
    top3: int = 0
    finish_sum: float = 0.0

    def add(self, finish: int) -> None:
        self.n += 1
        self.wins += int(finish == 1)
        self.top2 += int(finish <= 2)
        self.top3 += int(finish <= 3)
        self.finish_sum += finish

    @property
    def win_pct(self) -> float:
        return self.wins / self.n * 100 if self.n else 0.0

    @property
    def top2_pct(self) -> float:
        return self.top2 / self.n * 100 if self.n else 0.0

    @property
    def top3_pct(self) -> float:
        return self.top3 / self.n * 100 if self.n else 0.0

    @property
    def avg_finish(self) -> float:
        return self.finish_sum / self.n if self.n else 999.0


def norm_class(v: Any) -> str:
    if v is None:
        return "CLASS_MISSING"
    text = str(v).strip().upper()
    return {"1": "A1", "2": "A2", "3": "B1", "4": "B2"}.get(
        text, text or "CLASS_MISSING"
    )


def print_agg(label: str, a: Agg, baseline: Optional[Agg] = None) -> None:
    lift = ""
    if baseline and baseline.n:
        lift = f" top3_lift={a.top3_pct - baseline.top3_pct:+.2f}pt"
    print(
        f"{label}: n={a.n} avg_finish={a.avg_finish:.3f} "
        f"win={a.win_pct:.2f}% top2={a.top2_pct:.2f}% "
        f"top3={a.top3_pct:.2f}%{lift}",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ feature_lab_previous_st_detail_pg.py VERSION 2026-07-20 st-detail-v1", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        f"MIN_SAMPLES={MIN_SAMPLES} MIN_LIFT_PT={MIN_LIFT_PT:.2f} TOP_N={TOP_N}",
        flush=True,
    )
    print("読み取り専用です。本番判定・LINE通知・購入処理・DB更新は行いません。", flush=True)

    s = detect_schema()
    print(
        "schema: "
        f"previous_st={s.entry_previous_st} lane={s.entry_lane} "
        f"class={s.entry_class or 'NONE'} result_mode={s.result_mode} "
        f"exhibition_st={s.exhibition_st or 'NONE'}",
        flush=True,
    )

    rows = load_rows(s)
    print(f"loaded_entry_rows={len(rows)}", flush=True)

    overall = Agg()
    lane_base: Dict[str, Agg] = defaultdict(Agg)
    class_base: Dict[str, Agg] = defaultdict(Agg)
    venue_base: Dict[str, Agg] = defaultdict(Agg)
    by_st: Dict[str, Agg] = defaultdict(Agg)
    by_lane_st: Dict[Tuple[str, str], Agg] = defaultdict(Agg)
    by_class_st: Dict[Tuple[str, str], Agg] = defaultdict(Agg)
    by_venue_st: Dict[Tuple[str, str], Agg] = defaultdict(Agg)
    by_delta: Dict[str, Agg] = defaultdict(Agg)
    by_lane_delta: Dict[Tuple[str, str], Agg] = defaultdict(Agg)

    valid_rows = st_present = ex_present = 0
    race_ids = set()

    for row in rows:
        finish = safe_int(row.get("finish_order"))
        lane = safe_int(row.get("lane"))
        if finish is None or lane is None or not (1 <= lane <= 6) or not (1 <= finish <= 6):
            continue

        valid_rows += 1
        race_ids.add(str(row.get("race_id")))
        lane_key = str(lane)
        venue = str(row.get("venue_id") or "").zfill(2)
        cls = norm_class(row.get("racer_class"))
        pst = safe_float(row.get("previous_st"))
        est = safe_float(row.get("exhibition_st"))
        st_present += int(pst is not None)
        ex_present += int(est is not None)
        sb = st_bucket(pst)

        overall.add(finish)
        lane_base[lane_key].add(finish)
        class_base[cls].add(finish)
        venue_base[venue].add(finish)
        by_st[sb].add(finish)
        by_lane_st[(lane_key, sb)].add(finish)
        by_class_st[(cls, sb)].add(finish)
        by_venue_st[(venue, sb)].add(finish)

        if pst is not None and est is not None:
            db = delta_bucket(est - pst)
            by_delta[db].add(finish)
            by_lane_delta[(lane_key, db)].add(finish)

    print(
        f"valid_entry_rows={valid_rows} distinct_races={len(race_ids)} "
        f"previous_st_coverage={st_present}/{valid_rows} "
        f"({st_present / valid_rows * 100 if valid_rows else 0:.1f}%) "
        f"exhibition_st_coverage={ex_present}/{valid_rows} "
        f"({ex_present / valid_rows * 100 if valid_rows else 0:.1f}%)",
        flush=True,
    )

    print("\n=== OVERALL ===", flush=True)
    print_agg("ALL", overall)

    print("\n=== PREVIOUS ST BUCKET ===", flush=True)
    for sb in ST_ORDER:
        if sb in by_st:
            print_agg(sb, by_st[sb], overall)

    print("\n=== LANE x PREVIOUS ST ===", flush=True)
    for lane in map(str, range(1, 7)):
        print(f"-- lane={lane} baseline --", flush=True)
        print_agg(f"lane={lane}", lane_base[lane])
        for sb in ST_ORDER:
            a = by_lane_st.get((lane, sb))
            if a and a.n >= MIN_SAMPLES:
                print_agg(f"lane={lane} st={sb}", a, lane_base[lane])

    print("\n=== CLASS x PREVIOUS ST ===", flush=True)
    for cls in sorted(class_base):
        if class_base[cls].n < MIN_SAMPLES:
            continue
        print(f"-- class={cls} baseline --", flush=True)
        print_agg(f"class={cls}", class_base[cls])
        for sb in ST_ORDER:
            a = by_class_st.get((cls, sb))
            if a and a.n >= MIN_SAMPLES:
                print_agg(f"class={cls} st={sb}", a, class_base[cls])

    print("\n=== VENUE x PREVIOUS ST: CANDIDATES ===", flush=True)
    candidates = []
    for (venue, sb), a in by_venue_st.items():
        base = venue_base[venue]
        if a.n >= MIN_SAMPLES and base.n:
            candidates.append((a.top3_pct - base.top3_pct, a.n, venue, sb, a, base))
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    shown = 0
    for lift, _, venue, sb, a, base in candidates:
        if lift < MIN_LIFT_PT:
            continue
        print_agg(f"venue={venue} st={sb}", a, base)
        shown += 1
        if shown >= TOP_N:
            break
    if shown == 0:
        print("採用候補なし（現在の基準）", flush=True)

    print("\n=== EXHIBITION ST - PREVIOUS ST ===", flush=True)
    delta_order = [
        "<=-0.10", "-0.09--0.05", "-0.04--0.02", "-0.01-+0.01",
        "+0.02-+0.04", "+0.05-+0.09", ">=+0.10",
    ]
    if by_delta:
        for db in delta_order:
            if db in by_delta:
                print_agg(f"delta={db}", by_delta[db], overall)

        print("\n=== LANE x ST DELTA ===", flush=True)
        for lane in map(str, range(1, 7)):
            for db in delta_order:
                a = by_lane_delta.get((lane, db))
                if a and a.n >= MIN_SAMPLES:
                    print_agg(f"lane={lane} delta={db}", a, lane_base[lane])
    else:
        print("展示STとの比較データなし。", flush=True)

    print("\n=== DISCOVERY CANDIDATES: LANE/CLASS ===", flush=True)
    discovery = []
    for (lane, sb), a in by_lane_st.items():
        base = lane_base[lane]
        if a.n >= MIN_SAMPLES and base.n:
            discovery.append((a.top3_pct - base.top3_pct, a.n, f"lane={lane} st={sb}", a, base))
    for (cls, sb), a in by_class_st.items():
        base = class_base[cls]
        if a.n >= MIN_SAMPLES and base.n:
            discovery.append((a.top3_pct - base.top3_pct, a.n, f"class={cls} st={sb}", a, base))
    discovery.sort(key=lambda x: (x[0], x[1]), reverse=True)

    shown = 0
    for lift, _, label, a, base in discovery:
        if lift < MIN_LIFT_PT:
            continue
        print_agg(label, a, base)
        shown += 1
        if shown >= TOP_N:
            break
    if shown == 0:
        print("採用候補なし（現在の基準）", flush=True)

    print("\n判定上の注意:", flush=True)
    print("- これは特徴量探索であり、本番採用判定ではありません。", flush=True)
    print("- 有望条件は別期間（例: 4月）で再検証してから補正値を決めます。", flush=True)
    print("- 場別は多重比較になるため、少数件の高liftをそのまま採用しません。", flush=True)
    print("=== previous ST detail lab finished ===", flush=True)


if __name__ == "__main__":
    main()