# -*- coding: utf-8 -*-
"""Load official BOAT RACE racer-term fixed-width files into a provenance table.

This table is independent from v2_race_entries. It is for historical
corroboration / gap filling only after an explicit agreement audit.
"""
from __future__ import annotations

import hashlib
import io
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import lhafile
import requests

from db_pg import execute, upsert_rows

JST=timezone(timedelta(hours=9))
BASE="https://boatrace.jp/static_extra/pc_static/download/data/kibetsu"
CLASS_MAP={"B2":1,"B1":2,"A2":3,"A1":4}
TERMS=[
    ("2025_H2","2025-07-01","2025-12-31","fan2504.lzh"),
    ("2026_H1","2026-01-01","2026-06-30","fan2510.lzh"),
    ("2026_H2","2026-07-01","2026-12-31","fan2604.lzh"),
]
EVIDENCE_CLASS="historical_fixed_term_prerace_reference"
PARSER_VERSION="fixed403_v1"

DDL=[
"""create table if not exists v2_historical_racer_term_reconstruction (
  term text not null,
  applies_from date not null,
  applies_through date not null,
  racer_number integer not null,
  racer_name text,
  branch text,
  racer_class integer,
  racer_class_text text,
  national_win_rate numeric,
  national_place2_rate numeric,
  avg_st numeric,
  source text not null,
  source_url text not null,
  source_archive_sha256 text not null,
  source_record_sha256 text not null,
  fetched_at timestamptz not null,
  evidence_class text not null,
  parser_version text not null,
  primary key(term,racer_number)
);""",
"create index if not exists ix_v2_hist_racer_term_apply on v2_historical_racer_term_reconstruction(applies_from,applies_through);",
"create index if not exists ix_v2_hist_racer_term_racer on v2_historical_racer_term_reconstruction(racer_number);",
]


def digits_scaled(raw:str,divisor:float):
    s=raw.strip()
    return (int(s)/divisor) if s.isdigit() else None


def parse_line(line:str)->dict:
    if len(line)!=403:
        raise ValueError(f"unexpected fixed-width length {len(line)}")
    racer_raw=line[0:4]
    if not racer_raw.isdigit():
        raise ValueError("racer_number is not numeric")
    cls=line[29:31].strip()
    if cls not in CLASS_MAP:
        raise ValueError(f"unexpected class {cls!r}")
    return {
      "racer_number":int(racer_raw),
      "racer_name":line[4:12].replace("　","").strip(),
      "branch":line[27:29].strip(),
      "racer_class":CLASS_MAP[cls],
      "racer_class_text":cls,
      "national_win_rate":digits_scaled(line[48:52],100.0),
      "national_place2_rate":digits_scaled(line[52:56],10.0),
      "avg_st":digits_scaled(line[69:72],100.0),
      "source_record_sha256":hashlib.sha256(line.encode("cp932")).hexdigest(),
    }


def fetch_archive(url:str)->bytes:
    r=requests.get(url,timeout=30,headers={"User-Agent":"boat-ai-v2-historical-racer-term-db/1.0"})
    r.raise_for_status()
    if len(r.content)<1000:
        raise RuntimeError("term archive unexpectedly small")
    return r.content


def extract_lines(data:bytes)->list[str]:
    with tempfile.TemporaryDirectory(prefix="racer_term_") as td:
        p=Path(td)/"term.lzh"
        p.write_bytes(data)
        arc=lhafile.Lhafile(str(p))
        names=arc.namelist()
        if len(names)!=1:
            raise RuntimeError(f"expected one archive member, got {names}")
        text=arc.read(names[0]).decode("cp932")
    return [x.rstrip("\r\n") for x in text.splitlines() if x.strip()]


def main()->None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL required")
    for sql in DDL:
        execute(sql)
    print("RACER_TERM_CANONICAL_OVERWRITE=0 RESULT_READ=0 ODDS_READ=0 LINE=0 BUY=0",flush=True)
    total=0
    fetched_at=datetime.now(JST).isoformat()
    for term,start,end,name in TERMS:
        url=f"{BASE}/{name}"
        data=fetch_archive(url)
        archive_sha=hashlib.sha256(data).hexdigest()
        lines=extract_lines(data)
        rows=[]
        for line in lines:
            row=parse_line(line)
            row.update({
              "term":term,
              "applies_from":start,
              "applies_through":end,
              "source":"BOAT_RACE_OFFICIAL_RACER_TERM",
              "source_url":url,
              "source_archive_sha256":archive_sha,
              "fetched_at":fetched_at,
              "evidence_class":EVIDENCE_CLASS,
              "parser_version":PARSER_VERSION,
            })
            rows.append(row)
        saved=upsert_rows("v2_historical_racer_term_reconstruction",rows,["term","racer_number"])
        total+=saved
        print(f"RACER_TERM_DB term={term} lines={len(lines)} saved={saved} sha256={archive_sha}",flush=True)
    print(f"RACER_TERM_DB_TOTAL_SAVED={total}",flush=True)
    print("RACER_TERM_DB_RESULT=PASS",flush=True)


if __name__=="__main__":
    main()
