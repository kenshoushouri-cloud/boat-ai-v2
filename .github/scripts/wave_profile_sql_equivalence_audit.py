# -*- coding: utf-8 -*-
"""Read-only equivalence/performance audit for the gated wave profile.

Compares the already-validated Python reference implementation with one
PostgreSQL aggregation query suitable for realtime Shadow use.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wave_bt = load_module("wave_bt_eq", ROOT / ".github/scripts/wave_venue_lane_shadow_backtest.py")
wave_gate = load_module("wave_gate_eq", ROOT / ".github/scripts/wave_train_stability_gate_backtest.py")
from db_pg import fetch_all

SQL = r"""
with base as (
  select lpad(r.venue_id::text,2,'0') venue,
         e.lane,
         case when w.wave_height_cm < 3 then '<3'
              when w.wave_height_cm < 6 then '3-<6'
              when w.wave_height_cm < 10 then '6-<10'
              else '10+' end bucket,
         case when re.finish_position=1 then 1.0 else 0.0 end win,
         case when r.race_date <= %s then 'early' else 'late' end phase
  from v2_races r
  join v2_race_entries e on e.race_id=r.race_id
  join v2_result_entries re
    on re.race_id=e.race_id and re.lane=e.lane and re.racer_number=e.racer_number
  join v2_realtime_weather_snapshots w
    on w.race_id=r.race_id and w.snapshot_label='historical'
  where r.race_date >= %s and r.race_date <= %s
    and re.finish_position between 1 and 6
    and w.wave_height_cm is not null
),
phase_bucket as (
  select venue,lane,bucket,phase,count(*)::bigint n,sum(win)::float8 wins
  from base group by venue,lane,bucket,phase
),
phase_base as (
  select venue,lane,phase,count(*)::bigint n,sum(win)::float8 wins
  from base group by venue,lane,phase
),
phase_effect as (
  select b.venue,b.lane,b.bucket,b.phase,b.n,bb.n base_n,
         (
           ln(((b.wins+0.5)/(b.n+1.0)) / (1.0-((b.wins+0.5)/(b.n+1.0))))
           -
           ln(((bb.wins+0.5)/(bb.n+1.0)) / (1.0-((bb.wins+0.5)/(bb.n+1.0))))
         ) * (b.n::float8/(b.n+25.0)) delta_logit
  from phase_bucket b
  join phase_base bb using(venue,lane,phase)
  where b.n >= 15 and bb.n >= 50
),
stable as (
  select e.venue,e.lane,e.bucket
  from phase_effect e
  join phase_effect l using(venue,lane,bucket)
  where e.phase='early' and l.phase='late'
    and abs(e.delta_logit) >= 0.05
    and abs(l.delta_logit) >= 0.05
    and e.delta_logit*l.delta_logit > 0
),
full_bucket as (
  select venue,lane,bucket,count(*)::bigint n,sum(win)::float8 wins
  from base group by venue,lane,bucket
),
full_base as (
  select venue,lane,count(*)::bigint n,sum(win)::float8 wins
  from base group by venue,lane
)
select f.venue,f.lane,f.bucket,f.n,b.n base_n,
       (
         ln(((f.wins+0.5)/(f.n+1.0)) / (1.0-((f.wins+0.5)/(f.n+1.0))))
         -
         ln(((b.wins+0.5)/(b.n+1.0)) / (1.0-((b.wins+0.5)/(b.n+1.0))))
       ) * (f.n::float8/(f.n+50.0)) delta_logit
from full_bucket f
join full_base b using(venue,lane)
join stable s using(venue,lane,bucket)
where f.n >= 30 and b.n >= 100
order by f.venue,f.lane,f.bucket
"""


def python_reference():
    early = wave_bt.load_rows(wave_gate.START_DATE, wave_gate.INTERNAL_SPLIT)
    late = wave_bt.load_rows(wave_gate.next_day(wave_gate.INTERNAL_SPLIT), wave_gate.TRAIN_END)
    full = wave_bt.load_rows(wave_gate.START_DATE, wave_gate.TRAIN_END)
    e1 = wave_gate.half_effects(early)
    e2 = wave_gate.half_effects(late)
    stable = {k for k in set(e1) & set(e2) if e1[k]["delta_logit"] * e2[k]["delta_logit"] > 0}
    profile = wave_bt.build_profile(full)
    return {k:v for k,v in profile.items() if k in stable}


def sql_profile():
    rows = fetch_all(SQL, (wave_gate.INTERNAL_SPLIT, wave_gate.START_DATE, wave_gate.TRAIN_END))
    out = {}
    for r in rows:
        key = (str(r["venue"]).zfill(2), int(r["lane"]), str(r["bucket"]))
        out[key] = {
            "n": int(r["n"]),
            "base_n": int(r["base_n"]),
            "delta_logit": float(r["delta_logit"]),
        }
    return out


def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")
    print("WAVE_SQL_EQ_MODE=read_only", flush=True)
    print("WAVE_SQL_EQ_POLICY=no_writes_no_schema_no_prediction_no_line", flush=True)

    t0 = time.perf_counter()
    py = python_reference()
    py_sec = time.perf_counter() - t0
    t1 = time.perf_counter()
    sq = sql_profile()
    sql_sec = time.perf_counter() - t1

    py_keys = set(py)
    sql_keys = set(sq)
    missing_sql = py_keys - sql_keys
    extra_sql = sql_keys - py_keys
    common = py_keys & sql_keys
    max_delta = max((abs(float(py[k]["delta_logit"]) - float(sq[k]["delta_logit"])) for k in common), default=0.0)
    count_mismatch = sum(1 for k in common if int(py[k]["n"]) != int(sq[k]["n"]) or int(py[k]["base_n"]) != int(sq[k]["base_n"]))

    print(f"WAVE_SQL_EQ_PY_GROUPS={len(py)}", flush=True)
    print(f"WAVE_SQL_EQ_SQL_GROUPS={len(sq)}", flush=True)
    print(f"WAVE_SQL_EQ_MISSING_SQL={len(missing_sql)}", flush=True)
    print(f"WAVE_SQL_EQ_EXTRA_SQL={len(extra_sql)}", flush=True)
    print(f"WAVE_SQL_EQ_COUNT_MISMATCH={count_mismatch}", flush=True)
    print(f"WAVE_SQL_EQ_MAX_DELTA_LOGIT_DIFF={max_delta:.12g}", flush=True)
    print(f"WAVE_SQL_EQ_PY_SECONDS={py_sec:.3f}", flush=True)
    print(f"WAVE_SQL_EQ_SQL_SECONDS={sql_sec:.3f}", flush=True)

    ok = not missing_sql and not extra_sql and count_mismatch == 0 and max_delta <= 1e-9
    print(f"WAVE_SQL_EQ_RESULT={'PASS_EXACT' if ok else 'FAIL'}", flush=True)
    if not ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
