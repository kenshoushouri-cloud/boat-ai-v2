# -*- coding: utf-8 -*-
"""Read-only residual audit for the fixed 2026-08-30 outage repair.

Compares:
- Railway PostgreSQL residual odds / historical exhibition rows
- current official beforeinfo pages
- official BOAT RACE K result source
- current official odds3t pages for zero-odds races

No DB writes. No PRE/LINE/FINAL/model/Shadow/Forward execution.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Set, Tuple

from db_pg import fetch_all
import audit_k_day_all_pg as kday
import repair_month_all_pg as repair
import v21_realtime_collector_pg as v21

VERSION = "2026-08-31 outage-residual-audit-v2-k-source"
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


def load_hist_exhibition_lanes() -> Dict[str, Set[int]]:
    rows = fetch_all(
        """
        select race_id, lane
        from v2_realtime_exhibition_snapshots
        where race_id >= %s and race_id < %s
          and snapshot_label='historical'
        order by race_id, lane
        """,
        (START_KEY, END_KEY),
    )
    out: Dict[str, Set[int]] = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        lane = as_int(row.get("lane"))
        if rid and lane in range(1, 7):
            out.setdefault(rid, set()).add(lane)
    return out


def probe_beforeinfo(race: Dict[str, Any]) -> Dict[str, Any]:
    rid = str(race["race_id"])
    venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
    race_no = as_int(race.get("race_no"))
    try:
        url = v21._official_url("beforeinfo", TARGET_DATE, venue, race_no)
        html = v21._fetch(url)
        if not html:
            return {"race_id": rid, "status": "FETCH_MISSING", "lanes": []}
        parsed = v21.parse_exhibition(html)
        lanes = sorted({
            as_int(x.get("lane"))
            for x in parsed
            if as_int(x.get("lane")) in range(1, 7)
        })
        return {"race_id": rid, "status": "OK", "lanes": lanes}
    except Exception as exc:
        return {
            "race_id": rid,
            "status": "ERROR",
            "lanes": [],
            "error": f"{type(exc).__name__}:{exc}",
        }


def load_k_source() -> Tuple[Dict[str, Set[int]], Dict[str, Set[int]], Dict[str, str], int]:
    kday.TARGET_DATE = TARGET_DATE
    text = kday.get_k_text(TARGET_DATE)
    sections = kday.split_venue_sections(text.splitlines())
    races: List[Dict[str, Any]] = []
    for section in sections:
        races.extend(kday.parse_section(section))

    available: Dict[str, Set[int]] = {}
    unavailable: Dict[str, Set[int]] = {}
    statuses: Dict[str, str] = {}

    for race in races:
        rid = str(race["race_id"])
        avail: Set[int] = set()
        all_lanes: Set[int] = set()
        status_parts: List[str] = []
        for entry in race.get("entries") or []:
            lane = as_int(entry.get("lane"))
            if lane not in range(1, 7):
                continue
            all_lanes.add(lane)
            if entry.get("exhibition_time") is not None:
                avail.add(lane)
            status_parts.append(f"{lane}:{entry.get('finish_status') or '-'}")
        available[rid] = avail
        unavailable[rid] = all_lanes - avail
        statuses[rid] = ",".join(status_parts)

    return available, unavailable, statuses, len(races)


def probe_zero_odds(race: Dict[str, Any]) -> Dict[str, Any]:
    rid = str(race["race_id"])
    venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
    race_no = as_int(race.get("race_no"))
    try:
        url = repair._official_url("odds3t", TARGET_DATE, venue, race_no)
        html = repair._fetch(url)
        if not html:
            return {"race_id": rid, "html": "missing", "parsed": 0}
        rows = repair.parse_odds3t(html, rid)
        tickets = {str(x.get("ticket") or "") for x in rows if x.get("ticket")}
        return {"race_id": rid, "html": "ok", "parsed": len(tickets)}
    except Exception as exc:
        return {
            "race_id": rid,
            "html": "error",
            "parsed": 0,
            "error": f"{type(exc).__name__}:{exc}",
        }


def csv_lanes(values: Set[int] | List[int]) -> str:
    vals = sorted(set(int(x) for x in values))
    return ",".join(str(x) for x in vals) if vals else "none"


def main() -> None:
    print(f"OUTAGE_RESIDUAL_VERSION={VERSION}", flush=True)
    print(f"OUTAGE_RESIDUAL_DATE={TARGET_DATE}", flush=True)
    print(
        "OUTAGE_RESIDUAL_POLICY=read_only_db_select_official_http_get_k_source_no_line_no_model_no_shadow_forward",
        flush=True,
    )

    races = load_races()
    race_by_id = {str(x["race_id"]): x for x in races}
    odds = load_odds_counts()
    hist = load_hist_exhibition_lanes()

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

    db_incomplete = [
        race for race in races
        if len(hist.get(str(race["race_id"]), set())) < 6
    ]
    before_results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(probe_beforeinfo, race) for race in db_incomplete]
        for future in as_completed(futures):
            before_results.append(future.result())
    before_results.sort(key=lambda x: str(x["race_id"]))

    print(
        "OUTAGE_RESIDUAL_BEFOREINFO_SCOPE="
        f"db_incomplete_races:{len(db_incomplete)} probed:{len(before_results)}",
        flush=True,
    )
    for x in before_results:
        rid = str(x["race_id"])
        print(
            "OUTAGE_RESIDUAL_BEFOREINFO_RACE="
            f"race:{rid} status:{x['status']} lanes:{csv_lanes(x.get('lanes') or [])} "
            f"db_hist_lanes:{csv_lanes(hist.get(rid, set()))}",
            flush=True,
        )

    k_available, k_unavailable, k_statuses, k_race_count = load_k_source()
    k_expected_rows = sum(len(v) for v in k_available.values())
    db_rows = sum(len(v) for v in hist.values())
    recoverable_total = 0
    affected: List[str] = []

    for rid in sorted(k_available):
        recoverable = k_available[rid] - hist.get(rid, set())
        if recoverable:
            recoverable_total += len(recoverable)
            affected.append(rid)

    print(
        "OUTAGE_RESIDUAL_K_SOURCE="
        f"races:{k_race_count} available_exhibition_rows:{k_expected_rows} "
        f"db_hist_rows:{db_rows} recoverable_missing_rows:{recoverable_total} "
        f"affected_races:{len(affected)}",
        flush=True,
    )
    for rid in affected:
        print(
            "OUTAGE_RESIDUAL_K_RECOVERABLE="
            f"race:{rid} k_available:{csv_lanes(k_available.get(rid, set()))} "
            f"k_unavailable:{csv_lanes(k_unavailable.get(rid, set()))} "
            f"db_hist:{csv_lanes(hist.get(rid, set()))} "
            f"recoverable:{csv_lanes(k_available.get(rid, set()) - hist.get(rid, set()))} "
            f"finish_status:{k_statuses.get(rid) or 'none'}",
            flush=True,
        )

    for rid in zero:
        race = race_by_id.get(rid)
        if not race:
            continue
        x = probe_zero_odds(race)
        print(
            "OUTAGE_RESIDUAL_ZERO_ODDS_PROBE="
            f"race:{rid} html:{x['html']} parsed:{as_int(x.get('parsed'))}",
            flush=True,
        )

    correlated = sorted(set(affected) & set(zero + partial))
    print(
        "OUTAGE_RESIDUAL_CORRELATION="
        f"k_gap_races:{len(affected)} odds_incomplete_races:{len(zero)+len(partial)} "
        f"intersection:{len(correlated)} races:{','.join(correlated) if correlated else 'none'}",
        flush=True,
    )

    print("OUTAGE_RESIDUAL_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
