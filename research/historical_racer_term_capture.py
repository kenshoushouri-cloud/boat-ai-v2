# -*- coding: utf-8 -*-
"""Capture official BOAT RACE racer term archives required for 2025-07 onward."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

JST=timezone(timedelta(hours=9))
BASE="https://boatrace.jp/static_extra/pc_static/download/data/kibetsu"
FILES=[
    {
        "term":"2025_H2",
        "applies_from":"2025-07-01",
        "applies_through":"2025-12-31",
        "name":"fan2504.lzh",
    },
    {
        "term":"2026_H1",
        "applies_from":"2026-01-01",
        "applies_through":"2026-06-30",
        "name":"fan2510.lzh",
    },
    {
        "term":"2026_H2",
        "applies_from":"2026-07-01",
        "applies_through":"2026-12-31",
        "name":"fan2604.lzh",
    },
]
UA="boat-ai-v2-historical-racer-term/1.0"


def sha256(data: bytes)->str:
    return hashlib.sha256(data).hexdigest()


def fetch(url:str)->bytes:
    req=Request(url,headers={"User-Agent":UA})
    with urlopen(req,timeout=30) as resp:
        if int(getattr(resp,"status",200) or 200)!=200:
            raise RuntimeError(f"HTTP {resp.status}")
        return resp.read()


def main()->None:
    out=Path("historical-racer-term-official")
    out.mkdir(parents=True,exist_ok=True)
    rows=[]
    print("RACER_TERM_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0",flush=True)
    for spec in FILES:
        url=f"{BASE}/{spec['name']}"
        status="ok"; detail=None; data=b""
        try:
            data=fetch(url)
            if len(data)<32:
                raise RuntimeError("archive too small")
            (out/spec["name"]).write_bytes(data)
        except Exception as exc:
            status="error"; detail=repr(exc)
        rows.append({
            **spec,
            "url":url,
            "status":status,
            "bytes":len(data),
            "sha256":sha256(data) if data else None,
            "fetched_at_jst":datetime.now(JST).isoformat(),
            "role":"fixed_term_prerace_racer_stats",
            "detail":detail,
        })
        print(f"RACER_TERM_FETCH term={spec['term']} status={status} bytes={len(data)}",flush=True)
    payload={
        "contract":"BOATRACE_OFFICIAL_RACER_TERM_CAPTURE_V1",
        "source":"BOAT_RACE_OFFICIAL",
        "historical_evidence_class":"reconstructed_predeadline_assumption",
        "db_write":False,
        "line":False,
        "buy":False,
        "production_change":False,
        "files":rows,
    }
    (out/"manifest.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    ok=sum(r["status"]=="ok" for r in rows)
    if ok!=len(FILES):
        raise SystemExit(f"only {ok}/{len(FILES)} racer term archives captured")
    print("RACER_TERM_RESULT=PASS_ALL_THREE",flush=True)


if __name__=="__main__":
    main()
