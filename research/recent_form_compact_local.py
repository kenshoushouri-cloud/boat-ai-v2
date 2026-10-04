# -*- coding: utf-8 -*-
"""Local-only Recent Form compact preflight verifier.

Runs only against isolated GitHub Actions PostgreSQL databases. It never connects
to Railway directly. The Railway source is dumped read-only by the workflow.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import psycopg
from psycopg import sql

def _sha(rows) -> str:
    h=hashlib.sha256()
    for row in rows:
        h.update(("\t".join("" if v is None else str(v) for v in row)+"\n").encode())
    return h.hexdigest()

def capture(dsn: str, out: str) -> None:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set maintenance_work_mem='64MB'")
            cur.execute("select pg_database_size(current_database())")
            db_bytes=int(cur.fetchone()[0])

            cur.execute("""
              select tablename
              from pg_tables
              where schemaname='public'
              order by tablename
            """)
            tables=[r[0] for r in cur.fetchall()]
            counts={}
            for table in tables:
                cur.execute(sql.SQL("select count(*) from {}").format(sql.Identifier(table)))
                counts[table]=int(cur.fetchone()[0])

            cur.execute("""
              select table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,
                     coalesce(column_default,'')
              from information_schema.columns
              where table_schema='public'
              order by table_name,ordinal_position
            """)
            columns=cur.fetchall()

            cur.execute("""
              select c.relname,i.relname,pg_get_indexdef(i.oid)
              from pg_class c
              join pg_namespace n on n.oid=c.relnamespace
              join pg_index x on x.indrelid=c.oid
              join pg_class i on i.oid=x.indexrelid
              where n.nspname='public'
              order by c.relname,i.relname
            """)
            indexes=cur.fetchall()

            cur.execute("""
              select c.relname,con.conname,con.contype,pg_get_constraintdef(con.oid,true)
              from pg_constraint con
              join pg_class c on c.oid=con.conrelid
              join pg_namespace n on n.oid=c.relnamespace
              where n.nspname='public'
              order by c.relname,con.conname
            """)
            constraints=cur.fetchall()

            cur.execute("""
              select count(*)::bigint,
                     count(*) filter (
                       where recent_form is not null
                         and recent_form::text not in ('null','[]','{}','""','')
                     )::bigint,
                     coalesce(sum(pg_column_size(recent_form))
                       filter (where recent_form is not null),0)::bigint,
                     coalesce(bit_xor(hashtextextended((to_jsonb(e)-'recent_form')::text,0)),0)::bigint
              from v2_race_entries e
            """)
            entry_rows,recent_nonempty,recent_bytes,entry_xor=cur.fetchone()

            cur.execute("""
              select sequence_schema,sequence_name,data_type,start_value,minimum_value,
                     maximum_value,increment,cycle_option
              from information_schema.sequences
              where sequence_schema='public'
              order by sequence_name
            """)
            sequences=cur.fetchall()

    payload={
      "db_bytes":db_bytes,
      "tables":tables,
      "table_counts":counts,
      "columns_sha256":_sha(columns),
      "indexes_sha256":_sha(indexes),
      "constraints_sha256":_sha(constraints),
      "sequences_sha256":_sha(sequences),
      "entry_rows":int(entry_rows),
      "recent_nonempty":int(recent_nonempty),
      "recent_bytes":int(recent_bytes),
      "entry_nonrecent_xor":int(entry_xor),
    }
    Path(out).write_text(json.dumps(payload,sort_keys=True,indent=2)+"\n",encoding="utf-8")

def compact(dsn: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set maintenance_work_mem='64MB'")
            cur.execute("set synchronous_commit=off")
            cur.execute("""
              update v2_race_entries
                 set recent_form=null
               where recent_form is not null
                 and recent_form::text not in ('null','[]','{}','""','')
            """)
            changed=cur.rowcount
            print(f"LOCAL_RECENT_FORM_ROWS_NULLED={changed}",flush=True)
            cur.execute("vacuum (full, analyze) v2_race_entries")
            print("LOCAL_VACUUM_FULL_V2_RACE_ENTRIES=PASS",flush=True)

def verify(source: str, compacted: str, restored: str) -> None:
    s=json.loads(Path(source).read_text())
    c=json.loads(Path(compacted).read_text())
    r=json.loads(Path(restored).read_text())
    keys=["tables","table_counts","columns_sha256","indexes_sha256","constraints_sha256",
          "sequences_sha256","entry_rows","entry_nonrecent_xor"]
    mismatch=[k for k in keys if s[k]!=c[k] or c[k]!=r[k]]
    if mismatch:
        raise RuntimeError("parity_mismatch:"+",".join(mismatch))
    if s["recent_nonempty"] <= 0:
        raise RuntimeError("source_recent_form_not_present")
    if c["recent_nonempty"] != 0 or r["recent_nonempty"] != 0:
        raise RuntimeError("compact_recent_form_not_zero")
    if c["db_bytes"] >= s["db_bytes"]:
        raise RuntimeError("compact_db_not_smaller")
    saved=s["db_bytes"]-c["db_bytes"]
    print("LOCAL_PARITY=PASS",flush=True)
    print(f"SOURCE_LOCAL_DB_BYTES={s['db_bytes']}",flush=True)
    print(f"COMPACT_LOCAL_DB_BYTES={c['db_bytes']}",flush=True)
    print(f"VERIFY_LOCAL_DB_BYTES={r['db_bytes']}",flush=True)
    print(f"LOCAL_DB_BYTES_SAVED={saved}",flush=True)
    print(f"LOCAL_DB_MB_SAVED={saved/1_000_000:.3f}",flush=True)
    print(f"SOURCE_RECENT_FORM_NONEMPTY={s['recent_nonempty']}",flush=True)
    print(f"SOURCE_RECENT_FORM_BYTES={s['recent_bytes']}",flush=True)
    print("COMPACT_RECENT_FORM_NONEMPTY=0",flush=True)
    print("SCHEMA_INDEX_CONSTRAINT_SEQUENCE_PARITY=PASS",flush=True)
    print("ALL_PUBLIC_TABLE_ROW_COUNTS_PARITY=PASS",flush=True)
    print("V2_RACE_ENTRIES_NON_RECENT_FINGERPRINT_PARITY=PASS",flush=True)

def main():
    ap=argparse.ArgumentParser()
    sp=ap.add_subparsers(dest="mode",required=True)
    p=sp.add_parser("capture"); p.add_argument("--dsn",required=True); p.add_argument("--out",required=True)
    p=sp.add_parser("compact"); p.add_argument("--dsn",required=True)
    p=sp.add_parser("verify")
    p.add_argument("--source",required=True); p.add_argument("--compacted",required=True); p.add_argument("--restored",required=True)
    a=ap.parse_args()
    if a.mode=="capture": capture(a.dsn,a.out)
    elif a.mode=="compact": compact(a.dsn)
    else: verify(a.source,a.compacted,a.restored)

if __name__=="__main__":
    main()
