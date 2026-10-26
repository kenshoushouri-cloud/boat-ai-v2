#!/usr/bin/env python3
"""V5 official exhibition classification diagnostic: no DB writes, no BUY.

--race-id optional: when omitted, choose up to 2 upcoming eligible races
using current physical V5 stage (READ ONLY) with 6 entries, deadline in 5–45m.
Fetch the single exact official beforeinfo page per race and compare structural
classifier with time-shaped evidence found strictly in lane-labelled rows.
Do not infer missing exhibition times or backfill any actual snapshots.
"""
import argparse
import re
from psycopg import connect
from bs4 import BeautifulSoup
from historical_beforeinfo_parser_v3 import (
    inspect_exhibition_time_page, _direct_cells, _lane_from_cells,
    _parse_primary_boat_rows,
)
from v5.native_official_realtime_stage_pg import official_page, race_parts

def candidates():
    with connect("postgresql:///railway", connect_timeout=5,
                 autocommit=True) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='6000ms'")
                cur.execute("""
                    SELECT r.race_id FROM boat_data_stage.races r
                    WHERE r.race_date =
                          (now() AT TIME ZONE 'Asia/Tokyo')::date
                      AND r.deadline_at::timestamptz
                          BETWEEN now()+interval '5 minutes'
                              AND now()+interval '45 minutes'
                      AND (SELECT count(*) FROM boat_data_stage.entries e
                           WHERE e.race_id=r.race_id)=6
                    ORDER BY r.deadline_at::timestamptz,r.race_id LIMIT 2
                """)
                return [z[0] for z in cur.fetchall()]

def summarize(rid):
    try:
        before, observed, digest = official_page("beforeinfo", rid)
        evidence = inspect_exhibition_time_page(before)
        soup = BeautifulSoup(before, "html.parser")
        primary = _parse_primary_boat_rows(soup)
        candidates_by_lane = {}
        td_counts = {}
        for tbody in soup.select("tbody.is-fs12"):
            trs = tbody.find_all("tr", recursive=False)
            if not trs:
                continue
            cells = _direct_cells(trs[0])
            lane = _lane_from_cells(cells)
            if lane is None:
                continue
            td_counts[lane] = len(cells)
            # Only time-shaped values in the structured lane's own cells.
            hits = [f"{i}:{v}" for i,v in enumerate(cells)
                    if re.fullmatch(r"[67][.][0-9]{2}", v)]
            candidates_by_lane[lane] = hits[:4]
        lines = [
            f"RACE={rid} observation={observed.isoformat()} hash8={digest[:8]}",
            "PARSE status="+str(evidence.get("status"))+
            " source="+str(evidence.get("source"))+
            " valid="+str(evidence.get("valid_time_count"))+
            " lanes="+str(evidence.get("lanes")),
            "STRUCTURED_LANES="+str(sorted(td_counts))+
            " TIME_PARSED_LANES="+str(sorted(primary)),
            "TIME_SHAPED_CELLS="+str(candidates_by_lane),
            "CELL_COUNTS="+str(td_counts),
        ]
        if (evidence.get("status")=="official_absent" and
                any(candidates_by_lane.values())):
            lines.append("VERDICT=POSSIBLE_EXHIBITION_PARSER_MISMATCH_NO_WRITES")
        elif evidence.get("status")=="official_absent":
            lines.append("VERDICT=NO_TIME_SHAPED_EVIDENCE_IN_STRUCTURED_LANES_NO_WRITES")
        elif evidence.get("status")=="complete" and
              evidence.get("source")=="primary_structured_rows"):
            lines.append("VERDICT=OFFICIAL_STRUCTURED_SIX_LANES_VISIBLE_NO_WRITES")
        else:
            lines.append("VERDICT=OFFICIAL_PARTIAL_OR_UNVERIFIED_NO_WRITES")
        print(*lines, sep=chr(10), flush=True)
    except Exception as exc:
        print("DIAGNOSTIC_HOLD "+rid+" "+type(exc).__name__+":"+
              str(exc).splitlines()[0][:150], flush=True)
        return False
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--race-id")
    args=ap.parse_args()
    if args.race_id:
        race_parts(args.race_id)
        targets=[args.race_id]
    else:
        targets=candidates()
    if not targets:
        print("NO_CURRENT_UPCOMING_STAGE_RACES_FOR_DIAGNOSIS_NO_WRITES")
        return 0
    print("V5_OFFICIAL_EXHIBITION_DIAGNOSIS_BEGIN_READ_ONLY_NO_BUY")
    success=all(summarize(rid) for rid in targets)
    print("V5_OFFICIAL_EXHIBITION_DIAGNOSIS_COMPLETE_NO_WRITES_NO_BUY")
    return 0 if success else 2

if __name__=="__main__":
    raise SystemExit(main())
