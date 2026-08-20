# -*- coding: utf-8 -*-
from __future__ import annotations
import os,subprocess,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Dict
from db_pg import fetch_all
JST=timezone(timedelta(hours=9));VERSION='2026-08-20 motor2-forward-stages-v5'
def flag(n,d):return os.getenv(n,d).strip().lower() not in {'0','false','no','off'}
RUN_CANDIDATE_SHADOW_EVAL=flag('RUN_CANDIDATE_SHADOW_EVAL','1');RUN_CANDIDATE_SHADOW_REPORT=flag('RUN_CANDIDATE_SHADOW_REPORT','1');RUN_N02_FORWARD_REPORT=flag('RUN_N02_FORWARD_REPORT','1');RUN_N02_VARIANT_FORWARD_REPORT=flag('RUN_N02_VARIANT_FORWARD_REPORT','1');RUN_EXHIBITION_SHADOW_EVAL=flag('RUN_EXHIBITION_SHADOW_EVAL','1');RUN_EXHIBITION_SHADOW_REPORT=flag('RUN_EXHIBITION_SHADOW_REPORT','1');RUN_MOTOR2_FORWARD_EVAL=flag('RUN_MOTOR2_FORWARD_EVAL','1');RUN_MOTOR2_FORWARD_REPORT=flag('RUN_MOTOR2_FORWARD_REPORT','1');SHADOW_EVAL_STRICT=flag('SHADOW_EVAL_STRICT','0')
def now():return datetime.now(JST).isoformat(timespec='seconds')
def run_stage(stage_no:int,stage_name:str,script_path:Path,env:Dict[str,str],strict=True):
    print('\n'+'='*80);print(f'STAGE {stage_no} START: {stage_name} at {now()}');print(f'SCRIPT: {script_path.name}');print('='*80)
    if not script_path.exists():
        msg=f'{script_path.name} ãè¦ã¤ããã¾ãã: {script_path}'
        if strict:raise FileNotFoundError(msg)
        print(f'â ï¸ {msg}');print(f'STAGE {stage_no} SKIPPED: {stage_name}');return False
    ce=os.environ.copy();ce.update(env);ce['PYTHONUNBUFFERED']='1';st=time.monotonic();r=subprocess.run([sys.executable,'-u',str(script_path)],cwd=str(script_path.parent),env=ce,text=True,capture_output=True,check=False);el=time.monotonic()-st
    print(f'--- STAGE {stage_no} OUTPUT: {stage_name} ---');print(r.stdout.rstrip() if r.stdout else '')
    if r.stderr:print(f'--- STAGE {stage_no} STDERR: {stage_name} ---');print(r.stderr.rstrip())
    print(f'STAGE {stage_no} END: {stage_name} returncode={r.returncode} elapsed={el:.1f}s at {now()}');print('='*80)
    if r.returncode!=0:
        msg=f'{stage_name} ãå¤±æãã¾ãããreturncode={r.returncode}'
        if strict:raise RuntimeError(msg)
        print(f'â ï¸ {msg}');return False
    return True
def targets(d):return [str(r.get('race_id')) for r in fetch_all('select race_id from v2_races where race_date=%s order by venue_id,race_no',(d,)) if r.get('race_id')]
def main():
    print(f'â run_nightly_results_pg.py VERSION {VERSION}');td=os.getenv('TARGET_DATE') or datetime.now(JST).strftime('%Y-%m-%d');print(f'TARGET_DATE={td}');print(f'RUN_MOTOR2_FORWARD_EVAL={RUN_MOTOR2_FORWARD_EVAL} RUN_MOTOR2_FORWARD_REPORT={RUN_MOTOR2_FORWARD_REPORT}');print('æ¬çªå¤å®ã»LINEéç¥ã»è³¼å¥å¦çã«ã¯å½±é¿ãã¾ããã')
    bd=Path(__file__).resolve().parent;common={'TARGET_DATE':td,'SNAPSHOT_LABEL':os.getenv('SNAPSHOT_LABEL','final_ab'),'SELECTOR_MODE':os.getenv('SELECTOR_MODE','ab'),'UNIT_YEN':os.getenv('UNIT_YEN','100')};ids=targets(td);print(f'nightly_target_races={len(ids)} (v2_raceså½æ¥éå¬åã®ã¿)')
    repair={**common,'REPAIR_START_DATE':td,'REPAIR_END_DATE':td,'REPAIR_RACE_IDS':','.join(ids),'REPAIR_DO_RACES':'0','REPAIR_DO_RESULTS':'1','REPAIR_DO_ODDS':'0','REPAIR_WORKERS':os.getenv('REPAIR_WORKERS',os.getenv('WORKERS','4')),'REPAIR_ODDS_WORKERS':os.getenv('REPAIR_ODDS_WORKERS',os.getenv('ODDS_WORKERS','1')),'REPAIR_SLEEP_SEC':os.getenv('REPAIR_SLEEP_SEC',os.getenv('SLEEP_SEC','0.1'))}
    if ids:run_stage(1,'å½æ¥çµæåå¾',bd/'repair_month_all_pg.py',repair,True)
    if RUN_CANDIDATE_SHADOW_EVAL:run_stage(2,'åè£ãã£ã«ã¿ã¼Shadowå½æ¥çµæè©ä¾¡',bd/'evaluate_candidate_filter_shadow_results_pg.py',{**common,'CANDIDATE_SHADOW_EVAL_ENABLED':os.getenv('CANDIDATE_SHADOW_EVAL_ENABLED','1'),'CANDIDATE_SHADOW_EVAL_REEVALUATE':os.getenv('CANDIDATE_SHADOW_EVAL_REEVALUATE','0')},False)
    if RUN_CANDIDATE_SHADOW_REPORT:run_stage(3,'åè£ãã£ã«ã¿ã¼Shadowç´¯ç©ã¬ãã¼ã',bd/'report_candidate_filter_shadow_performance_pg.py',{**common,'CANDIDATE_SHADOW_REPORT_DAYS':os.getenv('CANDIDATE_SHADOW_REPORT_DAYS','30'),'CANDIDATE_SHADOW_READY_MIN_EVALUATED':os.getenv('CANDIDATE_SHADOW_READY_MIN_EVALUATED','30'),'CANDIDATE_SHADOW_READY_MIN_RULE_EVALUATED':os.getenv('CANDIDATE_SHADOW_READY_MIN_RULE_EVALUATED','20'),'CANDIDATE_SHADOW_READY_MIN_ROI':os.getenv('CANDIDATE_SHADOW_READY_MIN_ROI','100'),'CANDIDATE_SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT':os.getenv('CANDIDATE_SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT','60')},False)
    if RUN_N02_FORWARD_REPORT:run_stage(4,'N02 Forwardå°ç¨ã¬ãã¼ã',bd/'report_n02_forward_performance_pg.py',{**common,'N02_FORWARD_START_DATE':os.getenv('N02_FORWARD_START_DATE','2026-08-18'),'N02_FORWARD_UNIT_YEN':os.getenv('N02_FORWARD_UNIT_YEN',os.getenv('UNIT_YEN','100'))},False)
    if RUN_EXHIBITION_SHADOW_EVAL:run_stage(5,'å±ç¤ºShadowå½æ¥çµæè©ä¾¡',bd/'evaluate_exhibition_shadow_results_pg.py',common,SHADOW_EVAL_STRICT)
    if RUN_EXHIBITION_SHADOW_REPORT:run_stage(6,'å±ç¤ºShadowç´¯ç©ã¬ãã¼ã',bd/'report_exhibition_shadow_performance_pg.py',{**common,'SHADOW_REPORT_DAYS':os.getenv('SHADOW_REPORT_DAYS','30'),'SHADOW_READY_MIN_ROWS':os.getenv('SHADOW_READY_MIN_ROWS','300'),'SHADOW_READY_MIN_BASE_CANDIDATES':os.getenv('SHADOW_READY_MIN_BASE_CANDIDATES','20'),'SHADOW_READY_MIN_SHADOW_CANDIDATES':os.getenv('SHADOW_READY_MIN_SHADOW_CANDIDATES','20'),'SHADOW_READY_MIN_ADDED':os.getenv('SHADOW_READY_MIN_ADDED','10'),'SHADOW_READY_MIN_REMOVED':os.getenv('SHADOW_READY_MIN_REMOVED','10'),'SHADOW_READY_MAX_ROI_DROP_PT':os.getenv('SHADOW_READY_MAX_ROI_DROP_PT','0')},SHADOW_EVAL_STRICT)
    if RUN_N02_VARIANT_FORWARD_REPORT:run_stage(7,'N02_WIND_LT4 Variant Forwardæ¯è¼ã¬ãã¼ã',bd/'report_n02_windlt4_variants_forward_pg.py',{**common,'N02_VARIANT_FORWARD_START_DATE':os.getenv('N02_VARIANT_FORWARD_START_DATE','2026-08-19'),'N02_VARIANT_UNIT_YEN':os.getenv('N02_VARIANT_UNIT_YEN',os.getenv('UNIT_YEN','100')),'N02_VARIANT_REVIEW_TARGETS':os.getenv('N02_VARIANT_REVIEW_TARGETS','10,30,50,100')},False)
    if RUN_MOTOR2_FORWARD_EVAL:run_stage(8,'Motor2 Forward Shadowå½æ¥çµæè©ä¾¡',bd/'evaluate_v24_motor2_forward_shadow_pg.py',{**common,'MOTOR2_EVAL_UNIT_YEN':os.getenv('MOTOR2_EVAL_UNIT_YEN',os.getenv('UNIT_YEN','100')),'RUN_CLASS':'','WINDOW_NAME':'','SNAPSHOT_KEY':''},False)
    if RUN_MOTOR2_FORWARD_REPORT:run_stage(9,'Motor2 Forward PRE/FINALç´¯ç©æ¯è¼ã¬ãã¼ã',bd/'report_v24_motor2_forward_performance_pg.py',{**common,'MOTOR2_FORWARD_REPORT_START_DATE':os.getenv('MOTOR2_FORWARD_REPORT_START_DATE','2026-08-20'),'MOTOR2_FORWARD_UNIT_YEN':os.getenv('MOTOR2_FORWARD_UNIT_YEN',os.getenv('UNIT_YEN','100')),'MOTOR2_FORWARD_REVIEW_TARGETS':os.getenv('MOTOR2_FORWARD_REVIEW_TARGETS','10,30,50,100')},False)
    print('\n=== nightly results + candidate/N02/N02-variant/exhibition/Motor2 shadow evaluation/report å®äº ===')
if __name__=='__main__':main()