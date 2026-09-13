# -*- coding: utf-8 -*-
"""Read-only pre-production timing-integrity audit for Opponent Pressure v2.

Reads only race schedule/timing metadata and the research shadow table.
No results, odds, predictions, LINE state, purchase state, Production
coefficients, or writes are used.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
TARGET_DATE = date.fromisoformat(os.getenv("TARGET_DATE", "2026-09-11"))
HISTORY_START = date.fromisoformat(os.getenv("HISTORY_START", "2026-08-25"))
SOURCE_CUTOFF = time(8, 15)


def as_jst(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST)


def before_cutoff_for_date(value: datetime | None, race_date: date) -> bool:
    v = as_jst(value)
    return bool(v is not None and v.date() == race_date and v.time().replace(tzinfo=None) <= SOURCE_CUTOFF)


def timing_flags(r: dict[str, Any]) -> tuple[bool, bool, bool, bool, datetime | None, datetime | None]:
    race_date = r.get("race_date")
    if not isinstance(race_date, date):
        raise ValueError("race_date missing")
    deadline = as_jst(r.get("deadline_at"))
    created = as_jst(r.get("created_at"))
    updated = as_jst(r.get("updated_at"))
    c_cut = before_cutoff_for_date(created, race_date)
    u_cut = before_cutoff_for_date(updated, race_date)
    c_dead = bool(created is not None and deadline is not None and created < deadline)
    u_dead = bool(updated is not None and deadline is not None and updated < deadline)
    return c_cut, u_cut, c_dead, u_dead, created, updated


def main() -> None:
    db = os.getenv("DATABASE_URL", "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("OPP_TIMING_AUDIT_MODE=read_only_no_results_no_odds_no_predictions", flush=True)
    print("OPP_TIMING_AUDIT_POLICY=no_writes_no_production_no_line_no_coefficients", flush=True)
    print(f"OPP_TIMING_AUDIT_DATE={TARGET_DATE}", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("""
                select r.race_id, r.race_date, r.deadline_at,
                       o.race_id is not null as has_opp,
                       o.model_version, o.train_end, o.matched_opponents,
                       o.created_at, o.updated_at
                  from v2_races r
                  left join v2_opponent_pressure_shadow_v2 o on o.race_id=r.race_id
                 where r.race_date=%s
                 order by r.race_id
            """, (TARGET_DATE,))
            rows = [dict(x) for x in cur.fetchall()]
            cur.execute("""
                select r.race_id, r.race_date, r.deadline_at,
                       o.model_version, o.train_end, o.matched_opponents,
                       o.created_at, o.updated_at
                  from v2_races r
                  join v2_opponent_pressure_shadow_v2 o on o.race_id=r.race_id
                 where r.race_date between %s and %s
                 order by r.race_date,r.race_id
            """, (HISTORY_START, TARGET_DATE - timedelta(days=1)))
            history = [dict(x) for x in cur.fetchall()]
        conn.rollback()

    target = len(rows)
    present = [r for r in rows if r.get("has_opp")]
    missing = target - len(present)
    deadline_ready = sum(as_jst(r.get("deadline_at")) is not None for r in rows)

    full_safe = model_ok = train_ok = 0
    created_cutoff_ok = updated_cutoff_ok = 0
    created_deadline_ok = updated_deadline_ok = 0
    timing_clean = mutable_rows = 0
    post_cutoff_updates = post_deadline_updates = 0
    post_cutoff_creates = post_deadline_creates = 0

    for r in present:
        c_cut, u_cut, c_dead, u_dead, created, updated = timing_flags(r)
        matched = r.get("matched_opponents")
        is_full = isinstance(matched, list) and len(matched) == 6 and all(int(x) >= 4 for x in matched)
        is_model = int(r.get("model_version") or 0) == 2
        is_train = r.get("train_end") == TARGET_DATE - timedelta(days=1)
        full_safe += int(is_full)
        model_ok += int(is_model)
        train_ok += int(is_train)
        created_cutoff_ok += int(c_cut)
        updated_cutoff_ok += int(u_cut)
        created_deadline_ok += int(c_dead)
        updated_deadline_ok += int(u_dead)
        timing_clean += int(is_full and is_model and is_train and c_cut and u_cut and c_dead and u_dead)
        mutable_rows += int(created is not None and updated is not None and updated > created)
        post_cutoff_updates += int(not u_cut)
        post_deadline_updates += int(not u_dead)
        post_cutoff_creates += int(not c_cut)
        post_deadline_creates += int(not c_dead)

    print(
        "OPP_TIMING_AUDIT_ROWS="
        f"target:{target} deadline_ready:{deadline_ready} present:{len(present)} missing:{missing} "
        f"full_safe:{full_safe} model_ok:{model_ok} train_ok:{train_ok}", flush=True,
    )
    print(
        "OPP_TIMING_AUDIT_CREATED="
        f"cutoff_ok:{created_cutoff_ok} deadline_ok:{created_deadline_ok} "
        f"post_cutoff:{post_cutoff_creates} post_deadline:{post_deadline_creates}", flush=True,
    )
    print(
        "OPP_TIMING_AUDIT_UPDATED="
        f"cutoff_ok:{updated_cutoff_ok} deadline_ok:{updated_deadline_ok} "
        f"mutable:{mutable_rows} post_cutoff:{post_cutoff_updates} post_deadline:{post_deadline_updates}", flush=True,
    )
    print(f"OPP_TIMING_AUDIT_TIMING_CLEAN={timing_clean}/{target}", flush=True)

    hist_mutable = hist_created_post_cutoff = hist_updated_post_cutoff = 0
    hist_created_post_deadline = hist_updated_post_deadline = 0
    hidden_cutoff = hidden_deadline = 0
    by_date: dict[date, dict[str, Any]] = defaultdict(lambda: {
        "rows": 0, "post_cutoff": 0, "post_deadline": 0,
        "mutable": 0, "min_created": None, "max_created": None,
    })

    for r in history:
        race_date = r.get("race_date")
        if not isinstance(race_date, date):
            continue
        c_cut, u_cut, c_dead, u_dead, created, updated = timing_flags(r)
        hist_mutable += int(created is not None and updated is not None and updated > created)
        hist_created_post_cutoff += int(not c_cut)
        hist_updated_post_cutoff += int(not u_cut)
        hist_created_post_deadline += int(not c_dead)
        hist_updated_post_deadline += int(not u_dead)
        hidden_cutoff += int(c_cut and not u_cut)
        hidden_deadline += int(c_dead and not u_dead)

        d = by_date[race_date]
        d["rows"] += 1
        d["post_cutoff"] += int(not c_cut)
        d["post_deadline"] += int(not c_dead)
        d["mutable"] += int(created is not None and updated is not None and updated > created)
        if created is not None:
            if d["min_created"] is None or created < d["min_created"]:
                d["min_created"] = created
            if d["max_created"] is None or created > d["max_created"]:
                d["max_created"] = created

    print(
        "OPP_TIMING_AUDIT_HISTORY="
        f"start:{HISTORY_START} end:{TARGET_DATE - timedelta(days=1)} dates:{len(by_date)} rows:{len(history)} "
        f"mutable:{hist_mutable} created_post_cutoff:{hist_created_post_cutoff} updated_post_cutoff:{hist_updated_post_cutoff} "
        f"created_post_deadline:{hist_created_post_deadline} updated_post_deadline:{hist_updated_post_deadline} "
        f"created_safe_updated_unsafe_cutoff:{hidden_cutoff} created_safe_updated_unsafe_deadline:{hidden_deadline}", flush=True,
    )
    for race_date in sorted(by_date):
        d = by_date[race_date]
        mn = d["min_created"].strftime("%H:%M:%S") if d["min_created"] else "none"
        mx = d["max_created"].strftime("%H:%M:%S") if d["max_created"] else "none"
        print(
            "OPP_TIMING_AUDIT_HISTORY_DATE="
            f"date:{race_date} rows:{d['rows']} post_cutoff:{d['post_cutoff']} "
            f"post_deadline:{d['post_deadline']} mutable:{d['mutable']} created_jst:{mn}-{mx}", flush=True,
        )

    structural_mutability = True  # current collector uses ON CONFLICT ... DO UPDATE
    empirical_bad_update = post_cutoff_updates > 0 or post_deadline_updates > 0
    historical_hidden_mutation = hidden_cutoff > 0 or hidden_deadline > 0
    if target == 0 or deadline_ready != target:
        verdict = "BLOCK_RACE_TIMING_INCOMPLETE"
    elif missing > 0:
        verdict = "BLOCK_OPPONENT_ROWS_INCOMPLETE"
    elif empirical_bad_update:
        verdict = "BLOCK_POST_CUTOFF_OR_DEADLINE_UPDATE_OBSERVED"
    elif historical_hidden_mutation:
        verdict = "BLOCK_CREATED_AT_ONLY_WOULD_MISS_HISTORICAL_MUTATION"
    elif structural_mutability:
        verdict = "BLOCK_MUTABLE_UPSERT_CONTRACT_REQUIRES_REMEDIATION"
    else:
        verdict = "PASS_PREPROD_TIMING_INTEGRITY"
    print(f"OPP_TIMING_AUDIT_VERDICT={verdict}", flush=True)
    print("OPP_TIMING_AUDIT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"OPP_TIMING_AUDIT_ERROR={type(exc).__name__}:{str(exc).replace(chr(10), ' ')[:700]}", flush=True)
        raise
