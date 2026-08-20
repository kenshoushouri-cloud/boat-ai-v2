# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb
from db_pg import execute, fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-20 v24-motor2-forward-shadow-v1.4-pre-final-dual-scope"
JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SESSION = os.getenv("MOTOR2_SHADOW_SESSION", "all").strip().lower()
RUN_CLASS = os.getenv("MOTOR2_SHADOW_RUN_CLASS", "manual").strip().lower()
WINDOW_NAME = os.getenv("WINDOW_NAME", "manual").strip().lower()
SNAPSHOT_KEY = (os.getenv("MOTOR2_SHADOW_SNAPSHOT_KEY") or datetime.now(JST).strftime("%Y%m%d%H%M%S")).strip()


def sf(v, d=None):
    try: return float(v) if v not in (None, "") else d
    except Exception: return d


def si(v, d=0):
    try: return int(float(v)) if v not in (None, "") else d
    except Exception: return d


def valid_motor2(v):
    x = sf(v, None)
    return x if x is not None and 0 <= x <= 100 else 33.0


def next_day(date_str):
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def _parse_ids(raw: str) -> set[str]:
    raw = (raw or "").strip()
    if not raw:
        return set()
    return {x.strip() for x in re.split(r"[,\s]+", raw) if x.strip()}


WINDOW_TARGET_IDS = _parse_ids(os.getenv("MOTOR2_SHADOW_TARGET_RACE_IDS") or "")
COLLECTION_TARGET_IDS = _parse_ids(
    os.getenv("MOTOR2_SHADOW_COLLECTION_RACE_IDS")
    or os.getenv("COLLECTION_RACE_IDS")
    or ""
)

if COLLECTION_TARGET_IDS:
    TARGET_RACE_IDS = COLLECTION_TARGET_IDS
    TARGET_SCOPE = "collection_ids"
elif WINDOW_TARGET_IDS:
    TARGET_RACE_IDS = WINDOW_TARGET_IDS
    TARGET_SCOPE = "window_ids"
else:
    TARGET_RACE_IDS = set()
    TARGET_SCOPE = "all_day"


def fetch_entries_with_motor2(date_str):
    a = date_str.replace("-", "")
    b = next_day(date_str).replace("-", "")
    rows = fetch_all(
        """
        select race_id,lane,racer_number,racer_class,racer_name,
               national_win_rate,national_place2_rate,
               local_win_rate,local_place2_rate,
               motor_no,boat_no,avg_st,motor_place2_rate
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id,lane
        """,
        (a, b),
    )
    out = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid:
            out.setdefault(rid, []).append(row)
    return out


def ensure_table():
    execute("""create table if not exists v2_v24_motor2_forward_shadow(
      id bigserial primary key,race_id text not null,race_date date not null,venue_id text,race_no integer,ticket text not null,
      odds numeric,market_rank integer,
      base_prob numeric,base_prob_rank integer,base_raw_ev numeric,
      motor2_prob numeric,motor2_prob_rank integer,motor2_raw_ev numeric,
      base_low_candidate boolean not null default false,motor2_low_candidate boolean not null default false,
      base_mid_candidate boolean not null default false,motor2_mid_candidate boolean not null default false,
      candidate_transition text,base_near_boundary boolean not null default false,motor2_near_boundary boolean not null default false,
      motor2_valid_lanes integer,motor2_fallback_lanes integer,
      run_class text not null default 'manual',window_name text not null default 'manual',session_scope text not null default 'all',
      snapshot_key text not null default '',snapshot_at timestamptz not null default now(),
      result_ticket text,payout_yen integer,base_hit boolean,motor2_hit boolean,evaluated_at timestamptz,
      raw jsonb,created_at timestamptz not null default now(),updated_at timestamptz not null default now()
    )""")
    execute("create unique index if not exists uq_v24_motor2_forward_run on v2_v24_motor2_forward_shadow(race_id,ticket,run_class,window_name,snapshot_key)")


def raw_strength(e, lane, venue, use_motor):
    cls = si(e.get("racer_class"), 2); cw = v24.CLASS_WEIGHT.get(cls, .55)
    wr = sf(e.get("national_win_rate"), 0) or 0
    n2 = sf(e.get("national_place2_rate"), 32); n2 = 32 if n2 is None else n2
    l2 = sf(e.get("local_place2_rate"), 30); l2 = 30 if l2 is None else l2
    st = sf(e.get("avg_st"), .18); st = .18 if st is None else st
    m2 = valid_motor2(e.get("motor_place2_rate")) if use_motor else 33.0
    cb = v24.VENUE_COURSE_BIAS.get(venue, v24.DEFAULT_COURSE_BIAS).get(lane, v24.DEFAULT_COURSE_BIAS[lane])
    ss = max(0, min(1, (.24 - st) / .12))
    return cw + wr*.16 + (n2/100)*.90 + (l2/100)*.55 + (m2/100)*.45 + (34/100)*.25 + ss*.35 + cb*.22


def probs(entries, venue, use_motor):
    by = v24._entry_by_lane(entries)
    r = {i: raw_strength(by[i], i, venue, use_motor) for i in range(1, 7)}
    w = {i: math.exp(r[i] / v24.PROB_TEMP) for i in range(1, 7)}
    total = sum(w.values()); out = {}
    for a in range(1, 7):
        pa = w[a] / total; tb = total - w[a]
        for b in range(1, 7):
            if b == a: continue
            pb = w[b] / tb; tc = tb - w[b]
            for c in range(1, 7):
                if c in (a, b): continue
                out[f"{a}-{b}-{c}"] = pa * pb * (w[c] / tc)
    return out


def ranks(p): return {t:i for i,(t,_) in enumerate(sorted(p.items(), key=lambda kv:(-kv[1],kv[0])),1)}
def market_ranks(odds): return {t:i for i,(t,_) in enumerate(sorted(odds.items(), key=lambda kv:(kv[1],kv[0])),1)}
def is_low(pr,mr,odd): return 11 <= pr <= 20 and mr == 1 and 3 <= odd < 5
def is_mid(t,pr,mr,odd): return 4 <= pr <= 5 and 21 <= mr <= 30 and 30 <= odd < 50 and v24._head_lane(t) != "1"
def near(pr): return 3 <= pr <= 6 or 10 <= pr <= 21
def trans(b,m): return "BOTH" if b and m else "BASE_ONLY" if b else "MOTOR2_ONLY" if m else "NEITHER"


def session_match(r):
    if SESSION == "all": return True
    venue = str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
    meta = v24._metadata_text(r); sess = v24._infer_session_type(r)
    night = v24._is_night_like_session(sess, venue, meta)
    return night if SESSION == "night" else not night


def save(row):
    execute("""insert into v2_v24_motor2_forward_shadow(
      race_id,race_date,venue_id,race_no,ticket,odds,market_rank,
      base_prob,base_prob_rank,base_raw_ev,motor2_prob,motor2_prob_rank,motor2_raw_ev,
      base_low_candidate,motor2_low_candidate,base_mid_candidate,motor2_mid_candidate,candidate_transition,
      base_near_boundary,motor2_near_boundary,motor2_valid_lanes,motor2_fallback_lanes,
      run_class,window_name,session_scope,snapshot_key,snapshot_at,raw,updated_at)
      values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s,now())
      on conflict(race_id,ticket,run_class,window_name,snapshot_key) do update set
      odds=excluded.odds,market_rank=excluded.market_rank,base_prob=excluded.base_prob,base_prob_rank=excluded.base_prob_rank,
      base_raw_ev=excluded.base_raw_ev,motor2_prob=excluded.motor2_prob,motor2_prob_rank=excluded.motor2_prob_rank,
      motor2_raw_ev=excluded.motor2_raw_ev,base_low_candidate=excluded.base_low_candidate,motor2_low_candidate=excluded.motor2_low_candidate,
      base_mid_candidate=excluded.base_mid_candidate,motor2_mid_candidate=excluded.motor2_mid_candidate,
      candidate_transition=excluded.candidate_transition,base_near_boundary=excluded.base_near_boundary,motor2_near_boundary=excluded.motor2_near_boundary,
      motor2_valid_lanes=excluded.motor2_valid_lanes,motor2_fallback_lanes=excluded.motor2_fallback_lanes,
      session_scope=excluded.session_scope,snapshot_at=excluded.snapshot_at,raw=excluded.raw,updated_at=now()""",
      (row["race_id"],row["race_date"],row["venue_id"],row["race_no"],row["ticket"],row["odds"],row["market_rank"],
       row["base_prob"],row["base_prob_rank"],row["base_raw_ev"],row["motor2_prob"],row["motor2_prob_rank"],row["motor2_raw_ev"],
       row["base_low_candidate"],row["motor2_low_candidate"],row["base_mid_candidate"],row["motor2_mid_candidate"],row["candidate_transition"],
       row["base_near_boundary"],row["motor2_near_boundary"],row["motor2_valid_lanes"],row["motor2_fallback_lanes"],
       RUN_CLASS,WINDOW_NAME,SESSION,SNAPSHOT_KEY,Jsonb(row["raw"])))


def main():
    if not os.getenv("DATABASE_URL"): raise RuntimeError("DATABASE_URL is required")
    if SESSION not in {"all","day","night"}: raise RuntimeError(f"invalid session={SESSION}")
    if RUN_CLASS not in {"live","manual","test","final"}: raise RuntimeError(f"invalid run_class={RUN_CLASS}")

    print(f"OK collect_v24_motor2_forward_shadow_pg.py VERSION {VERSION}", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} SESSION={SESSION} RUN_CLASS={RUN_CLASS} WINDOW_NAME={WINDOW_NAME} SNAPSHOT_KEY={SNAPSHOT_KEY}", flush=True)
    print("SHADOW_ONLY=1 LINE=0 BUY=0 PROD_V24_CHANGE=0 N02_CHANGE=0", flush=True)
    print(f"TARGET_SCOPE={TARGET_SCOPE} target_ids={len(TARGET_RACE_IDS)}", flush=True)

    ensure_table()
    races, _e, ob = v24._fetch_live_day_rows(TARGET_DATE)
    eb = fetch_entries_with_motor2(TARGET_DATE)

    if TARGET_RACE_IDS:
        races = [r for r in races if str(r.get("race_id") or "") in TARGET_RACE_IDS]

    races = [r for r in races if session_match(r)]
    if not races:
        print("races=0", flush=True); print("RESULT=NO_RACES", flush=True); return

    print(f"ENTRY_SOURCE=direct_v2_race_entries_with_motor2 entry_races={len(eb)} entry_rows={sum(len(v) for v in eb.values())}", flush=True)

    saved=ready=skip_e=skip_o=skip_sparse=0
    tb=tm=mb=mm=0
    trc={"BOTH":0,"BASE_ONLY":0,"MOTOR2_ONLY":0,"NEITHER":0}
    valid_total=fallback_total=0

    for race in races:
        rid=str(race.get("race_id") or "")
        venue=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        rno=si(race.get("race_no"),0); ent=eb.get(rid,[]); odds=ob.get(rid,{})
        by=v24._entry_by_lane(ent)
        if len(by)!=6: skip_e+=1; continue
        ok,_=v24._validate_odds_snapshot(odds)
        if not ok: skip_o+=1; continue

        ready+=1
        bp=probs(ent,venue,False); mp=probs(ent,venue,True)
        br=ranks(bp); mr=ranks(mp); mar=market_ranks(odds)
        vl=fl=0
        for lane in range(1,7):
            x=sf(by[lane].get("motor_place2_rate"),None)
            if x is not None and 0<=x<=100: vl+=1
            else: fl+=1
        valid_total+=vl; fallback_total+=fl

        for t,odd in odds.items():
            if t not in bp or t not in mp: continue
            odd=float(odd); bpr=br[t]; mpr=mr[t]; mkr=mar[t]
            bl=is_low(bpr,mkr,odd); ml=is_low(mpr,mkr,odd)
            bmi=is_mid(t,bpr,mkr,odd); mmi=is_mid(t,mpr,mkr,odd)
            bc=bl or bmi; mc=ml or mmi; tr=trans(bc,mc)
            bn=near(bpr); mn=near(mpr)
            if not (bc or mc or bn or mn): skip_sparse+=1; continue

            trc[tr]+=1; tb+=int(bl); tm+=int(ml); mb+=int(bmi); mm+=int(mmi)
            save(dict(
                race_id=rid,race_date=TARGET_DATE,venue_id=venue,race_no=rno,ticket=t,odds=odd,market_rank=mkr,
                base_prob=bp[t],base_prob_rank=bpr,base_raw_ev=bp[t]*odd,
                motor2_prob=mp[t],motor2_prob_rank=mpr,motor2_raw_ev=mp[t]*odd,
                base_low_candidate=bl,motor2_low_candidate=ml,base_mid_candidate=bmi,motor2_mid_candidate=mmi,
                candidate_transition=tr,base_near_boundary=bn,motor2_near_boundary=mn,
                motor2_valid_lanes=vl,motor2_fallback_lanes=fl,
                raw={"version":VERSION,"save_policy":"candidate_or_prob_rank_boundary","motor2_weight":0.45,
                     "entry_source":"direct_v2_race_entries_with_motor2","target_scope":TARGET_SCOPE}
            ))
            saved+=1

    print("=== MOTOR2 FORWARD SHADOW SUMMARY ===", flush=True)
    print(f"races={len(races)} ready={ready} saved={saved} skipped_sparse={skip_sparse}", flush=True)
    print(f"skipped_entries={skip_e} skipped_odds={skip_o}", flush=True)
    print(f"LOW BASE={tb} MOTOR2={tm}", flush=True)
    print(f"MID BASE={mb} MOTOR2={mm}", flush=True)
    print(f"TRANSITIONS BOTH={trc['BOTH']} BASE_ONLY={trc['BASE_ONLY']} MOTOR2_ONLY={trc['MOTOR2_ONLY']} NEITHER={trc['NEITHER']}", flush=True)
    print(f"MOTOR_DATA valid_lane_total={valid_total} fallback_lane_total={fallback_total}", flush=True)
    print(f"RUN_CLASS={RUN_CLASS} WINDOW_NAME={WINDOW_NAME} SNAPSHOT_KEY={SNAPSHOT_KEY}", flush=True)
    print("RESULT=PASS", flush=True)


if __name__=="__main__":
    main()