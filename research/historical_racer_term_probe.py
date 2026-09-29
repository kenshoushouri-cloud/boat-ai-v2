# -*- coding: utf-8 -*-
"""Inspect official racer-term LZH members and fixed-width record shape."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
import lhafile

ROOT=Path("historical-racer-term-official")


def inspect_archive(path: Path) -> dict:
    arc=lhafile.Lhafile(str(path))
    names=arc.namelist()
    if not names:
        raise RuntimeError(f"no members: {path.name}")
    members=[]
    for name in names:
        data=arc.read(name)
        text=data.decode("cp932")
        lines=[line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
        lengths=Counter(len(line) for line in lines)
        members.append({
            "name":str(name),
            "bytes":len(data),
            "line_count":len(lines),
            "line_length_counts":dict(sorted(lengths.items())),
            "sample_lines":lines[:5],
            "sample_fields":[
                {
                    "racer_number":line[0:4],
                    "class_raw":line[29:31],
                    "win_raw":line[48:52],
                    "place2_raw":line[52:56],
                    "avg_st_raw":line[69:72],
                }
                for line in lines[:5]
            ],
        })
    return {"archive":path.name,"members":members}


def main()->None:
    rows=[inspect_archive(p) for p in sorted(ROOT.glob("fan*.lzh"))]
    if len(rows)!=3:
        raise SystemExit(f"expected 3 archives, got {len(rows)}")
    payload={"contract":"BOATRACE_RACER_TERM_STRUCTURE_PROBE_V1","archives":rows}
    Path("historical-racer-term-inspection.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    for row in rows:
        for m in row["members"]:
            print(
                f"RACER_TERM_STRUCTURE archive={row['archive']} member={m['name']} "
                f"lines={m['line_count']} lengths={m['line_length_counts']}",
                flush=True,
            )
            for i,line in enumerate(m["sample_lines"],1):
                fields=m["sample_fields"][i-1]
                print(f"RACER_TERM_SAMPLE_FIELDS archive={row['archive']} n={i} fields={fields}",flush=True)
    print("RACER_TERM_STRUCTURE_RESULT=PASS",flush=True)


if __name__=="__main__":
    main()
