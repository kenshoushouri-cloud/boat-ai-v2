# -*- coding: utf-8 -*-
from __future__ import annotations
import os,re,time,threading,unicodedata
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta,timezone
from typing import Any,Dict,List,Optional,Tuple
import requests
from bs4 import BeautifulSoup
from db_pg import fetch_all,upsert_rows

JST=timezone(timedelta(hours=9))
START_DATE=os.getenv("BACKFILL_START_DATE","").strip()
END_DATE=os.getenv("BACKFILL_END_DATE","").strip()
SNAPSHOT_LABEL=os.getenv("SNAPSHOT_LABEL","final_ab").strip() or "final_ab"
WORKERS=max(1,int(os.getenv("BACKFILL_WORKERS","3")))
BATCH_RACES=max(1,int(os.getenv("BACKFILL_BATCH_RACES","50")))
SLEEP_SEC=max(0.0,float(os.getenv("BACKFILL_SLEEP_SEC","0.15")))
HTTP_TIMEOUT=max(10,int(os.getenv("HTTP_TIMEOUT","35")))
RETRY_MAX=max(0,int(os.getenv("RETRY_MAX","2")))
RETRY_SLEEP=max(0.0,float(os.getenv("RETRY_SLEEP","1.5")))
SKIP_COMPLETE=os.getenv("BACKFILL_SKIP_COMPLETE","1").lower() not in {"0","false","no"}
SAVE_RAW=os.getenv("BACKFILL_SAVE_RAW","0").lower() in {"1","true","yes"}
VENUES=[x.strip().zfill(2) for x in os.getenv("BACKFILL_VENUES",",".join(f"{i:02d}" for i in range(1,25))).split(",") if x.strip()]
OFFICIAL="https://www.boatrace.jp/owpc/pc/race"
_thread_local=threading.local()

def _norm_text(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def _safe_int(v, d=0):
    try:
        return int(float(str(v).replace(',', ''))) if v not in (None, '') else d
    except:
        return d

def _safe_float(v, d=0.0):
    try:
        if v in (None, ''):
            return d
        s = str(v).replace(',', '').replace('F', '').replace('L', '').strip()
        if s.startswith('.'):
            s = '0' + s
        if s.startswith('-.'):
            s = s.replace('-.', '-0.', 1)
        return float(s)
    except:
        return d

def _soup_text(html):
    if BeautifulSoup is not None:
        return _norm_text(BeautifulSoup(html, 'html.parser').get_text(' ', strip=True))
    return _norm_text(re.sub('<[^>]+>', ' ', html))

PART_KEYWORDS = ['ãã¹ãã³', 'ãªã³ã°', 'é»æ°ä¸å¼', 'ã­ã£ãªã¢ããã¼', 'ã®ã¤ã±ã¼ã¹', 'ã¯ã©ã³ã¯ã·ã£ãã', 'ã·ãªã³ã', 'ã­ã£ãã¬ã¿', 'ã­ã£ãã¬ã¿ã¼', 'ãã­ãã©']

def parse_beforeinfo_extra(html, entries):
    """
    beforeinfoã®é¸æå¥tbodyããè¿½å æå ±ãæ½åºããã

    å¬å¼HTMLã¯ä¸é¨trã®å¥ãå­ãä¸æ­£ãªãããè¡çªå·åºå®ã ãã§ãªã
    ãé²å¥ããSTããçé ãã®ã©ãã«ãæã¤è¡ãæ¤ç´¢ãã¦å¤ãåå¾ããã
    """
    soup = BeautifulSoup(html, 'html.parser')
    text = _soup_text(html)
    entry_by_lane = {_safe_int(e.get('lane')): e for e in entries if 1 <= _safe_int(e.get('lane')) <= 6}
    distance_m = None
    m = re.search('(?<!\\d)(1200|1800)\\s*m', text, flags=re.I)
    if m:
        distance_m = _safe_int(m.group(1), None)
    race_condition = {'is_stabilizer_used': 'å®å®æ¿' in text, 'is_fixed_entry': 'é²å¥åºå®' in text, 'race_distance_m': distance_m, 'has_new_propeller': 'æ°ãã­ãã©' in text or 'æ°ãã©' in text or 'ãã­ãã©äº¤æ' in text, 'parts_replacement_count': 0, 'raw_text': text[:5000]}
    by_lane = {lane: {'lane': lane, 'racer_number': entry_by_lane.get(lane, {}).get('racer_number'), 'weight_kg': None, 'adjustment_weight_kg': None, 'is_new_propeller': False, 'parts_replacements': [], 'previous_race_no': None, 'previous_course': None, 'previous_st': None, 'previous_finish': None, 'raw_cells': []} for lane in range(1, 7)}

    def norm(value):
        return unicodedata.normalize('NFKC', re.sub('\\s+', ' ', str(value or '')).strip())

    def cells_of(tr):
        return [norm(cell.get_text(' ', strip=True)) for cell in tr.find_all(['th', 'td'], recursive=False)]
    for tbody in soup.select('tbody.is-fs12'):
        trs = tbody.find_all('tr', recursive=False)
        if not trs:
            continue
        row_cells = [cells_of(tr) for tr in trs]
        row_cells = [cells for cells in row_cells if cells]
        if not row_cells:
            continue
        main = row_cells[0]
        lane = None
        for value in main[:3]:
            if re.fullmatch('[1-6]', norm(value)):
                lane = int(norm(value))
                break
        if lane is None:
            continue
        row = by_lane[lane]
        row['raw_cells'] = row_cells
        if len(main) >= 4:
            weight_match = re.search('(?<!\\d)(\\d{2}(?:\\.\\d)?)\\s*kg', norm(main[3]), flags=re.I)
            if weight_match:
                weight = _safe_float(weight_match.group(1), None)
                if weight is not None and 35 <= weight <= 80:
                    row['weight_kg'] = weight
        propeller_text = norm(main[6]) if len(main) >= 7 else ''
        parts_text = norm(main[7]) if len(main) >= 8 else ''
        previous_r_text = norm(main[-1]) if len(main) >= 9 else ''
        row['is_new_propeller'] = any((key in propeller_text for key in ('æ°ãã­ãã©', 'æ°ãã©', 'ãã­ãã©äº¤æ')))
        parts = []
        for keyword in PART_KEYWORDS:
            if keyword in parts_text and keyword not in parts:
                parts.append(keyword)
        row['parts_replacements'] = parts
        prev_r = re.fullmatch('\\d{1,2}', previous_r_text)
        if prev_r:
            row['previous_race_no'] = int(previous_r_text)
        if row.get('previous_race_no') is not None:
            if len(row_cells) >= 2 and len(row_cells[1]) >= 2:
                raw_course = str(row_cells[1][-1])
                digits = ''.join((ch for ch in unicodedata.normalize('NFKC', raw_course) if ch.isdigit()))
                if digits:
                    course_value = int(digits)
                    if 1 <= course_value <= 6:
                        row['previous_course'] = course_value
            if len(row_cells) >= 4 and len(row_cells[3]) >= 2:
                raw_finish = str(row_cells[3][-1])
                digits = ''.join((ch for ch in unicodedata.normalize('NFKC', raw_finish) if ch.isdigit()))
                if digits:
                    finish_value = int(digits)
                    if 1 <= finish_value <= 6:
                        row['previous_finish'] = finish_value
        for cells in row_cells[1:]:
            normalized = [norm(x) for x in cells]
            joined = ' | '.join(normalized)
            if any(('é²å¥' in x for x in normalized)):
                for value in reversed(normalized):
                    course_value = _safe_int(value, 0)
                    if 1 <= course_value <= 6:
                        row['previous_course'] = course_value
                        break
            if any((x.upper() == 'ST' for x in normalized)):
                if normalized:
                    adjustment = _safe_float(normalized[0], None)
                    if adjustment is not None and 0 <= adjustment <= 10:
                        row['adjustment_weight_kg'] = adjustment
                st_label_index = next((idx for idx, value in enumerate(normalized) if value.upper() == 'ST'), -1)
                if st_label_index >= 0:
                    for value in normalized[st_label_index + 1:]:
                        st_text = value.strip()
                        if re.fullmatch('[FL]?\\d?\\.\\d{2}', st_text, flags=re.I):
                            st_value = _safe_float(st_text.replace('F', '-').replace('L', ''), None)
                            if st_value is not None:
                                row['previous_st'] = st_value
                                break
            if any(('çé ' in x for x in normalized)):
                for value in reversed(normalized):
                    finish_value = _safe_int(value, 0)
                    if 1 <= finish_value <= 6:
                        row['previous_finish'] = finish_value
                        break
        if row.get('previous_race_no') is not None:
            pass
        if row['adjustment_weight_kg'] is None:
            for cells in row_cells:
                normalized = [norm(x) for x in cells]
                if any((x.upper() == 'ST' for x in normalized)) and normalized:
                    adjustment = _safe_float(normalized[0], None)
                    if adjustment is not None and 0 <= adjustment <= 10:
                        row['adjustment_weight_kg'] = adjustment
                        break
    total_parts = sum((len(row.get('parts_replacements', [])) for row in by_lane.values()))
    race_condition['parts_replacement_count'] = total_parts
    race_condition['has_new_propeller'] = bool(race_condition['has_new_propeller'] or any((row.get('is_new_propeller') for row in by_lane.values())))
    pass
    return (race_condition, [by_lane[lane] for lane in range(1, 7)])


def _session():
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; boat-ai-beforeinfo-history-backfill/1.0)",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        })
        _thread_local.session = s
    return s

def _fetch(url):
    last = None
    for attempt in range(RETRY_MAX + 1):
        try:
            r = _session().get(url, timeout=HTTP_TIMEOUT)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception as exc:
            last = exc
            if attempt < RETRY_MAX:
                time.sleep(RETRY_SLEEP)
    raise RuntimeError(f"fetch_failed: {last!r}")

def _url(race):
    ds = str(race.get("race_date")).replace("-", "")
    venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
    rno = _safe_int(race.get("race_no"))
    return f"{OFFICIAL}/beforeinfo?rno={rno}&jcd={venue}&hd={ds}"

def _no_data(html):
    if not html:
        return True
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return any(x in text for x in ("ãã¼ã¿ãããã¾ãã","éå¬ã¯ããã¾ãã","è©²å½ãããã¼ã¿ã¯ããã¾ãã"))

def _rows(race, race_cond, racer_conds):
    rid = str(race.get("race_id"))
    venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
    rno = _safe_int(race.get("race_no"))
    now = datetime.now(JST).isoformat()
    race_row = {
        "race_id": rid, "race_date": race.get("race_date"),
        "venue_id": venue, "venue_code": venue, "race_no": rno,
        "snapshot_label": SNAPSHOT_LABEL, "snapshot_at": now,
        "source": "official_beforeinfo_history",
        "is_stabilizer_used": race_cond.get("is_stabilizer_used"),
        "is_fixed_entry": race_cond.get("is_fixed_entry"),
        "race_distance_m": race_cond.get("race_distance_m"),
        "has_new_propeller": race_cond.get("has_new_propeller"),
        "parts_replacement_count": race_cond.get("parts_replacement_count"),
        "raw": {"text": race_cond.get("raw_text", "")[:5000]} if SAVE_RAW else {},
        "updated_at": now,
    }
    racer_rows = []
    for row in racer_conds:
        racer_rows.append({
            "race_id": rid, "race_date": race.get("race_date"),
            "venue_id": venue, "venue_code": venue, "race_no": rno,
            "snapshot_label": SNAPSHOT_LABEL, "snapshot_at": now,
            "source": "official_beforeinfo_history",
            "lane": row.get("lane"), "racer_number": row.get("racer_number"),
            "weight_kg": row.get("weight_kg"),
            "adjustment_weight_kg": row.get("adjustment_weight_kg"),
            "is_new_propeller": row.get("is_new_propeller"),
            "parts_replacements": row.get("parts_replacements", []),
            "previous_race_no": row.get("previous_race_no"),
            "previous_course": row.get("previous_course"),
            "previous_st": row.get("previous_st"),
            "previous_finish": row.get("previous_finish"),
            "raw": {"cells": row.get("raw_cells", [])} if SAVE_RAW else {},
            "updated_at": now,
        })
    return race_row, racer_rows

def _process(race, entries):
    rid = str(race.get("race_id"))
    try:
        html = _fetch(_url(race))
        if _no_data(html):
            return {"status":"no_data","race_id":rid}
        rc, rcs = parse_beforeinfo_extra(html or "", entries)
        wc = sum(x.get("weight_kg") is not None for x in rcs)
        if wc < 6:
            return {"status":"parse_incomplete","race_id":rid,"detail":f"weight={wc}/6"}
        rr, rrs = _rows(race, rc, rcs)
        return {
            "status":"ok","race_id":rid,"race_row":rr,"racer_rows":rrs,
            "previous_st_filled":sum(x.get("previous_st") is not None for x in rcs),
        }
    except Exception as exc:
        return {"status":"failed","race_id":rid,"detail":repr(exc)}
    finally:
        if SLEEP_SEC:
            time.sleep(SLEEP_SEC)

def _flush(race_rows, racer_rows):
    a = upsert_rows("v2_realtime_race_condition_snapshots", race_rows, ["race_id","snapshot_label"]) if race_rows else 0
    b = upsert_rows("v2_realtime_racer_condition_snapshots", racer_rows, ["race_id","snapshot_label","lane"]) if racer_rows else 0
    race_rows.clear(); racer_rows.clear()
    return a, b

def main():
    print("â backfill_beforeinfo_history_pg.py VERSION 2026-07-16 january-safety-v2-norm-text-fix", flush=True)
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")
    if not START_DATE or not END_DATE:
        raise RuntimeError("BACKFILL_START_DATE ã¨ BACKFILL_END_DATE ãå¿è¦ã§ãã")
    print(f"PERIOD={START_DATE}..{END_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL}", flush=True)
    print(f"WORKERS={WORKERS} BATCH_RACES={BATCH_RACES} SLEEP_SEC={SLEEP_SEC} SKIP_COMPLETE={SKIP_COMPLETE} SAVE_RAW={SAVE_RAW}", flush=True)
    print("æ¬çªå¤å®ã»LINEéç¥ã»è³¼å¥å¦çã¯è¡ãã¾ããã", flush=True)

    races = fetch_all("""
        select * from v2_races
        where race_date >= %s and race_date <= %s
          and coalesce(venue_id, venue_code) = any(%s)
        order by race_date, venue_id, race_no;
    """, (START_DATE, END_DATE, VENUES))
    ids = [str(r.get("race_id")) for r in races]
    print(f"db_target_races={len(races)}", flush=True)
    if not ids:
        print("å¯¾è±¡ã¬ã¼ã¹ã¯ããã¾ããã", flush=True); return

    entries_by = {}
    for row in fetch_all("select * from v2_race_entries where race_id=any(%s) order by race_id,lane;", (ids,)):
        entries_by.setdefault(str(row.get("race_id")), []).append(row)

    completed = set()
    if SKIP_COMPLETE:
        rows = fetch_all("""
            select race_id from v2_realtime_racer_condition_snapshots
            where race_id=any(%s) and snapshot_label=%s
            group by race_id having count(distinct lane)=6;
        """, (ids, SNAPSHOT_LABEL))
        completed = {str(r.get("race_id")) for r in rows}

    tasks=[]; skipped_complete=0; skipped_entries=0
    for race in races:
        rid=str(race.get("race_id")); entries=entries_by.get(rid,[])
        if rid in completed: skipped_complete += 1; continue
        if len(entries) != 6: skipped_entries += 1; continue
        tasks.append((race,entries))
    print(f"tasks={len(tasks)} skipped_complete={skipped_complete} skipped_entries={skipped_entries}", flush=True)

    pending_race=[]; pending_racer=[]
    counts={"success":0,"no_data":0,"parse_incomplete":0,"failed":0}
    saved_races=saved_racers=previous_st_filled=0; samples=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures=[ex.submit(_process,r,e) for r,e in tasks]
        for i,fut in enumerate(as_completed(futures),1):
            res=fut.result(); st=res.get("status")
            if st=="ok":
                counts["success"] += 1
                pending_race.append(res["race_row"]); pending_racer.extend(res["racer_rows"])
                previous_st_filled += _safe_int(res.get("previous_st_filled"))
            else:
                counts[st] = counts.get(st,0) + 1
                if st in ("parse_incomplete","failed") and len(samples)<20: samples.append(res)
            if len(pending_race)>=BATCH_RACES or i==len(futures):
                a,b=_flush(pending_race,pending_racer); saved_races+=a; saved_racers+=b
            if i%50==0 or i==len(futures):
                print(f"progress={i}/{len(futures)} success={counts['success']} no_data={counts['no_data']} parse_incomplete={counts['parse_incomplete']} failed={counts['failed']}", flush=True)

    print("=== historical beforeinfo backfill summary ===", flush=True)
    print(f"target_races={len(races)} tasks={len(tasks)}", flush=True)
    for k in ("success","no_data","parse_incomplete","failed"):
        print(f"{k}={counts[k]}", flush=True)
    print(f"saved_race_rows={saved_races}", flush=True)
    print(f"saved_racer_rows={saved_racers}", flush=True)
    print(f"previous_st_filled={previous_st_filled}", flush=True)
    if samples:
        print("--- failure samples ---", flush=True)
        for s in samples: print(s, flush=True)
    print("æåã®1ãæçµäºå¾ã«DBå®¹éã¨åå¾çãç¢ºèªãã¦ãããæ¬¡æã¸é²ãã§ãã ããã", flush=True)
    print("=== historical beforeinfo backfill finished ===", flush=True)

if __name__ == "__main__":
    main()