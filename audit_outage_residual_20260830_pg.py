# -*- coding: utf-8 -*-
"""Read-only residual audit for the fixed 2026-08-30 outage repair.

Purpose:
- identify the exact races that still have zero trifecta odds rows
- identify official beforeinfo races whose exhibition parse has fewer than 6 lanes
- compare those official rows with historical exhibition snapshot counts

No DB writes. No PRE/LINE/FINAL/model/Shadow/Forward execution.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from db_pg import fetch_all
import v21_realtime_collector_pg as v21

VERSION = "2026-08-31 outage-residual-audit-v1"
TARGET_DATE = "2026-08-30"
START_KEY = "20260830"
END_KEY = "20260831"
WORKERS = 4


def as_int(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def load_races() -> List[Dict[str, Any]]:
    return fetch_all(
        """
        select race_id, venue_id, venue_code, race_no
        from v2_races
        where race_date=%s
        order by venue_id, race_no
        """,
        (TARGET_DATE,),
    )


def load_odds_counts() -> Dict[str, int]:
    rows = fetch_all(
        """
        with oc as (
            select race_id, count(distinct ticket) as ticket_count
            from v2_odds_trifecta
            where race_id >= %s and race_id < %s
            group by race_id
        )
        select r.race_id, coalesce(oc.ticket_count,0) as ticket_count
        from v2_races r
        left join oc on oc.race_id=r.race_id
        where r.race_date=%s
        order by r.venue_id, r.race_no
        """,
        (START_KEY, END_KEY, TARGET_DATE),
    )
    return {str(x["race_id"]): as_int(x.get("ticket_count")) for x in rows}


def load_hist_exhibition_counts() -> Dict[str, int]:
    rows = fetch_all(
        """
        select race_id, count(*) as n
        from v2_realtime_exhibition_snapshots
        where race_id >= %s and race_id < %s
          and snapshot_label='historical'
        group by race_id
        order by race_id
        """,
        (START_KEY, END_KEY),
    )
    return {str(x["race_id"]): as_int(x.get("n")) for x in rows}


def probe_beforeinfo(race: Dict[str, Any]) -> Dict[str, Any]:
    rid = str(race["race_id"])
    venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
    race_no = as_int(race.get("race_no"))
    try:
        url = v21._official_url("beforeinfo", TARGET_DATE, venue, race_no)
        html = v21._fetch(url)
        if not html:
            return {"race_id": rid, "status": "FETCH_MISSING", "count": 0, "lanes": []}
        parsed = v21.parse_exhibition(html)
        lanes = sorted(
            {
                as_int(x.get("lane"))
                for x in parsed
                if as_int(x.get("lane")) in range(1, 7)
            }
        )
        return {
            "race_id": rid,
            "status": "OK",
            "count": len(lanes),
            "lanes": lanes,
        }
    except Exception as exc:
        return {
            "race_id": rid,
            "status": "ERROR",
            "count": 0,
            "lanes": [],
            "error": f"{type(exc).__name__}:{exc}",
        }


def main() -> None:
    print(f"OUTAGE_RESIDUAL_VERSION={VERSION}", flush=True)
    print(f"OUTAGE_RESIDUAL_DATE={TARGET_DATE}", flush=True)
    print(
        "OUTAGE_RESIDUAL_POLICY=read_only_db_select_official_http_get_no_line_no_model_no_shadow_forward",
        flush=True,
    )

    races = load_races()
    odds = load_odds_counts()
    hist = load_hist_exhibition_counts()

    zero = [rid for rid, n in odds.items() if n == 0]
    partial = [rid for rid, n in odds.items() if n not in (0, 24, 60, 120)]
    complete = [rid for rid, n in odds.items() if n in (24, 60, 120)]

    print(f"OUTAGE_RESIDUAL_DB_RACES={len(races)}", flush=True)
    print(
        "OUTAGE_RESIDUAL_ODDS="
        f"zero:{len(zero)} partial:{len(partial)} complete:{len(complete)}",
        flush=True,
    )
    print(
        "OUTAGE_RESIDUAL_ZERO_ODDS="
        f"count:{len(zero)} races:{','.join(zero) if zero else 'none'}",
        flush=True,
    )
    print(
        "OUTAGE_RESIDUAL_PARTIAL_ODDS="
        f"count:{len(partial)} races:{','.join(partial) if partial else 'none'}",
        flush=True,
    )

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(probe_beforeinfo, race) for race in races]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda x: str(x["race_id"]))
    ok = [x for x in results if x["status"] == "OK"]
    missing = [x for x in results if x["status"] == "FETCH_MISSING"]
    errors = [x for x in results if x["status"] == "ERROR"]
    incomplete = [x for x in ok if as_int(x.get("count")) != 6]
    official_rows = sum(as_int(x.get("count")) for x in ok)
    db_rows = sum(hist.values())

    print(
        "OUTAGE_RESIDUAL_BEFOREINFO="
        f"http_ok:{len(ok)} fetch_missing:{len(missing)} errors:{len(errors)} "
        f"official_exhibition_rows:{official_rows} incomplete_races:{len(incomplete)}",
        flush=True,
    )
    print(
        "OUTAGE_RESIDUAL_HIST_EXHIBITION="
        f"db_rows:{db_rows} official_rows:{official_rows} delta:{official_rows-db_rows}",
        flush=True,
    )

    pattern_delta = 0
    pattern_matches = bool(incomplete)
    for x in incomplete:
        rid = str(x["race_id"])
        official_count = as_int(x.get("count"))
        db_count = as_int(hist.get(rid))
        lanes = ",".join(str(v) for v in x.get("lanes") or []) or "none"
        pattern_delta += official_count - db_count
        if not (0 < official_count < 6 and db_count == 0):
            pattern_matches = False
        print(
            "OUTAGE_RESIDUAL_EXHIBITION_RACE="
            f"race:{rid} official_count:{official_count} official_lanes:{lanes} "
            f"db_hist_count:{db_count}",
            flush=True,
        )

    print(
        "OUTAGE_RESIDUAL_PARTIAL_DISCARD_PATTERN="
        f"matches:{str(pattern_matches).lower()} delta:{pattern_delta}",
        flush=True,
    )
    if missing:
        print(
            "OUTAGE_RESIDUAL_FETCH_MISSING="
            f"count:{len(missing)} races:{','.join(str(x['race_id']) for x in missing)}",
            flush=True,
        )
    if errors:
        print(
            "OUTAGE_RESIDUAL_ERRORS="
            f"count:{len(errors)} races:{','.join(str(x['race_id']) for x in errors)}",
            flush=True,
        )

    result = "PASS_READ_ONLY" if not missing and not errors else "CHECK_HTTP"
    print(f"OUTAGE_RESIDUAL_RESULT={result}", flush=True)


if __name__ == "__main__":
    main()
