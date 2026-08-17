# -*- coding: utf-8 -*-
"""
save_k_day_results_pg.py

監査済み BOAT RACE公式Kファイル parser を使い、1日分だけDB保存する。
安全方針:
- TARGET_DATE 1日限定
- v2_result_entries は必要なら自動作成
- v2_results は既存行のみ UPDATE（INSERTしない）
- 既存 trifecta_ticket / payout は上書きしない
- finish_order / winning_method / raw のみ補完
- 保存前に全レース6艇・parser failure=0・duplicate=0を必須検証
- トランザクションで一括保存。失敗時ROLLBACK

環境変数:
  TARGET_DATE=2026-08-16
  CONFIRM_K_DB_WRITE=YES
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from typing import Any, Dict, List

from db_pg import fetch_all
import psycopg
from psycopg.types.json import Jsonb

# 監査済みparserをそのまま利用
import audit_k_day_all_pg as ka

VERSION="2026-08-17 k-day-db-save-v1"
TARGET_DATE=os.getenv("TARGET_DATE","2026-08-16")
CONFIRM=os.getenv("CONFIRM_K_DB_WRITE","")
DATABASE_URL=os.getenv("DATABASE_URL","")

DDL = """
create table if not exists v2_result_entries (
    race_id text not null,
    lane integer not null,
    racer_number integer,
    racer_name text,
    finish_position integer,
    finish_status text,
    motor_no integer,
    boat_no integer,
    exhibition_time double precision,
    start_course integer,
    start_timing double precision,
    start_status text,
    is_flying boolean not null default false,
    is_late boolean not null default false,
    race_time text,
    source text,
    raw jsonb,
    fetched_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (race_id,lane)
);
create index if not exists idx_v2_result_entries_racer
on v2_result_entries(racer_number);
"""

def cols(table:str)->set[str]:
    rows=fetch_all("""
      select column_name
      from information_schema.columns
      where table_schema='public' and table_name=%s
    """,(table,))
    return {str(x["column_name"]) for x in rows}

def build():
    text=ka.get_k_text(TARGET_DATE)
    sections=ka.split_venue_sections(text.splitlines())
    races=[]
    for s in sections:
        races.extend(ka.parse_section(s))

    ids=[x["race_id"] for x in races]
    failures=[(x["race_id"],z) for x in races for z in x["parse_failed_candidate_lines"]]
    incomplete=[x["race_id"] for x in races if len(x["entries"]) != 6]

    print("=== PREWRITE AUDIT ===",flush=True)
    print(f"venue_sections={len(sections)} races={len(races)} entry_rows={sum(len(x['entries']) for x in races)}",flush=True)
    print(f"incomplete6={len(incomplete)} parser_failures={len(failures)} duplicate_race_ids={len(ids)-len(set(ids))}",flush=True)

    if not races or incomplete or failures or len(ids)!=len(set(ids)):
        raise RuntimeError("PREWRITE AUDIT failed. DB書き込みを中止します。")
    return races

def main():
    print(f"✅ save_k_day_results_pg.py VERSION {VERSION}",flush=True)
    print(f"TARGET_DATE={TARGET_DATE}",flush=True)
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL が必要です")
    if CONFIRM != "YES":
        raise RuntimeError("安全装置: CONFIRM_K_DB_WRITE=YES を設定してください")

    races=build()

    result_cols=cols("v2_results")
    if not result_cols:
        raise RuntimeError("v2_results が存在しません")

    # 対象日の既存resultを確認。Kから新規結果行は作らない。
    wanted=[x["race_id"] for x in races]
    existing=fetch_all("select race_id from v2_results where race_id = any(%s)",(wanted,))
    existing_ids={str(x["race_id"]) for x in existing}
    missing=[rid for rid in wanted if rid not in existing_ids]
    print(f"existing_v2_results={len(existing_ids)}/{len(wanted)} missing={len(missing)}",flush=True)
    if missing:
        print("missing sample:",",".join(missing[:20]),flush=True)
        raise RuntimeError("v2_resultsに対象raceが不足しています。安全のため保存中止。")

    update_fields=[x for x in ("finish_order","winning_method","raw") if x in result_cols]
    print(f"v2_results supplement fields={update_fields}",flush=True)
    if not update_fields:
        raise RuntimeError("v2_results に補完対象カラムがありません")

    entry_count=0
    result_count=0

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(DDL)

                for race in races:
                    rid=race["race_id"]
                    for e in race["entries"]:
                        raw=dict(e)
                        cur.execute("""
                          insert into v2_result_entries(
                            race_id,lane,racer_number,racer_name,
                            finish_position,finish_status,motor_no,boat_no,
                            exhibition_time,start_course,start_timing,start_status,
                            is_flying,is_late,race_time,source,raw,fetched_at,updated_at
                          ) values(
                            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            'official_k_file',%s,now(),now()
                          )
                          on conflict(race_id,lane) do update set
                            racer_number=excluded.racer_number,
                            racer_name=excluded.racer_name,
                            finish_position=excluded.finish_position,
                            finish_status=excluded.finish_status,
                            motor_no=excluded.motor_no,
                            boat_no=excluded.boat_no,
                            exhibition_time=excluded.exhibition_time,
                            start_course=excluded.start_course,
                            start_timing=excluded.start_timing,
                            start_status=excluded.start_status,
                            is_flying=excluded.is_flying,
                            is_late=excluded.is_late,
                            race_time=excluded.race_time,
                            source=excluded.source,
                            raw=excluded.raw,
                            fetched_at=now(),
                            updated_at=now()
                        """,(
                            rid,e["lane"],e["racer_number"],e["racer_name"],
                            e["finish_position"],e["finish_status"],e["motor_no"],e["boat_no"],
                            e["exhibition_time"],e["start_course"],e["start_timing"],e["start_status"],
                            e["is_flying"],e["is_late"],e["race_time"],Jsonb(raw)
                        ))
                        entry_count += 1

                    sets=[]
                    vals=[]
                    if "finish_order" in update_fields:
                        sets.append("finish_order = coalesce(finish_order,%s)")
                        vals.append(race["finish_order"])
                    if "winning_method" in update_fields:
                        sets.append("winning_method = coalesce(winning_method,%s)")
                        vals.append(race["winning_method"])
                    if "raw" in update_fields:
                        # rawは既存値を壊さず、NULLのときだけK要約を入れる。
                        sets.append("raw = coalesce(raw,%s)")
                        vals.append(Jsonb({
                            "source":"official_k_file",
                            "race_title":race["race_title"],
                            "weather":race["weather"],
                            "wind_direction":race["wind_direction"],
                            "wind_speed_m":race["wind_speed_m"],
                            "wave_height_cm":race["wave_height_cm"],
                            "finish_order":race["finish_order"],
                            "winning_method":race["winning_method"],
                        }))
                    vals.append(rid)
                    cur.execute("update v2_results set "+", ".join(sets)+" where race_id=%s",vals)
                    result_count += cur.rowcount

            # COMMIT前のDB内監査
            with conn.cursor() as cur:
                cur.execute("""
                  select count(*) total,
                         count(*) filter(where finish_position is not null) normal_finish,
                         count(*) filter(where finish_position is null) accident
                  from v2_result_entries
                  where race_id = any(%s)
                """,(wanted,))
                audit=cur.fetchone()
                if not audit or int(audit[0]) != len(races)*6:
                    raise RuntimeError(f"POSTWRITE AUDIT failed: {audit}")
                print(f"POSTWRITE rows={audit[0]} normal_finish={audit[1]} accident={audit[2]}",flush=True)

    print("=== WRITE SUMMARY ===",flush=True)
    print(f"v2_result_entries_upsert={entry_count}",flush=True)
    print(f"v2_results_updated={result_count}",flush=True)
    print("RESULT=PASS",flush=True)

if __name__=="__main__":
    main()