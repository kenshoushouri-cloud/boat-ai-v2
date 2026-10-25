# -*- coding: utf-8 -*-
"""Read-only Feature Lab equivalence using archived base odds.

This is a research adapter, not a Production path. It keeps all non-odds
inputs in PostgreSQL read-only and compares Feature Lab summaries computed
with online v2_odds_trifecta rows versus an exact verified archive partition.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import os

from db_pg import fetch_all
import feature_lab_pg as fl
from research_archive_readthrough import EvidenceQuery, JsonlGzipPartitionSource


def _odds_by(rows):
    out = {}
    for r in rows:
        t = fl.ticket(r.get("ticket"))
        o = fl.sf(r.get("odds"))
        if t and o > 0:
            out.setdefault(str(r.get("race_id")), {})[t] = o
    return out


def _summary(races, entries_by, cond_by, odds_by, course_stats, results):
    ranks = {name: [] for name in fl.CONFIGS}
    improved = {name: 0 for name in fl.CONFIGS}
    worsened = {name: 0 for name in fl.CONFIGS}
    same = {name: 0 for name in fl.CONFIGS}
    st_cov = 0
    course_cov = 0
    eligible = 0

    for race in races:
        rid = str(race.get("race_id"))
        entries = entries_by.get(rid, [])
        odds = odds_by.get(rid, {})
        win = results.get(rid)
        if len(fl.base._entry_by_lane(entries)) != 6 or len(odds) < 100 or not win:
            continue
        eligible += 1
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        rr = {}
        for name, (use_st, use_course) in fl.CONFIGS.items():
            rank_map, sc, cc = fl.make_rank(
                entries,
                venue,
                odds,
                cond_by.get(rid, {}),
                course_stats,
                use_st,
                use_course,
            )
            rr[name] = rank_map.get(win, 999)
            if name == "PREVIOUS_ST_FIXED" and sc > 0:
                st_cov += 1
            if name == "RACER_COURSE" and cc == 6:
                course_cov += 1
        base_rank = rr["BASELINE"]
        for name in fl.CONFIGS:
            rank = rr[name]
            ranks[name].append(rank)
            improved[name] += int(rank < base_rank)
            worsened[name] += int(rank > base_rank)
            same[name] += int(rank == base_rank)

    payload = {
        "eligible_races": eligible,
        "previous_st_coverage_races": st_cov,
        "racer_course_full_coverage_races": course_cov,
        "configs": {},
    }
    for name in fl.CONFIGS:
        m = fl.calc(ranks[name])
        payload["configs"][name] = {
            "n": m["n"],
            "avg": round(float(m["avg"]), 12),
            "t3": round(float(m["t3"]), 12),
            "t5": round(float(m["t5"]), 12),
            "t10": round(float(m["t10"]), 12),
            "t20": round(float(m["t20"]), 12),
            "improved": improved[name],
            "worsened": worsened[name],
            "same": same[name],
        }
    return payload


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")
    manifest_path = os.getenv("FEATURE_LAB_BASE_ODDS_ARCHIVE_MANIFEST", "").strip()
    if not manifest_path:
        raise RuntimeError("FEATURE_LAB_BASE_ODDS_ARCHIVE_MANIFEST is required")

    start = os.getenv("FEATURE_LAB_START_DATE", "2026-07-01")
    end = os.getenv("FEATURE_LAB_END_DATE", "2026-07-31")
    label = os.getenv("SNAPSHOT_LABEL", "final_ab")

    races = fetch_all(
        "select * from v2_races where race_date >= %s and race_date <= %s order by race_date,venue_id,race_no",
        (start, end),
    )
    ids = [str(r.get("race_id")) for r in races]
    if not ids:
        raise RuntimeError("no races in requested period")

    entries_by = fl.group(
        fetch_all(
            "select * from v2_race_entries where race_id=any(%s) order by race_id,lane",
            (ids,),
        )
    )
    cond_rows = fl.group(
        fetch_all(
            "select * from v2_realtime_racer_condition_snapshots where race_id=any(%s) and snapshot_label=%s order by race_id,lane",
            (ids, label),
        )
    )
    cond_by = {
        rid: {fl.si(x.get("lane")): x for x in rows}
        for rid, rows in cond_rows.items()
    }

    online_odds_rows = fetch_all(
        "select race_id,ticket,odds from v2_odds_trifecta where race_id=any(%s)",
        (ids,),
    )
    online_odds = _odds_by(online_odds_rows)

    source = JsonlGzipPartitionSource(manifest_path)
    query = EvidenceQuery(
        table="v2_odds_trifecta",
        start_date=start,
        end_date=end,
        race_ids=tuple(ids),
    )
    archive_rows = source.fetch(query)
    archive_odds = _odds_by(archive_rows)

    course_stats = {}
    for r in fetch_all(
        "select distinct on (racer_number,course) racer_number,course,entry_rate,top3_rate,avg_st,snapshot_date "
        "from v2_racer_course_stats_snapshots where snapshot_date <= %s "
        "order by racer_number,course,snapshot_date desc",
        (end,),
    ):
        course_stats[(fl.si(r.get("racer_number")), fl.si(r.get("course")))] = r

    next_day = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
    results = {}
    for r in fetch_all(
        "select * from v2_results where race_id >= %s and race_id < %s",
        (start.replace("-", ""), next_day),
    ):
        t = fl.result_ticket(r)
        if t:
            results[str(r.get("race_id"))] = t

    online = _summary(races, entries_by, cond_by, online_odds, course_stats, results)
    archived = _summary(races, entries_by, cond_by, archive_odds, course_stats, results)

    online_json = json.dumps(online, sort_keys=True, separators=(",", ":"))
    archive_json = json.dumps(archived, sort_keys=True, separators=(",", ":"))
    if online_json != archive_json:
        raise RuntimeError("Feature Lab online/archive summary mismatch")

    print(
        f"FEATURE_LAB_ARCHIVE_COMPARE=PASS period={start}..{end} "
        f"online_odds_rows={len(online_odds_rows)} archive_odds_rows={len(archive_rows)} "
        f"eligible_races={online['eligible_races']}",
        flush=True,
    )
    for name, values in sorted(online["configs"].items()):
        print(
            "FEATURE_LAB_ARCHIVE_CONFIG "
            f"name={name} n={values['n']} avg={values['avg']} "
            f"top5={values['t5']} top10={values['t10']}",
            flush=True,
        )
    print("FEATURE_LAB_ARCHIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
