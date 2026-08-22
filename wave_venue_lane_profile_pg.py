# -*- coding: utf-8 -*-
"""Fixed train-only-stable wave x venue x lane profile loader.

The SQL is exactly equivalent to the validated Python reference from PR #71,
as proven by the read-only SQL equivalence audit in PR #73.
"""
from __future__ import annotations

from datetime import date
from db_pg import fetch_all

PROFILE_VERSION = "wave-vl-stable-v1-20260531"
START_DATE = date(2025, 7, 1)
INTERNAL_SPLIT = date(2026, 2, 28)
TRAIN_END = date(2026, 5, 31)

PROFILE_SQL = r"""
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


def wave_bucket(value) -> str:
    x = float(value)
    if x < 3:
        return "<3"
    if x < 6:
        return "3-<6"
    if x < 10:
        return "6-<10"
    return "10+"


def load_profile() -> dict[tuple[str, int, str], dict]:
    rows = fetch_all(PROFILE_SQL, (INTERNAL_SPLIT, START_DATE, TRAIN_END))
    out = {}
    for r in rows:
        key = (str(r["venue"]).zfill(2), int(r["lane"]), str(r["bucket"]))
        out[key] = {
            "n": int(r["n"]),
            "base_n": int(r["base_n"]),
            "delta_logit": float(r["delta_logit"]),
        }
    return out
