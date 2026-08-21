# -*- coding: utf-8 -*-
"""Railway Postgres realtime collector with deadline window filter."""
from __future__ import annotations
import os,re,time,unicodedata
from collections import defaultdict
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import requests
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup=None
from db_pg import execute,fetch_all,upsert_rows

JST=timezone(timedelta(hours=9))
TARGET_DATE=os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
TARGET_RACE_ID=os.getenv("TARGET_RACE_ID","").strip()
SNAPSHOT_LABEL=os.getenv("SNAPSHOT_LABEL","manual").strip() or "manual"
COLLECT_SCOPE=os.getenv("COLLECT_SCOPE","candidates").strip().lower()
TARGET_ID_SCOPE=os.getenv("TARGET_ID_SCOPE","same").strip().lower()
TARGET_VENUES=[v.strip().zfill(2) for v in os.getenv("TARGET_VENUES",",".join(f"{i:02d}" for i in range(1,25))).split(",") if v.strip()]
REALTIME_SLEEP_SEC=float(os.getenv("REALTIME_SLEEP_SEC","0.15"))
PARSE_ALLOW_PARTIAL=os.getenv("PARSE_ALLOW_PARTIAL","0").strip() in ("1","true","True","yes","YES")
FINAL_DEADLINE_FILTER=os.getenv("FINAL_DEADLINE_FILTER","1").strip() not in ("0","false","False","no","NO")
FINAL_WINDOW_BEFORE_MIN=max(0,int(os.getenv("FINAL_WINDOW_BEFORE_MIN","30")))
FINAL_WINDOW_AFTER_MIN=max(0,int(os.getenv("FINAL_WINDOW_AFTER_MIN","0")))
TARGET_RACE_IDS_FILE=os.getenv("TARGET_RACE_IDS_FILE","/tmp/v21_target_race_ids.txt").strip() or "/tmp/v21_target_race_ids.txt"
COLLECTION_RACE_IDS_FILE=os.getenv("COLLECTION_RACE_IDS_FILE","/tmp/v21_collection_race_ids.txt").strip() or "/tmp/v21_collection_race_ids.txt"
HTTP_TIMEOUT=int(os.getenv("HTTP_TIMEOUT","35")); RETRY_MAX=int(os.getenv("RETRY_MAX","2")); RETRY_SLEEP=float(os.getenv("RETRY_SLEEP","2.0"))
BAD5_VENUES={"01","04","05","06","23"}; IN_STRONG_VENUES={"12","15","18","21","24"}; ROUGH_VENUES={"02","03","04","05","06"}
OFFICIAL="https://www.boatrace.jp/owpc/pc/race"
SESSION=requests.Session(); SESSION.headers.update({"User-Agent":"Mozilla/5.0 (compatible; boatrace-realtime-collector-pg/1.0)"})

def _require_settings():
    if not os.getenv("DATABASE_URL"): raise RuntimeError("DATABASE_URL が必要です。")
def _now(): return datetime.now(JST)
def _now_iso(): return _now().isoformat()
def _yyyymmdd(s): return s.replace("-","")
def _rid_prefix(s): return s.replace("-","")
def _next_day(s): return (datetime.strptime(s,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y-%m-%d")
def _shift_day(s,n): return (datetime.strptime(s,"%Y-%m-%d")+timedelta(days=n)).strftime("%Y-%m-%d")
def _norm_text(s): return re.sub(r"\s+"," ",str(s or "")).strip()
def _norm_ticket(s):
    text=unicodedata.normalize("NFKC",str(s or "")).strip()
    m=re.fullmatch(r"\s*([1-6])\s*[-－]\s*([1-6])\s*[-－]\s*([1-6])\s*",text)
    if not m:return ""
    a,b,c=m.groups()
    return f"{a}-{b}-{c}" if len({a,b,c})==3 else ""
def _safe_int(v,d=0):
    try:return int(float(str(v).replace(",",""))) if v not in (None,"") else d
    except:return d
def _safe_float(v,d=0.0):
    try:
        if v in (None,""):return d
        s=str(v).replace(",","").replace("F","").replace("L","").strip()
        if s.startswith("."):s="0"+s
        if s.startswith("-."):s=s.replace("-.","-0.",1)
        return float(s)
    except:return d
def _official_url(kind,date_str,venue_id,race_no):return f"{OFFICIAL}/{kind}?rno={int(race_no)}&jcd={venue_id.zfill(2)}&hd={_yyyymmdd(date_str)}"
def _fetch(url):
    last=None
    for _ in range(RETRY_MAX+1):
        try:
            r=SESSION.get(url,timeout=HTTP_TIMEOUT)
            if r.status_code==404:return None
            if not r.ok:last=f"HTTP {r.status_code}: {r.text[:120]}";time.sleep(RETRY_SLEEP);continue
            r.encoding=r.apparent_encoding or "utf-8";return r.text
        except Exception as e:last=repr(e);time.sleep(RETRY_SLEEP)
    print(f"⚠️ fetch failed: {url} / {last}",flush=True);return None
def _looks_no_data(html):
    if not html:return True
    t=_norm_text(re.sub(r"<[^>]+>"," ",html))
    return "データがありません" in t or "開催はありません" in t or "該当するデータはありません" in t or ("オッズの更新" in t and len(t)<500)
def _parse_deadline_at(r):
    raw=r.get("deadline_at")
    if isinstance(raw,datetime):
        dt=raw if raw.tzinfo else raw.replace(tzinfo=JST);return dt.astimezone(JST)
    if raw:
        try:
            dt=datetime.fromisoformat(str(raw).replace("Z","+00:00"));dt=dt if dt.tzinfo else dt.replace(tzinfo=JST);return dt.astimezone(JST)
        except:pass
    tm=str(r.get("deadline_time") or "").strip();rd=r.get("race_date")
    if tm and rd:
        try:
            d=rd.date() if isinstance(rd,datetime) else rd if isinstance(rd,date) else datetime.strptime(str(rd)[:10],"%Y-%m-%d").date()
            h,m=map(int,tm.split(":")[:2]);return datetime(d.year,d.month,d.day,h,m,tzinfo=JST)
        except:return None
    return None
def _deadline_match(r,now):
    dl=_parse_deadline_at(r)
    if dl is None:return False,"deadline_missing"
    if now<dl-timedelta(minutes=FINAL_WINDOW_BEFORE_MIN):return False,"too_early"
    if now>dl+timedelta(minutes=FINAL_WINDOW_AFTER_MIN):return False,"deadline_passed"
    return True,"in_window"

def _ensure_realtime_tables():
    tables=["v2_realtime_weather_snapshots","v2_realtime_exhibition_snapshots","v2_realtime_entry_snapshots","v2_realtime_odds_snapshots","v2_realtime_race_condition_snapshots","v2_realtime_racer_condition_snapshots"]
    for t in tables:execute(f"create table if not exists {t} (id bigserial primary key);")
    alters={
      "v2_realtime_weather_snapshots":[("race_id","text"),("race_date","date"),("venue_id","text"),("venue_code","text"),("race_no","integer"),("snapshot_label","text"),("snapshot_at","timestamptz"),("source","text"),("weather","text"),("temperature_c","numeric"),("water_temperature_c","numeric"),("wind_speed_m","numeric"),("wind_direction","text"),("wave_height_cm","numeric"),("raw","jsonb"),("updated_at","timestamptz")],
      "v2_realtime_exhibition_snapshots":[("race_id","text"),("race_date","date"),("venue_id","text"),("venue_code","text"),("race_no","integer"),("snapshot_label","text"),("snapshot_at","timestamptz"),("source","text"),("lane","integer"),("exhibition_course","integer"),("exhibition_time","numeric"),("exhibition_time_rank","integer"),("exhibition_time_diff","numeric"),("start_timing","numeric"),("start_timing_rank","integer"),("start_timing_diff","numeric"),("tilt","numeric"),("original_tilt","numeric"),("tilt_change","numeric"),("raw","jsonb"),("updated_at","timestamptz")],
      "v2_realtime_entry_snapshots":[("race_id","text"),("race_date","date"),("venue_id","text"),("venue_code","text"),("race_no","integer"),("snapshot_label","text"),("snapshot_at","timestamptz"),("source","text"),("lane","integer"),("racer_number","integer"),("racer_name","text"),("racer_class","text"),("original_course","integer"),("exhibition_course","integer"),("is_course_changed","boolean"),("motor_no","integer"),("boat_no","integer"),("tilt","numeric"),("raw","jsonb"),("updated_at","timestamptz")],
      "v2_realtime_odds_snapshots":[("race_id","text"),("race_date","date"),("venue_id","text"),("venue_code","text"),("race_no","integer"),("snapshot_label","text"),("snapshot_at","timestamptz"),("source","text"),("ticket","text"),("odds","numeric"),("market_rank","integer"),("prev_odds","numeric"),("odds_delta","numeric"),("odds_delta_pct","numeric"),("prev_market_rank","integer"),("market_rank_delta","integer"),("is_favorite","boolean"),("is_odds_too_low","boolean"),("is_odds_drift","boolean"),("is_odds_steam","boolean"),("raw","jsonb"),("updated_at","timestamptz")],
      "v2_realtime_race_condition_snapshots":[("race_id","text"),("race_date","date"),("venue_id","text"),("venue_code","text"),("race_no","integer"),("snapshot_label","text"),("snapshot_at","timestamptz"),("source","text"),("is_stabilizer_used","boolean"),("is_fixed_entry","boolean"),("race_distance_m","integer"),("has_new_propeller","boolean"),("parts_replacement_count","integer"),("raw","jsonb"),("updated_at","timestamptz")],
      "v2_realtime_racer_condition_snapshots":[("race_id","text"),("race_date","date"),("venue_id","text"),("venue_code","text"),("race_no","integer"),("snapshot_label","text"),("snapshot_at","timestamptz"),("source","text"),("lane","integer"),("racer_number","integer"),("weight_kg","numeric"),("adjustment_weight_kg","numeric"),("is_new_propeller","boolean"),("parts_replacements","jsonb"),("previous_race_no","integer"),("previous_course","integer"),("previous_st","numeric"),("previous_finish","integer"),("raw","jsonb"),("updated_at","timestamptz")]
    }
    for t,cols in alters.items():
        for c,typ in cols:execute(f"alter table {t} add column if not exists {c} {typ};")
    for sql in [
      "alter table v2_race_entries add column if not exists tilt numeric;",
      "alter table v2_race_entries add column if not exists motor_no integer;",
      "alter table v2_race_entries add column if not exists boat_no integer;",
      "create unique index if not exists uq_v2_rt_weather_race_label on v2_realtime_weather_snapshots (race_id,snapshot_label);",
      "create unique index if not exists uq_v2_rt_exh_race_label_lane on v2_realtime_exhibition_snapshots (race_id,snapshot_label,lane);",
      "create unique index if not exists uq_v2_rt_entry_race_label_lane on v2_realtime_entry_snapshots (race_id,snapshot_label,lane);",
      "create unique index if not exists uq_v2_rt_odds_race_label_ticket on v2_realtime_odds_snapshots (race_id,snapshot_label,ticket);",
      "create unique index if not exists uq_v2_rt_race_condition on v2_realtime_race_condition_snapshots (race_id,snapshot_label);",
      "create unique index if not exists uq_v2_rt_racer_condition on v2_realtime_racer_condition_snapshots (race_id,snapshot_label,lane);"]:
        execute(sql)
def _upsert(t,rows,conflict,chunk_size=500):
    if not rows:return 0
    cols=[x.strip() for x in conflict.split(",")];total=0
    for i in range(0,len(rows),chunk_size):total+=upsert_rows(t,rows[i:i+chunk_size],cols)
    return total
def _soup_text(html):
    if BeautifulSoup is not None:return _norm_text(BeautifulSoup(html,"html.parser").get_text(" ",strip=True))
    return _norm_text(re.sub(r"<[^>]+>"," ",html))
def parse_weather(html):
    text=_soup_text(html);weather=next((w for w in ["晴","曇り","くもり","雨","雪","霧"] if w in text),None)
    def rx(p):
        m=re.search(p,text);return _safe_float(m.group(1),None) if m else None
    m=re.search(r"(北|北東|東|南東|南|南西|西|北西|向い風|追い風|右横風|左横風)",text)
    return {"weather":weather,"temperature_c":rx(r"気温\s*([0-9.]+)\s*℃"),"water_temperature_c":rx(r"水温\s*([0-9.]+)\s*℃"),"wind_speed_m":rx(r"風速\s*([0-9.]+)\s*m"),"wind_direction":m.group(1) if m else None,"wave_height_cm":rx(r"波高\s*([0-9.]+)\s*cm"),"raw_text":text[:2000]}
def _extract_table_rows(html):
    if BeautifulSoup is None:return []
    out=[]
    for tr in BeautifulSoup(html,"html.parser").find_all("tr"):
        cells=[_norm_text(c.get_text(" ",strip=True)) for c in tr.find_all(["td","th"])];cells=[c for c in cells if c]
        if cells:out.append(cells)
    return out
def _rank_diff(rows,key,rk,dk):
    vals=sorted([(r["lane"],r.get(key)) for r in rows if r.get(key) is not None],key=lambda x:x[1])
    if not vals:return
    best=vals[0][1];ranks={lane:i+1 for i,(lane,_) in enumerate(vals)}
    for r in rows:
        if r.get(key) is not None:r[rk]=ranks[r["lane"]];r[dk]=round(float(r[key])-float(best),3)
def parse_exhibition(html):
    text=_soup_text(html);out=[]
    times=[_safe_float(x) for x in re.findall(r"(?<!\d)([67]\.\d{2})(?!\d)",text)]
    sts=[_safe_float(x) for x in re.findall(r"(?<!\d)(?:F|L)?(0?\.\d{2})(?!\d)",text)]
    if len(times)>=6:
        times=times[:6]
        for i in range(6):out.append({"lane":i+1,"exhibition_course":i+1,"exhibition_time":times[i],"start_timing":sts[i] if len(sts)>=6 else None,"raw_cells":[]})
    else:
        for cells in _extract_table_rows(html):
            lane=next((int(c) for c in cells[:3] if re.fullmatch(r"[1-6]",c)),None)
            if not lane:continue
            joined=" ".join(cells);mt=re.search(r"(?<!\d)([67]\.\d{2})(?!\d)",joined);ms=re.search(r"(?<!\d)(?:F|L)?(0?\.\d{2})(?!\d)",joined)
            if mt:out.append({"lane":lane,"exhibition_course":lane,"exhibition_time":_safe_float(mt.group(1)),"start_timing":_safe_float(ms.group(1),None) if ms else None,"raw_cells":[cells]})
    by={r["lane"]:r for r in out};out=[by[i] for i in sorted(by)]
    if len(out)<6 and not PARSE_ALLOW_PARTIAL:return []
    _rank_diff(out,"exhibition_time","exhibition_time_rank","exhibition_time_diff");_rank_diff(out,"start_timing","start_timing_rank","start_timing_diff")
    return out
def parse_odds3t(html):
    if not html:return {}
    text=_soup_text(html);out={}
    for m in re.finditer(r"([1-6])\s*[-－]\s*([1-6])\s*[-－]\s*([1-6])\s+([0-9]{1,4}(?:\.[0-9])?)",text):
        a,b,c,o=m.groups();ticket=_norm_ticket(f"{a}-{b}-{c}");v=_safe_float(o)
        if ticket and v>0:out[ticket]=v
    return out

PART_KEYWORDS=["ピストン","リング","電気一式","キャリアボデー","ギヤケース","クランクシャフト","シリンダ","キャブレタ","キャブレター","プロペラ"]
def parse_beforeinfo_extra(html,entries):
    soup=BeautifulSoup(html,"html.parser");text=_soup_text(html)
    entry_by_lane={_safe_int(e.get("lane")):e for e in entries if 1<=_safe_int(e.get("lane"))<=6}
    m=re.search(r"(?<!\d)(1200|1800)\s*m",text,flags=re.I);distance_m=_safe_int(m.group(1),None) if m else None
    race_condition={"is_stabilizer_used":"安定板" in text,"is_fixed_entry":"進入固定" in text,"race_distance_m":distance_m,"has_new_propeller":("新プロペラ" in text or "新ペラ" in text or "プロペラ交換" in text),"parts_replacement_count":0,"raw_text":text[:5000]}
    by_lane={lane:{"lane":lane,"racer_number":entry_by_lane.get(lane,{}).get("racer_number"),"weight_kg":None,"adjustment_weight_kg":None,"is_new_propeller":False,"parts_replacements":[],"previous_race_no":None,"previous_course":None,"previous_st":None,"previous_finish":None,"raw_cells":[]} for lane in range(1,7)}
    def norm(v):return unicodedata.normalize("NFKC",re.sub(r"\s+"," ",str(v or "")).strip())
    def cells_of(tr):return [norm(c.get_text(" ",strip=True)) for c in tr.find_all(["th","td"],recursive=False)]
    for tbody in soup.select("tbody.is-fs12"):
        rows=[cells_of(tr) for tr in tbody.find_all("tr",recursive=False)];rows=[x for x in rows if x]
        if not rows:continue
        main=rows[0];lane=next((int(norm(v)) for v in main[:3] if re.fullmatch(r"[1-6]",norm(v))),None)
        if lane is None:continue
        row=by_lane[lane];row["raw_cells"]=rows
        if len(main)>=4:
            wm=re.search(r"(?<!\d)(\d{2}(?:\.\d)?)\s*kg",norm(main[3]),flags=re.I)
            if wm:
                w=_safe_float(wm.group(1),None)
                if w is not None and 35<=w<=80:row["weight_kg"]=w
        prop=norm(main[6]) if len(main)>=7 else "";parts=norm(main[7]) if len(main)>=8 else "";prev=norm(main[-1]) if len(main)>=9 else ""
        row["is_new_propeller"]=any(k in prop for k in ("新プロペラ","新ペラ","プロペラ交換"))
        row["parts_replacements"]=[k for k in PART_KEYWORDS if k in parts]
        if re.fullmatch(r"\d{1,2}",prev):row["previous_race_no"]=int(prev)
        if row["previous_race_no"] is not None:
            if len(rows)>=2 and len(rows[1])>=2:
                d="".join(ch for ch in unicodedata.normalize("NFKC",str(rows[1][-1])) if ch.isdigit())
                if d and 1<=int(d)<=6:row["previous_course"]=int(d)
            if len(rows)>=4 and len(rows[3])>=2:
                d="".join(ch for ch in unicodedata.normalize("NFKC",str(rows[3][-1])) if ch.isdigit())
                if d and 1<=int(d)<=6:row["previous_finish"]=int(d)
        for cells in rows[1:]:
            n=[norm(x) for x in cells]
            if any("進入" in x for x in n):
                for v in reversed(n):
                    x=_safe_int(v,0)
                    if 1<=x<=6:row["previous_course"]=x;break
            if any(x.upper()=="ST" for x in n):
                if n:
                    x=_safe_float(n[0],None)
                    if x is not None and 0<=x<=10:row["adjustment_weight_kg"]=x
                idx=next((i for i,v in enumerate(n) if v.upper()=="ST"),-1)
                if idx>=0:
                    for v in n[idx+1:]:
                        if re.fullmatch(r"[FL]?\d?\.\d{2}",v.strip(),flags=re.I):
                            x=_safe_float(v.replace("F","-").replace("L",""),None)
                            if x is not None:row["previous_st"]=x;break
            if any("着順" in x for x in n):
                for v in reversed(n):
                    x=_safe_int(v,0)
                    if 1<=x<=6:row["previous_finish"]=x;break
        if row["adjustment_weight_kg"] is None:
            for cells in rows:
                n=[norm(x) for x in cells]
                if any(x.upper()=="ST" for x in n) and n:
                    x=_safe_float(n[0],None)
                    if x is not None and 0<=x<=10:row["adjustment_weight_kg"]=x;break
    race_condition["parts_replacement_count"]=sum(len(r["parts_replacements"]) for r in by_lane.values())
    race_condition["has_new_propeller"]=bool(race_condition["has_new_propeller"] or any(r["is_new_propeller"] for r in by_lane.values()))
    return race_condition,[by_lane[i] for i in range(1,7)]
def save_beforeinfo_extra(race,entries,race_condition,racer_conditions):
    rid=str(race.get("race_id"));v=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2);rno=_safe_int(race.get("race_no"));now=_now_iso()
    rr={"race_id":rid,"race_date":race.get("race_date"),"venue_id":v,"venue_code":v,"race_no":rno,"snapshot_label":SNAPSHOT_LABEL,"snapshot_at":now,"source":"official_beforeinfo","is_stabilizer_used":race_condition.get("is_stabilizer_used"),"is_fixed_entry":race_condition.get("is_fixed_entry"),"race_distance_m":race_condition.get("race_distance_m"),"has_new_propeller":race_condition.get("has_new_propeller"),"parts_replacement_count":race_condition.get("parts_replacement_count"),"raw":{"text":race_condition.get("raw_text","")},"updated_at":now}
    rows=[]
    for x in racer_conditions:
        rows.append({"race_id":rid,"race_date":race.get("race_date"),"venue_id":v,"venue_code":v,"race_no":rno,"snapshot_label":SNAPSHOT_LABEL,"snapshot_at":now,"source":"official_beforeinfo","lane":x.get("lane"),"racer_number":x.get("racer_number"),"weight_kg":x.get("weight_kg"),"adjustment_weight_kg":x.get("adjustment_weight_kg"),"is_new_propeller":x.get("is_new_propeller"),"parts_replacements":x.get("parts_replacements",[]),"previous_race_no":x.get("previous_race_no"),"previous_course":x.get("previous_course"),"previous_st":x.get("previous_st"),"previous_finish":x.get("previous_finish"),"raw":{"cells":x.get("raw_cells",[])},"updated_at":now})
    return _upsert("v2_realtime_race_condition_snapshots",[rr],"race_id,snapshot_label"),_upsert("v2_realtime_racer_condition_snapshots",rows,"race_id,snapshot_label,lane")
def fetch_day_base(ds):
    p=_rid_prefix(ds);q=_rid_prefix(_next_day(ds))
    races=fetch_all("select * from v2_races where race_date=%s order by venue_id,race_no;",(ds,))
    races=[r for r in races if str(r.get("venue_id") or r.get("venue_code") or "").zfill(2) in TARGET_VENUES]
    if TARGET_RACE_ID:races=[r for r in races if str(r.get("race_id"))==TARGET_RACE_ID]
    er=fetch_all("select * from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane;",(p,q));eb=defaultdict(list)
    for e in er:eb[str(e.get("race_id"))].append(e)
    oo=fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s order by race_id,ticket;",(p,q));ob=defaultdict(dict)
    for o in oo:
        t=_norm_ticket(o.get("ticket"));v=_safe_float(o.get("odds"))
        if t and v>0:ob[str(o.get("race_id"))][t]=v
    return races,eb,ob
def _fetch_previous_odds(rid):
    rows=fetch_all("select ticket,odds,market_rank,snapshot_at from v2_realtime_odds_snapshots where race_id=%s order by snapshot_at desc nulls last limit 240;",(rid,));out={}
    for r in rows:
        t=_norm_ticket(r.get("ticket"))
        if t and t not in out:out[t]=r
    return out
def _infer_venue_style(v):return "bad5" if v in BAD5_VENUES else "rough" if v in ROUGH_VENUES else "in_strong" if v in IN_STRONG_VENUES else "standard"
def _event_day_by_venue(ds):
    rows=fetch_all("select race_date,venue_id,venue_code from v2_races where race_date >= %s and race_date <= %s order by race_date,venue_id;",(_shift_day(ds,-10),ds));dates=defaultdict(list)
    for r in rows:
        d=str(r.get("race_date"));v=str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
        if d not in dates[v]:dates[v].append(d)
    out={}
    for v,arr in dates.items():
        cur=0;prev=""
        for d in sorted(arr):cur=cur+1 if prev and d==_shift_day(prev,1) else 1;prev=d;out[v]=cur if d==ds else out.get(v,cur)
    return out
def _is_candidate_race(v,rno,day):
    if 1<=rno<=9:return True
    style=_infer_venue_style(v)
    return (style=="bad5" and 4<=rno<=9) or (style=="in_strong" and (1<=rno<=3 or 7<=rno<=9)) or (day in (2,3) and 4<=rno<=9) or (day>=6 and (1<=rno<=3 or 7<=rno<=9))

def save_weather(r,w):
    v=str(r.get("venue_id") or r.get("venue_code") or "").zfill(2);now=_now_iso()
    row={"race_id":str(r.get("race_id")),"race_date":r.get("race_date"),"venue_id":v,"venue_code":v,"race_no":_safe_int(r.get("race_no")),"snapshot_label":SNAPSHOT_LABEL,"snapshot_at":now,"source":"official_beforeinfo","weather":w.get("weather"),"temperature_c":w.get("temperature_c"),"water_temperature_c":w.get("water_temperature_c"),"wind_speed_m":w.get("wind_speed_m"),"wind_direction":w.get("wind_direction"),"wave_height_cm":w.get("wave_height_cm"),"raw":{"text":w.get("raw_text","")},"updated_at":now}
    return _upsert("v2_realtime_weather_snapshots",[row],"race_id,snapshot_label")
def save_exhibition_and_entries(r,entries,exh):
    rid=str(r.get("race_id"));v=str(r.get("venue_id") or r.get("venue_code") or "").zfill(2);rno=_safe_int(r.get("race_no"));eb={_safe_int(e.get("lane")):e for e in entries};xb={_safe_int(x.get("lane")):x for x in exh};er=[];xr=[]
    for lane in range(1,7):
        e=eb.get(lane,{});x=xb.get(lane,{});course=x.get("exhibition_course");raw={"cells":x.get("raw_cells",[])};now=_now_iso()
        er.append({"race_id":rid,"race_date":r.get("race_date"),"venue_id":v,"venue_code":v,"race_no":rno,"snapshot_label":SNAPSHOT_LABEL,"snapshot_at":now,"source":"official_beforeinfo","lane":lane,"racer_number":e.get("racer_number"),"racer_name":e.get("racer_name"),"racer_class":str(e.get("racer_class")) if e.get("racer_class") is not None else None,"original_course":lane,"exhibition_course":course,"is_course_changed":bool(course and course!=lane),"motor_no":e.get("motor_no"),"boat_no":e.get("boat_no"),"tilt":x.get("tilt"),"raw":raw,"updated_at":now})
        if x:xr.append({"race_id":rid,"race_date":r.get("race_date"),"venue_id":v,"venue_code":v,"race_no":rno,"snapshot_label":SNAPSHOT_LABEL,"snapshot_at":now,"source":"official_beforeinfo","lane":lane,"exhibition_course":course or lane,"exhibition_time":x.get("exhibition_time"),"exhibition_time_rank":x.get("exhibition_time_rank"),"exhibition_time_diff":x.get("exhibition_time_diff"),"start_timing":x.get("start_timing"),"start_timing_rank":x.get("start_timing_rank"),"start_timing_diff":x.get("start_timing_diff"),"tilt":x.get("tilt"),"original_tilt":_safe_float(e.get("tilt"),None),"tilt_change":None,"raw":raw,"updated_at":now})
    return _upsert("v2_realtime_exhibition_snapshots",xr,"race_id,snapshot_label,lane"),_upsert("v2_realtime_entry_snapshots",er,"race_id,snapshot_label,lane")
def save_odds(r,odds,source):
    rid=str(r.get("race_id"));v=str(r.get("venue_id") or r.get("venue_code") or "").zfill(2);valid={};invalid=0
    for raw_t,raw_o in (odds or {}).items():
        t=_norm_ticket(raw_t);o=_safe_float(raw_o)
        if not t or o<=0:invalid+=1;continue
        valid[t]=o
    if invalid:print(f"WARNING invalid trifecta rejected: race_id={rid} count={invalid}",flush=True)
    if len(valid)!=120:print(f"WARNING realtime odds incomplete: race_id={rid} valid_tickets={len(valid)}/120 source={source}",flush=True)
    if not valid:return 0
    prev=_fetch_previous_odds(rid);ranked=sorted(valid.items(),key=lambda x:x[1]);ranks={t:i+1 for i,(t,_) in enumerate(ranked)};rows=[]
    for t,o in ranked:
        p=prev.get(t,{});po=_safe_float(p.get("odds"),None) if p else None;pr=_safe_int(p.get("market_rank"),0) if p and p.get("market_rank") is not None else None;delta=round(o-po,2) if po else None;dp=round((o-po)/po,4) if po else None;now=_now_iso()
        rows.append({"race_id":rid,"race_date":r.get("race_date"),"venue_id":v,"venue_code":v,"race_no":_safe_int(r.get("race_no")),"snapshot_label":SNAPSHOT_LABEL,"snapshot_at":now,"source":source,"ticket":t,"odds":o,"market_rank":ranks[t],"prev_odds":po,"odds_delta":delta,"odds_delta_pct":dp,"prev_market_rank":pr,"market_rank_delta":ranks[t]-pr if pr is not None else None,"is_favorite":ranks[t]==1,"is_odds_too_low":o<3,"is_odds_drift":bool(dp is not None and dp>=.15),"is_odds_steam":bool(dp is not None and dp<=-.15),"raw":{},"updated_at":now})
    return _upsert("v2_realtime_odds_snapshots",rows,"race_id,snapshot_label,ticket")
def main():
    _require_settings();_ensure_realtime_tables();now=_now()
    print("✅ v21_realtime_collector_pg.py VERSION 2026-08-16 collect-all-dual-target-files-v3",flush=True)
    print(f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} SCOPE={COLLECT_SCOPE} TARGET_ID_SCOPE={TARGET_ID_SCOPE} TARGET_RACE_ID={TARGET_RACE_ID or '-'} PARSE_ALLOW_PARTIAL={PARSE_ALLOW_PARTIAL}",flush=True)
    print(f"FINAL_DEADLINE_FILTER={FINAL_DEADLINE_FILTER} FINAL_WINDOW_BEFORE_MIN={FINAL_WINDOW_BEFORE_MIN} FINAL_WINDOW_AFTER_MIN={FINAL_WINDOW_AFTER_MIN} NOW_JST={now.isoformat()}",flush=True)
    races,entries_by,base_odds=fetch_day_base(TARGET_DATE);days=_event_day_by_venue(TARGET_DATE);scope=[]
    for r in races:
        rid=str(r.get("race_id"));v=str(r.get("venue_id") or r.get("venue_code") or "").zfill(2);rno=_safe_int(r.get("race_no"))
        if TARGET_RACE_ID and rid!=TARGET_RACE_ID:continue
        if COLLECT_SCOPE=="candidates" and not _is_candidate_race(v,rno,days.get(v,1)):continue
        scope.append(r)
    use_filter=FINAL_DEADLINE_FILTER and not TARGET_RACE_ID;target=[];miss=early=passed=0
    for r in scope:
        if not use_filter:target.append(r);continue
        ok,why=_deadline_match(r,now)
        if ok:target.append(r)
        elif why=="deadline_missing":miss+=1
        elif why=="too_early":early+=1
        else:passed+=1
    print(f"races={len(races)} scope_races={len(scope)} target_races={len(target)}",flush=True)
    print(f"deadline_filter_used={use_filter} skipped_deadline_missing={miss} skipped_too_early={early} skipped_deadline_passed={passed}",flush=True)
    # 収集対象(target)と、後段の本番判定へ渡すrace_idを分離する。
    # COLLECT_SCOPE=all + TARGET_ID_SCOPE=candidates にすると、
    # 締切前の全レースの直前情報を保存しつつ、従来の候補レースだけを
    # TARGET_RACE_IDS_FILEへ出力できる。
    if TARGET_RACE_ID:
        target_id_rows = target
    elif TARGET_ID_SCOPE in ("candidates", "candidate"):
        target_id_rows = []
        for r in target:
            v=str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
            rno=_safe_int(r.get("race_no"))
            if _is_candidate_race(v,rno,days.get(v,1)):
                target_id_rows.append(r)
    elif TARGET_ID_SCOPE in ("none", "off", "disabled"):
        target_id_rows = []
    else:
        # same / all: 従来互換。収集対象をそのまま出力する。
        target_id_rows = target

    collection_ids=[str(r.get("race_id")) for r in target if r.get("race_id")]
    target_ids=[str(r.get("race_id")) for r in target_id_rows if r.get("race_id")]
    print(
        f"collection_target_races={len(collection_ids)} "
        f"decision_target_races={len(target_ids)} "
        f"TARGET_ID_SCOPE={TARGET_ID_SCOPE}",
        flush=True,
    )
    try:
        Path(COLLECTION_RACE_IDS_FILE).write_text(",".join(collection_ids),encoding="utf-8")
        print(
            f"COLLECTION_RACE_IDS_FILE={COLLECTION_RACE_IDS_FILE} "
            f"written={len(collection_ids)}",
            flush=True,
        )
    except Exception as e:
        raise RuntimeError(
            f"COLLECTION_RACE_IDS_FILEの書き込みに失敗しました: {e}"
        ) from e
    try:
        Path(TARGET_RACE_IDS_FILE).write_text(",".join(target_ids),encoding="utf-8")
        print(f"TARGET_RACE_IDS_FILE={TARGET_RACE_IDS_FILE} written={len(target_ids)}",flush=True)
    except Exception as e:raise RuntimeError(f"TARGET_RACE_IDS_FILEの書き込みに失敗しました: {e}") from e
    for r in target[:20]:
        dl=_parse_deadline_at(r);print(f"  {r.get('race_id')} deadline={dl.isoformat() if dl else '-'}",flush=True)
    sw=sx=se=so=src_cond=splayer_cond=nb=ne=no=0
    for i,r in enumerate(target,1):
        rid=str(r.get("race_id"));v=str(r.get("venue_id") or r.get("venue_code") or "").zfill(2);rno=_safe_int(r.get("race_no"));bh=_fetch(_official_url("beforeinfo",TARGET_DATE,v,rno));ex=[]
        if _looks_no_data(bh):
            nb+=1;c1,c2=save_exhibition_and_entries(r,entries_by.get(rid,[]),[]);sx+=c1;se+=c2
        else:
            sw+=save_weather(r,parse_weather(bh or ""));ex=parse_exhibition(bh or "");ne+=int(not ex);c1,c2=save_exhibition_and_entries(r,entries_by.get(rid,[]),ex);sx+=c1;se+=c2
            race_cond,racer_cond=parse_beforeinfo_extra(bh or "",entries_by.get(rid,[]));c3,c4=save_beforeinfo_extra(r,entries_by.get(rid,[]),race_cond,racer_cond);src_cond+=c3;splayer_cond+=c4
        oh=_fetch(_official_url("odds3t",TARGET_DATE,v,rno));od=parse_odds3t(oh or "") if oh else {};src="official_odds3t"
        if len(od)<80 and base_odds.get(rid):od=base_odds[rid];src="v2_odds_trifecta_fallback"
        if od:so+=save_odds(r,od,src)
        else:no+=1
        print(f"[{i}/{len(target)}] {rid} before={'ok' if bh else 'ng'} exh_rows={len(ex)} odds={len(od)} source={src if od else '-'}",flush=True)
        if REALTIME_SLEEP_SEC>0:time.sleep(REALTIME_SLEEP_SEC)
    print("\n=== v21 PG realtime collection summary ===",flush=True)
    print(f"scope_races: {len(scope)}\ntarget_races: {len(target)}\nsaved_weather: {sw}\nsaved_exhibition_rows: {sx}\nsaved_entry_rows: {se}\nsaved_race_condition_rows: {src_cond}\nsaved_racer_condition_rows: {splayer_cond}\nsaved_odds_rows: {so}\nno_beforeinfo: {nb}\nno_exhibition_complete: {ne}\nno_odds: {no}",flush=True)
    print("=== v21 PG リアルタイム収集終了 ===",flush=True)
if __name__=="__main__":main()
