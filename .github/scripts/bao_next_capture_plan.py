# -*- coding: utf-8 -*-
"""Read-only planner for the next useful Bao forward-capture windows.

Uses only race deadlines plus the isolated Bao Shadow tables to report the next
missing market-early, dedicated exhibition-mid, and paired market-late capture
opportunities. It never writes to the database and never touches Production
predictions/decisions or LINE.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
DB = os.getenv("DATABASE_URL", "").strip()
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")

EARLY_OPEN = 30.0
EARLY_CLOSE = 20.0
EX_OPEN = 15.0
EX_CLOSE = 8.0
LATE_OPEN = 7.0
LATE_CLOSE = 0.0


def table_exists(conn, table: str) -> bool:
    with conn.cursor() as c:
        c.execute("select to_regclass(%s) is not null ok", (f"public.{table}",))
        return bool(c.fetchone()["ok"])


def normalize_deadline(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST)


def candidate(race, now, open_before, close_before):
    dl = normalize_deadline(race["deadline_at"])
    opens = dl - timedelta(minutes=open_before)
    closes = dl - timedelta(minutes=close_before)
    if now > closes:
        return None
    action_at = now if now >= opens else opens
    return {
        "race_id": str(race["race_id"]),
        "deadline": dl,
        "opens": opens,
        "closes": closes,
        "action_at": action_at,
        "state": "open" if opens <= now <= closes else "future",
        "minutes_until": max(0.0, (action_at - now).total_seconds() / 60.0),
    }


def choose(races, now, open_before, close_before, allowed):
    options = []
    for race in races:
        rid = str(race["race_id"])
        if not allowed(rid):
            continue
        x = candidate(race, now, open_before, close_before)
        if x is not None:
            options.append(x)
    if not options:
        return None
    return min(options, key=lambda x: (x["action_at"], x["deadline"], x["race_id"]))


def emit(label, x):
    if x is None:
        print(f"BAO_PLAN_{label}=none", flush=True)
        return
    print(
        f"BAO_PLAN_{label}=state:{x['state']} race:{x['race_id']} "
        f"opens_at:{x['opens'].isoformat()} closes_at:{x['closes'].isoformat()} "
        f"deadline_at:{x['deadline'].isoformat()} minutes_until_open:{x['minutes_until']:.2f}",
        flush=True,
    )


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    now = datetime.now(JST)
    print(f"BAO_PLAN_MODE=read_only target:{TARGET_DATE} now:{now.isoformat()}", flush=True)
    print("BAO_PLAN_POLICY=no_writes_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute(
                """select race_id,deadline_at
                   from v2_races
                   where race_date=%s and deadline_at is not null
                   order by deadline_at,race_id""",
                (TARGET_DATE,),
            )
            races = [dict(x) for x in c.fetchall()]

        market_rows = set()
        early_races = set()
        late_races = set()
        if table_exists(conn, "v2_bao_market_shadow_snapshots"):
            with conn.cursor() as c:
                c.execute(
                    """select race_id,phase from v2_bao_market_shadow_snapshots
                       where race_date=%s""",
                    (TARGET_DATE,),
                )
                for row in c.fetchall():
                    key = (str(row["race_id"]), str(row["phase"]))
                    market_rows.add(key)
                    if key[1] == "early":
                        early_races.add(key[0])
                    elif key[1] == "late":
                        late_races.add(key[0])

        exhibition_races = set()
        if table_exists(conn, "v2_bao_exhibition_shadow_snapshots"):
            with conn.cursor() as c:
                c.execute(
                    """select race_id from v2_bao_exhibition_shadow_snapshots
                       where race_date=%s""",
                    (TARGET_DATE,),
                )
                exhibition_races = {str(x["race_id"]) for x in c.fetchall()}

        early = choose(
            races,
            now,
            EARLY_OPEN,
            EARLY_CLOSE,
            lambda rid: (rid, "early") not in market_rows,
        )
        exmid = choose(
            races,
            now,
            EX_OPEN,
            EX_CLOSE,
            lambda rid: rid not in exhibition_races,
        )
        late_pair = choose(
            races,
            now,
            LATE_OPEN,
            LATE_CLOSE,
            lambda rid: rid in early_races and rid not in late_races,
        )

    emit("MARKET_EARLY", early)
    emit("EXHIBITION_MID", exmid)
    emit("MARKET_LATE_PAIR", late_pair)

    available = [
        ("market_early", early),
        ("exhibition_mid", exmid),
        ("market_late_pair", late_pair),
    ]
    available = [(name, x) for name, x in available if x is not None]
    if available:
        reason, nxt = min(available, key=lambda p: (p[1]["action_at"], p[1]["deadline"]))
        print(
            f"BAO_PLAN_NEXT_COMBINED=reason:{reason} at:{nxt['action_at'].isoformat()} "
            f"minutes_until:{nxt['minutes_until']:.2f}",
            flush=True,
        )
    else:
        print("BAO_PLAN_NEXT_COMBINED=none", flush=True)

    print("BAO_PLAN_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
