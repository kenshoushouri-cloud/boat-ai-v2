"""V5 direct official realtime predeadline canary -> six physical stage tables.

V5 calls official beforeinfo and odds3t URLs directly. It reuses legacy
*parsers only*, NEVER the legacy collector's fetch/save/DDL functions and
NEVER reads or writes public.v2_* tables. PREVIEW defaults to no DB writes.
CANARY is disabled unless V5 core stage rows exist and all stage/delta,
BUY-OFF, key, cutoff, authenticity and separation gates are satisfied.
This module does NOT install timers or enable live prediction/betting.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from hashlib import sha256
import os
import uuid
from urllib.parse import urlsplit, parse_qs

from v5.native_stage_race_entries_pg import (
    JST, race_parts, official_fetch, official_payload,
    blocked_by_stage_delta, LOCK,
)

SOURCE = "official_beforeinfo_v5_native"
ODDS_SOURCE = "official_odds3t_v5_native"
STAGE = "boat_data_stage"
SNAPSHOT_KEYS = {
    "entry_snapshots": ("race_id", "snapshot_label", "lane"),
    "exhibition_snapshots": ("race_id", "snapshot_label", "lane"),
    "odds_snapshots": ("race_id", "snapshot_label", "ticket"),
    "weather_snapshots": ("race_id", "snapshot_label"),
    "race_condition_snapshots": ("race_id", "snapshot_label"),
    "racer_condition_snapshots": ("race_id", "snapshot_label", "lane"),
}
REQUIRED = {"V5_NATIVE_REALTIME_STAGE_APPROVED": "YES",
            "V5_SHARED_PRIMARY_MODE": "CANARY",
            "CONFIRM_V5_SHARED_PRIMARY_CANARY": "YES",
            "CONFIRM_LEGACY_WRITES_SEPARATELY": "YES"}
COLUMN_SETS = {
    "entry_snapshots": ("race_id","race_date","venue_id","venue_code","race_no",
      "snapshot_label","snapshot_at","source","lane","racer_number","racer_name",
      "racer_class","original_course","exhibition_course","is_course_changed",
      "motor_no","boat_no","tilt","raw","updated_at"),
    "exhibition_snapshots": ("race_id","race_date","venue_id","venue_code","race_no",
      "snapshot_label","snapshot_at","source","lane","exhibition_course",
      "exhibition_time","exhibition_time_rank","exhibition_time_diff",
      "start_timing","start_timing_rank","start_timing_diff","tilt",
      "original_tilt","tilt_change","raw","updated_at"),
    "odds_snapshots": ("race_id","race_date","venue_id","venue_code","race_no",
      "snapshot_label","snapshot_at","source","ticket","odds","market_rank",
      "prev_odds","odds_delta","odds_delta_pct","prev_market_rank",
      "market_rank_delta","is_favorite","is_odds_too_low","is_odds_drift",
      "is_odds_steam","raw","updated_at"),
    "weather_snapshots": ("race_id","race_date","venue_id","venue_code","race_no",
      "snapshot_label","snapshot_at","source","weather","temperature_c",
      "water_temperature_c","wind_speed_m","wind_direction","wave_height_cm",
      "raw","updated_at"),
    "race_condition_snapshots": ("race_id","race_date","venue_id","venue_code",
      "race_no","snapshot_label","snapshot_at","source","is_stabilizer_used",
      "is_fixed_entry","race_distance_m","has_new_propeller",
      "parts_replacement_count","raw","updated_at"),
    "racer_condition_snapshots": ("race_id","race_date","venue_id","venue_code",
      "race_no","snapshot_label","snapshot_at","source","lane",
      "racer_number","weight_kg","adjustment_weight_kg","is_new_propeller",
      "parts_replacements","previous_race_no","previous_course","previous_st",
      "previous_finish","raw","updated_at"),
}


def ready_to_apply() -> None:
    """No network or DB access before all explicit runtime safety gates."""
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_LOCAL_CONOHA_POSTGRES_REQUIRED")
    for name, value in REQUIRED.items():
        if os.environ.get(name) != value:
            raise RuntimeError("HOLD_MISSING_NATIVE_REALTIME_GATE_" + name)
    if any(os.environ.get(k, "").upper() in ("1", "YES", "ON", "TRUE")
           for k in ("BUY_ENABLED", "ENABLE_PURCHASE", "AUTO_BUY")):
        raise RuntimeError("HOLD_BUY_NOT_OFF")
    blocked_by_stage_delta()


def _check_before_cutoff(captured: datetime, deadline: datetime):
    if captured.tzinfo is None or deadline.tzinfo is None:
        raise RuntimeError("HOLD_NAIVE_CAPTURE_TIME")
    if captured + timedelta(seconds=180) >= deadline:
        raise RuntimeError("HOLD_NOT_PREDEADLINE_WITH_180S_BUFFER")


def official_page(kind: str, rid: str):
    """Single exact official URL, with no fallback to legacy/base odds."""
    import requests
    if kind not in ("beforeinfo", "odds3t"):
        raise ValueError("HOLD_UNKNOWN_OFFICIAL_ENDPOINT")
    day, venue, number = race_parts(rid)
    url = (f"https://www.boatrace.jp/owpc/pc/race/{kind}"
           f"?rno={number}&jcd={venue}&hd={day.replace('-','')}")
    with requests.Session() as client:
        result = client.get(url, timeout=(8, 18), headers={
            "User-Agent": "Mozilla/5.0 (compatible; V5-native-realtime/1.0)"
        })
        result.raise_for_status()
        resolved = urlsplit(result.url)
        expected_params = {"rno": [str(number)], "jcd": [venue],
                           "hd": [day.replace("-", "")]}
        if (resolved.scheme != "https" or resolved.netloc != "www.boatrace.jp"
                or resolved.path != f"/owpc/pc/race/{kind}"
                or resolved.fragment or parse_qs(resolved.query) != expected_params):
            raise RuntimeError("HOLD_OFFICIAL_REDIRECT_OR_RACE_MISMATCH")
        if not result.content or len(result.content) > 2_000_000:
            raise RuntimeError("HOLD_MISSING_OR_OVERSIZE_OFFICIAL_PAGE")
        observed = datetime.now(JST)
        return result.text, observed, sha256(result.content).hexdigest()


def prepare_rows(race, entries, before_html, odds_html, before_at, odds_at,
                 before_hash, odds_hash):
    """Parse official payload into 140 stage-only rows (6+6+120+1+1+6)."""
    import v21_realtime_collector_pg as parser  # *parsers only*, no legacy saves
    from official_odds3t_parser import parse_official_odds3t, complete_snapshot_ticket_set

    deadline = datetime.fromisoformat(race["deadline_at"])
    _check_before_cutoff(before_at, deadline)
    _check_before_cutoff(odds_at, deadline)
    if not before_html or parser._looks_no_data(before_html):
        raise RuntimeError("HOLD_MISSING_OFFICIAL_BEFOREINFO")
    weather = parser.parse_weather(before_html)
    exhibition = parser.parse_exhibition(before_html)
    if len(exhibition) != 6 or {x.get("lane") for x in exhibition} != set(range(1,7)):
        raise RuntimeError("HOLD_EXHIBITION_NOT_SIX_VALID_LANES")
    if any(x.get("exhibition_time") is None or
           not 5.0 <= float(x["exhibition_time"]) <= 9.0 for x in exhibition):
        raise RuntimeError("HOLD_EXHIBITION_TIME_MISSING_OR_INVALID")
    required_weather = ("temperature_c", "water_temperature_c",
                        "wind_speed_m", "wave_height_cm")
    if any(weather.get(k) is None for k in required_weather):
        raise RuntimeError("HOLD_WEATHER_INCOMPLETE")
    odds = parse_official_odds3t(odds_html)
    if len(odds) != 120 or complete_snapshot_ticket_set(odds) is None:
        raise RuntimeError("HOLD_ODDS_NOT_COMPLETE_OFFICIAL_120")
    if {e["lane"] for e in entries} != set(range(1,7)):
        raise RuntimeError("HOLD_RACELIST_NOT_SIX_LANES")
    rc, pcs = parser.parse_beforeinfo_extra(before_html, entries)
    if len(pcs) != 6 or {x.get("lane") for x in pcs} != set(range(1,7)):
        raise RuntimeError("HOLD_RACER_CONDITIONS_NOT_SIX")
    by_lane = {x["lane"]:x for x in entries}
    if any(c.get("racer_number") != by_lane[c["lane"]].get("racer_number")
           for c in pcs):
        raise RuntimeError("HOLD_RACER_CONDITION_ID_MISMATCH")
    rid = race["race_id"]
    label = "v5_native_" + before_at.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:12]
    day, venue, number = race_parts(rid)
    meta = {"race_id":rid,"race_date":day,"venue_id":venue,
            "venue_code":venue,"race_no":number,"snapshot_label":label}
    before_meta = {**meta,"snapshot_at":before_at.isoformat(),
                   "source":SOURCE,"updated_at":before_at.isoformat()}
    odds_meta = {**meta,"snapshot_at":odds_at.isoformat(),
                 "source":ODDS_SOURCE,"updated_at":odds_at.isoformat()}
    b_prov = {"page_sha256":before_hash, "capture_at":before_at.isoformat(),
              "kind":"beforeinfo", "official":True}
    o_prov = {"page_sha256":odds_hash, "capture_at":odds_at.isoformat(),
              "kind":"odds3t", "official":True}
    eb = {e["lane"]:e for e in entries}
    xb = {e["lane"]:e for e in exhibition}
    rows = {name: [] for name in COLUMN_SETS}
    for lane in range(1,7):
        e, x = eb[lane], xb[lane]
        course = x.get("exhibition_course")
        rows["entry_snapshots"].append({
            **before_meta,"lane":lane,"racer_number":e.get("racer_number"),
            "racer_name":e.get("racer_name"),"racer_class":str(e.get("racer_class"))
            if e.get("racer_class") is not None else None,
            "original_course":lane,"exhibition_course":course,
            "is_course_changed":bool(course and course != lane),
            "motor_no":e.get("motor_no"),"boat_no":e.get("boat_no"),
            "tilt":x.get("tilt"),"raw":b_prov})
        rows["exhibition_snapshots"].append({
            **before_meta,"lane":lane,"exhibition_course":course or lane,
            "exhibition_time":x.get("exhibition_time"),
            "exhibition_time_rank":x.get("exhibition_time_rank"),
            "exhibition_time_diff":x.get("exhibition_time_diff"),
            "start_timing":x.get("start_timing"),
            "start_timing_rank":x.get("start_timing_rank"),
            "start_timing_diff":x.get("start_timing_diff"),
            "tilt":x.get("tilt"),"original_tilt":e.get("tilt"),
            "tilt_change":None,"raw":b_prov})
    rows["weather_snapshots"].append({
        **before_meta,"weather":weather.get("weather"),
        "temperature_c":weather["temperature_c"],
        "water_temperature_c":weather["water_temperature_c"],
        "wind_speed_m":weather["wind_speed_m"],
        "wind_direction":weather.get("wind_direction"),
        "wave_height_cm":weather["wave_height_cm"],"raw":b_prov})
    rows["race_condition_snapshots"].append({
        **before_meta,
        "is_stabilizer_used":rc.get("is_stabilizer_used"),
        "is_fixed_entry":rc.get("is_fixed_entry"),
        "race_distance_m":rc.get("race_distance_m"),
        "has_new_propeller":rc.get("has_new_propeller"),
        "parts_replacement_count":rc.get("parts_replacement_count"),
        "raw":b_prov})
    for x in pcs:
        rows["racer_condition_snapshots"].append({
            **before_meta,"lane":x["lane"],"racer_number":x.get("racer_number"),
            "weight_kg":x.get("weight_kg"),
            "adjustment_weight_kg":x.get("adjustment_weight_kg"),
            "is_new_propeller":x.get("is_new_propeller"),
            "parts_replacements":x.get("parts_replacements", []),
            "previous_race_no":x.get("previous_race_no"),
            "previous_course":x.get("previous_course"),
            "previous_st":x.get("previous_st"),
            "previous_finish":x.get("previous_finish"),"raw":b_prov})
    ranked = sorted(odds.items(), key=lambda item:(item[1],item[0]))
    for rank, (ticket, value) in enumerate(ranked,1):
        rows["odds_snapshots"].append({
            **odds_meta,"ticket":ticket,"odds":value,
            "market_rank":rank,"prev_odds":None,"odds_delta":None,
            "odds_delta_pct":None,"prev_market_rank":None,
            "market_rank_delta":None,"is_favorite":rank == 1,
            "is_odds_too_low":value < 3,"is_odds_drift":False,
            "is_odds_steam":False,"raw":o_prov})
    expected = {"entry_snapshots":6,"exhibition_snapshots":6,
                "odds_snapshots":120,"weather_snapshots":1,
                "race_condition_snapshots":1,"racer_condition_snapshots":6}
    if {k:len(v) for k,v in rows.items()} != expected:
        raise RuntimeError("HOLD_INCOMPLETE_REALTIME_PAYLOAD")
    return rows


def save_canary(race, rows):
    # Prevent direct callers from bypassing command-line approval gates.
    ready_to_apply()
    from psycopg import connect, sql
    from psycopg.types.json import Jsonb
    if set(rows) != set(COLUMN_SETS):
        raise RuntimeError("HOLD_UNEXPECTED_STAGE_FAMILIES")
    _check_before_cutoff(datetime.now(JST),datetime.fromisoformat(race["deadline_at"]))
    blocked_by_stage_delta()
    from v5.direct_shared_primary_routes import canary_target
    with connect(os.environ["DATABASE_URL"],connect_timeout=5) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='750ms'")
                cur.execute("SET LOCAL statement_timeout='5000ms'")
                if not cur.execute("SELECT pg_try_advisory_xact_lock(%s)",(LOCK,)).fetchone()[0]:
                    raise RuntimeError("HOLD_STAGE_DELTA_LOCK_BUSY")
                cur.execute("""SELECT count(*) FROM boat_data_stage.entries
                               WHERE race_id=%s""",(race["race_id"],))
                if cur.fetchone()[0] != 6:
                    raise RuntimeError("HOLD_STAGE_CORE_ENTRIES_NOT_PRESENT")
                cur.execute("""SELECT deadline_at::timestamptz
                               FROM boat_data_stage.races WHERE race_id=%s""",
                            (race["race_id"],))
                cutoff = cur.fetchone()
                expected_cutoff = datetime.fromisoformat(race["deadline_at"])
                if not cutoff or cutoff[0] is None or abs(
                        (cutoff[0] - expected_cutoff).total_seconds()) > 1:
                    raise RuntimeError("HOLD_STAGE_CORE_DEADLINE_MISMATCH")
                for table, batch in rows.items():
                    dst = f"{STAGE}.{table}"
                    cur.execute("SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",(dst,))
                    record = cur.fetchone()
                    if not record or record[0] not in ("r","p"):
                        raise RuntimeError("HOLD_STAGE_NOT_PHYSICAL_" + table)
                    cur.execute("""SELECT attname FROM pg_attribute
                        WHERE attrelid=to_regclass(%s) AND attnum>0
                        AND NOT attisdropped""",(dst,))
                    allowed_cols = {x[0] for x in cur.fetchall()}
                    columns = COLUMN_SETS[table]
                    if not set(columns) <= allowed_cols:
                        raise RuntimeError("HOLD_STAGE_MISSING_COLUMNS_" + table)
                    keys=SNAPSHOT_KEYS[table]
                    cur.execute("""SELECT array_agg(a.attname ORDER BY x.ord)
                      FROM pg_index i
                      JOIN LATERAL unnest(i.indkey) WITH ORDINALITY x(num,ord)
                        ON x.ord <= i.indnkeyatts
                      JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=x.num
                      WHERE i.indrelid=to_regclass(%s)
                        AND i.indisvalid AND i.indisunique
                        AND i.indpred IS NULL AND i.indexprs IS NULL
                      GROUP BY i.indexrelid""",(dst,))
                    defined_keys={tuple(z[0]) for z in cur.fetchall()}
                    if keys not in defined_keys:
                        raise RuntimeError("HOLD_STAGE_UNIQUE_KEY_MISSING_" + table)
                    # Runtime catalog and per-table key certification required.
                    actual = canary_target(
                        "public.v2_realtime_" + table,
                        env=os.environ, verified_physical=True,
                        verified_schema_and_keys=True,
                        independent_native_writer=True,
                        legacy_destination_isolated=True,
                        live_buy_disabled=True)
                    if actual != dst:
                        raise RuntimeError("HOLD_STAGE_ROUTE_MISMATCH")
                    q=sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING").format(
                        sql.Identifier(STAGE,table),
                        sql.SQL(",").join(map(sql.Identifier,columns)),
                        sql.SQL(",").join(sql.Placeholder() for _ in columns),
                        sql.SQL(",").join(map(sql.Identifier,keys)))
                    for row in batch:
                        cur.execute(q,[
                            Jsonb(row.get(k)) if isinstance(row.get(k),(dict,list))
                            else row.get(k) for k in columns])
                        if cur.rowcount != 1:
                            raise RuntimeError("HOLD_REALTIME_INSERT_COLLISION_" + table)
                print("V5_NATIVE_REALTIME_STAGE_CANARY_ATOMIC_INSERT_PASS")
    return {k:len(v) for k,v in rows.items()}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--race-id",required=True)
    p.add_argument("--apply",action="store_true")
    args = p.parse_args(argv)
    race_parts(args.race_id)
    if args.apply:
        ready_to_apply()
    html, observed = official_fetch(args.race_id)
    race, entries = official_payload(args.race_id, html, observed)
    deadline=datetime.fromisoformat(race["deadline_at"])
    _check_before_cutoff(observed,deadline)
    before, before_at, b_hash = official_page("beforeinfo",args.race_id)
    odds, odds_at, o_hash = official_page("odds3t",args.race_id)
    rows=prepare_rows(race,entries,before,odds,before_at,odds_at,b_hash,o_hash)
    print("V5_NATIVE_REALTIME_OFFICIAL_VALIDATED race=" + args.race_id +
          " families=6 rows=140 last_capture=" + odds_at.isoformat(),flush=True)
    if not args.apply:
        print("V5_NATIVE_REALTIME_PREVIEW_NO_DB_WRITES_NO_BUY")
        return 0
    amounts=save_canary(race,rows)
    print("V5_NATIVE_REALTIME_COMMITTED " + str(amounts),flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("V5_NATIVE_REALTIME_HOLD " + type(exc).__name__ + ":" +
              str(exc).splitlines()[0][:150],flush=True)
        raise SystemExit(2)
