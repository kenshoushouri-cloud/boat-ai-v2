# -*- coding: utf-8 -*-
"""Result-blind read-only inventory of unused current-V4 race-entry information."""
from __future__ import annotations
import json, os
from datetime import date
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

START=date(2025,7,1)
END=date(2026,9,22)
OUT=Path(os.getenv("V4_UNUSED_ENTRY_OUTPUT_JSON","v4-unused-entry-inventory.json"))
VERSION="2026-09-27-v4-unused-entry-inventory-v1"

USED_BY_V4={
    "racer_class":"base",
    "national_win_rate":"base",
    "national_place2_rate":"base",
    "local_place2_rate":"base",
    "avg_st":"base",
    "motor_place2_rate":"motor2",
}
FIELDS=[
    "national_place3_rate","local_win_rate","local_place3_rate",
    "motor_place3_rate","boat_place2_rate","boat_place3_rate",
    "f_count","l_count","branch","origin","motor_no","boat_no",
]
STRONG_CAPTURE_COLUMNS=("source_fetched_at","fetched_at","captured_at","snapshot_at","source_captured_at")
WEAK_CAPTURE_COLUMNS=("created_at","updated_at")

def main():
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db,row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("set transaction read only")
                cur.execute("""select column_name,data_type,udt_name
                               from information_schema.columns
                               where table_schema='public' and table_name='v2_race_entries'
                               order by ordinal_position""")
                schema=list(cur.fetchall())
                cols={str(r["column_name"]):dict(r) for r in schema}
                strong=next((c for c in STRONG_CAPTURE_COLUMNS if c in cols),None)
                weak=[c for c in WEAK_CAPTURE_COLUMNS if c in cols]

                cur.execute("""select count(*) rows,
                                      count(distinct e.race_id) races,
                                      count(distinct r.race_date) days
                               from v2_race_entries e join v2_races r on r.race_id=e.race_id
                               where r.race_date between %s and %s""",(START,END))
                base=dict(cur.fetchone() or {})

                cur.execute("""select count(*) races from (
                                 select e.race_id
                                 from v2_race_entries e join v2_races r on r.race_id=e.race_id
                                 where r.race_date between %s and %s
                                 group by e.race_id
                                 having count(*)=6 and count(distinct e.lane)=6
                               ) q""",(START,END))
                exact6=int((cur.fetchone() or {}).get("races") or 0)

                stats={}
                for field in FIELDS:
                    if field not in cols:
                        stats[field]={"exists":False}
                        continue
                    cur.execute(f"""select count(*) filter (where e."{field}" is not null) nonnull_rows,
                                          count(distinct e.race_id) filter (where e."{field}" is not null) races_any
                                   from v2_race_entries e join v2_races r on r.race_id=e.race_id
                                   where r.race_date between %s and %s""",(START,END))
                    row=dict(cur.fetchone() or {})
                    cur.execute(f"""select count(*) races from (
                                      select e.race_id
                                      from v2_race_entries e join v2_races r on r.race_id=e.race_id
                                      where r.race_date between %s and %s
                                      group by e.race_id
                                      having count(*)=6 and count(distinct e.lane)=6
                                         and count(*) filter (where e."{field}" is not null)=6
                                    ) q""",(START,END))
                    full6=int((cur.fetchone() or {}).get("races") or 0)
                    item={
                        "exists":True,
                        "udt_name":str(cols[field]["udt_name"]),
                        "nonnull_rows":int(row.get("nonnull_rows") or 0),
                        "row_coverage_percent":round(100.0*int(row.get("nonnull_rows") or 0)/int(base.get("rows") or 1),6),
                        "races_with_any_nonnull":int(row.get("races_any") or 0),
                        "full6_races":full6,
                        "full6_of_exact6_percent":round(100.0*full6/exact6,6) if exact6 else 0.0,
                    }
                    if str(cols[field]["data_type"]) in {"smallint","integer","bigint","numeric","real","double precision","decimal"}:
                        cur.execute(f"""select min(e."{field}") min_value,max(e."{field}") max_value,
                                              count(distinct e."{field}") distinct_values
                                       from v2_race_entries e join v2_races r on r.race_id=e.race_id
                                       where r.race_date between %s and %s and e."{field}" is not null""",(START,END))
                        n=dict(cur.fetchone() or {})
                        item["min_value"]=str(n.get("min_value")) if n.get("min_value") is not None else None
                        item["max_value"]=str(n.get("max_value")) if n.get("max_value") is not None else None
                        item["distinct_values"]=int(n.get("distinct_values") or 0)
                    stats[field]=item

    for field,item in stats.items():
        if not item.get("exists"):
            item["readiness"]="ABSENT"
        elif int(item.get("nonnull_rows") or 0)==0:
            item["readiness"]="EMPTY"
        elif strong is None:
            item["readiness"]="DATA_PRESENT_0815_ROW_TIMING_UNPROVEN"
        else:
            item["readiness"]="DATA_PRESENT_CAPTURE_COLUMN_EXISTS_NEEDS_TIMESTAMP_AUDIT"

    report={
        "version":VERSION,
        "period":[START.isoformat(),END.isoformat()],
        "safety":{"transaction_read_only":True,"outcome_read":False,"odds_read":False,"db_write":False,"purchase_action":False},
        "current_v4_consumed_entry_fields":USED_BY_V4,
        "entry_schema":{"strong_capture_column":strong,"weak_capture_columns":weak},
        "population":{"rows":int(base.get("rows") or 0),"races":int(base.get("races") or 0),"days":int(base.get("days") or 0),"exact6_races":exact6},
        "fields":stats,
        "classification":"INVENTORY_COMPLETE_RESULT_BLIND",
    }
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"UNUSED_ENTRY_ROWS={report['population']['rows']}",flush=True)
    print(f"UNUSED_ENTRY_EXACT6_RACES={exact6}",flush=True)
    print(f"UNUSED_ENTRY_STRONG_CAPTURE_COLUMN={strong or 'NONE'}",flush=True)
    for field in FIELDS:
        item=stats[field]
        print(f"UNUSED_ENTRY_FIELD={field} coverage={item.get('row_coverage_percent')} full6={item.get('full6_of_exact6_percent')} readiness={item.get('readiness')}",flush=True)
    print("UNUSED_ENTRY_OUTCOME_READ=0",flush=True)
    print("RESULT=PASS_READ_ONLY",flush=True)

if __name__=="__main__":
    main()
