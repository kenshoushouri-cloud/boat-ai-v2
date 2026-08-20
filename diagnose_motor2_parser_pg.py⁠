# -*- coding: utf-8 -*-
from __future__ import annotations
import os,re
from typing import Any,Dict,List,Tuple
from db_pg import fetch_all
import repair_month_all_pg as repair

VERSION='2026-08-20 motor2-parser-diagnostic-v1'
MAX_RACES=max(1,int(os.getenv('DIAG_MAX_RACES','5')))
RAW_IDS=(os.getenv('DIAG_RACE_IDS') or '').strip()

def si(v:Any,d:int=0)->int:
    try:return int(float(v)) if v not in (None,'') else d
    except Exception:return d

def sf(v:Any,d=None):
    try:return float(v) if v not in (None,'') else d
    except Exception:return d

def target_ids()->List[str]:
    if RAW_IDS:
        return [x.strip() for x in re.split(r'[,\s]+',RAW_IDS) if x.strip()][:MAX_RACES]
    rows=fetch_all('''
        SELECT DISTINCT race_id
        FROM v2_race_entries
        WHERE motor_place2_rate IS NOT NULL
          AND (motor_place2_rate < 0 OR motor_place2_rate > 100)
        ORDER BY race_id DESC
        LIMIT %s
    ''',(MAX_RACES,))
    return [str(r.get('race_id') or '') for r in rows if r.get('race_id')]

def db_entries(race_id:str)->List[Dict[str,Any]]:
    return fetch_all('''
        SELECT race_id,lane,racer_number,racer_name,racer_class,avg_st,
               national_win_rate,national_place2_rate,national_place3_rate,
               local_win_rate,local_place2_rate,local_place3_rate,
               motor_no,motor_place2_rate,motor_place3_rate,
               boat_no,boat_place2_rate,boat_place3_rate
        FROM v2_race_entries
        WHERE race_id=%s
        ORDER BY lane
    ''',(race_id,))

def raw_lines(html:str)->List[str]:
    soup=repair.BeautifulSoup(html,'html.parser')
    out=[]
    for line in soup.get_text('\n',strip=True).splitlines():
        line=repair._clean_text(repair._zen_to_han(line))
        if line: out.append(line)
    return out

def segments(html:str)->Dict[int,Tuple[List[str],List[str]]]:
    all_lines=raw_lines(html)
    body_start=0
    for i,line in enumerate(all_lines):
        if 'åç ç»é²çªå·/ç´å¥' in line or 'ç»é²çªå·/ç´å¥' in line:
            body_start=i; break
    body_end=len(all_lines)
    for i in range(body_start+1,len(all_lines)):
        if all_lines[i] in ('ä»ç¯æç¸¾','ã¢ã¼ã¿ã¼ã»ãã¼ãå¤æ´æã¯èµ¤ã§è¡¨ç¤ºããã¾ãã','PAGE TOP'):
            body_end=i; break
    lines=all_lines[body_start:body_end]
    lane_pos=[]
    for i,line in enumerate(lines):
        if not re.fullmatch(r'[1-6]',line): continue
        look=' '.join(lines[i:i+8])
        if re.search(r'\b\d{4}\s*/\s*(A1|A2|B1|B2)\b',look):
            lane_pos.append((int(line),i))
    out={}
    for idx,(lane,pos) in enumerate(lane_pos):
        nxt=lane_pos[idx+1][1] if idx+1<len(lane_pos) else len(lines)
        seg_lines=lines[pos:nxt]
        seg=' '.join(seg_lines)
        nums=re.findall(r'\d+\.\d+|\d+',seg)
        avg_idx=None
        for k,tok in enumerate(nums):
            if re.fullmatch(r'0\.\d{2}',tok): avg_idx=k; break
        out[lane]=(seg_lines, nums[avg_idx:] if avg_idx is not None else [])
    return out

def main():
    if not os.getenv('DATABASE_URL'): raise RuntimeError('DATABASE_URL ãå¿è¦ã§ãã')
    print(f'â diagnose_motor2_parser_pg.py VERSION {VERSION}',flush=True)
    print('READ_ONLY=1 DB_UPDATE=0 LINE=0 BUY=0',flush=True)
    ids=target_ids(); print(f'target_races={len(ids)}',flush=True)
    if not ids:
        print('RESULT=NO_TARGETS',flush=True); return
    labels={0:'avg_st',1:'national_win_rate',2:'national_place2_rate',3:'national_place3_rate',4:'local_win_rate',5:'local_place2_rate',6:'local_place3_rate',7:'motor_no',8:'motor_place2_rate',9:'motor_place3_rate',10:'boat_no',11:'boat_place2_rate',12:'boat_place3_rate'}
    for race_id in ids:
        parsed=repair._parse_race_id(race_id)
        if parsed is None:
            print(f'SKIP invalid race_id={race_id}',flush=True); continue
        date_str,venue_id,race_no=parsed
        print('\n'+'='*90,flush=True)
        print(f'RACE race_id={race_id} date={date_str} venue={venue_id} race_no={race_no}',flush=True)
        rows=db_entries(race_id)
        bad=set()
        for row in rows:
            m2=sf(row.get('motor_place2_rate'),None); lane=si(row.get('lane'))
            if m2 is not None and (m2<0 or m2>100):
                bad.add(lane)
                print(f"DB_BAD lane={lane} racer={row.get('racer_number')} motor_no={row.get('motor_no')} motor2={row.get('motor_place2_rate')} motor3={row.get('motor_place3_rate')} boat_no={row.get('boat_no')} boat2={row.get('boat_place2_rate')} boat3={row.get('boat_place3_rate')}",flush=True)
        print(f'DB_BAD_LANES={sorted(bad)}',flush=True)
        html=repair._fetch(repair._official_url('racelist',date_str,venue_id,race_no))
        if repair._looks_no_race(html):
            print('OFFICIAL_PAGE_NOT_AVAILABLE',flush=True); continue
        cur={si(x.get('lane')):x for x in repair.parse_entries(html or '',race_id)}
        segs=segments(html or '')
        for lane in sorted(bad):
            print(f'\n--- LANE {lane} ---',flush=True)
            c=cur.get(lane,{})
            print('CURRENT_PARSE '+f"racer={c.get('racer_number')} avg_st={c.get('avg_st')} nat_win={c.get('national_win_rate')} nat2={c.get('national_place2_rate')} nat3={c.get('national_place3_rate')} loc_win={c.get('local_win_rate')} loc2={c.get('local_place2_rate')} loc3={c.get('local_place3_rate')} motor_no={c.get('motor_no')} motor2={c.get('motor_place2_rate')} motor3={c.get('motor_place3_rate')} boat_no={c.get('boat_no')} boat2={c.get('boat_place2_rate')} boat3={c.get('boat_place3_rate')}",flush=True)
            seg_lines,seq=segs.get(lane,([],[]))
            print('SEGMENT_LINES:',flush=True)
            for i,line in enumerate(seg_lines): print(f'  L{i:02d}: {line}',flush=True)
            print('SEQ_FROM_AVG_ST:',flush=True)
            for i,tok in enumerate(seq[:30]): print(f"  [{i:02d}] {tok} {labels.get(i,'')}",flush=True)
    print('\nRESULT=PASS',flush=True)

if __name__=='__main__': main()