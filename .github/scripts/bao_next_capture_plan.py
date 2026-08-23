# -*- coding: utf-8 -*-
"""Read-only planner for the next useful Bao forward-capture windows.

Uses only race deadlines plus the isolated Bao Shadow tables to report the next
missing market-early, pairable dedicated exhibition-mid, and paired market-late
capture opportunities. It also reports already-closed missing windows that
occurred after each Shadow stream started, so Forward coverage gaps remain
visible instead of silently disappearing from the planner.

It never writes to the database and never touches Production
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
MISSED_SAMPLE_MAX = 12


def table_exists(conn, table: str) -> bool:
    with conn.cursor() as c:
        c.execute("select to_regclass(%s) is not null ok", (f"public.{table}",))
        return bool(c.fetchone()["ok"])


def normalize_deadline(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST)


def normalize_time(value):
    if value is None:
        return None
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


def missed(races, now, close_before, tracking_start, allowed):
    """Return closed missing windows that occurred after tracking had started."""
    tracking_start = normalize_time(tracking_start)
    if tracking_start is None:
        return []
    out = []
    for race in races:
        rid = str(race["race_id"])
        if not allowed(rid):
            continue
        dl = normalize_deadline(race["deadline_at"])
        closes = dl - timedelta(minutes=close_before)
        if closes < tracking_start:
            continue
        if now > closes:
            out.append((closes, rid))
    out.sort()
    return [rid for _, rid in out]


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


def emit_missed(label, race_ids, tracking_start):
    start = normalize_time(tracking_start)
    start_text = start.isoformat() if start is not None else "none"
    if not race_ids:
        print(
            f"BAO_PLAN_MISSED_{label}=count:0 races:none tracking_start:{start_text}",
            flush=True,
        )
        return
    sample = race_ids[-MISSED_SAMPLE_MAX:]
    more = max(0, len(race_ids) - len(sample))
    print(
        f"BAO_PLAN_MISSED_{label}=count:{len(race_ids)} "
        f"races:{','.join(sample)} more:{more} tracking_start:{start_text}",
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
        market_start = None
        if table_exists(conn, "v2_bao_market_shadow_snapshots"):
            with conn.cursor() as c:
                c.execute(
                    """select race_id,phase,captured_at from v2_bao_market_shadow_snapshots
                       where race_date=%s""",
                    (TARGET_DATE,),
                )
                for row in c.fetchall():
                    key = (str(row["race_id"]), str(row["phase"]))
                    market_rows.add(key)
                    captured_at = normalize_time(row.get("captured_at"))
                    if captured_at is not None and (
                        market_start is None or captured_at < market_start
                    ):
                        market_start = captured_at
                    if key[1] == "early":
                        early_races.add(key[0])
                    elif key[1] == "late":
                        late_races.add(key[0])

        exhibition_races = set()
        exhibition_start = None
        if table_exists(conn, "v2_bao_exhibition_shadow_snapshots"):
            with conn.cursor() as c:
                c.execute(
                    """select race_id,captured_at from v2_bao_exhibition_shadow_snapshots
                       where race_date=%s""",
                    (TARGET_DATE,),
                )
                for row in c.fetchall():
                    exhibition_races.add(str(row["race_id"]))
                    captured_at = normalize_time(row.get("captured_at"))
                    if captured_at is not None and (
                        exhibition_start is None or captured_at < exhibition_start
                    ):
                        exhibition_start = captured_at

        early_missing = lambda rid: (rid, "early") not in market_rows
        ex_missing_pairable = lambda rid: rid in early_races and rid not in exhibition_races
        late_missing_pairable = lambda rid: rid in early_races and rid not in late_races

        early = choose(
            races,
            now,
            EARLY_OPEN,
            EARLY_CLOSE,
            early_missing,
        )
        # Exhibition evidence can only contribute to the current forward audit
        # when an early market row already exists. Prioritize those races so the
        # planner does not recommend an orphan exhibition-only capture.
        exmid = choose(
            races,
            now,
            EX_OPEN,
            EX_CLOSE,
            ex_missing_pairable,
        )
        late_pair = choose(
            races,
            now,
            LATE_OPEN,
            LATE_CLOSE,
            late_missing_pairable,
        )

        missed_early = missed(
            races,
            now,
            EARLY_CLOSE,
            market_start,
            early_missing,
        )
        missed_exmid = missed(
            races,
            now,
            EX_CLOSE,
            exhibition_start,
            ex_missing_pairable,
        )
        missed_late = missed(
            races,
            now,
            LATE_CLOSE,
            market_start,
            late_missing_pairable,
        )

    emit("MARKET_EARLY", early)
    emit("EXHIBITION_MID", exmid)
    emit("MARKET_LATE_PAIR", late_pair)
    emit_missed("MARKET_EARLY", missed_early, market_start)
    emit_missed("EXHIBITION_MID_PAIRABLE", missed_exmid, exhibition_start)
    emit_missed("MARKET_LATE_PAIR", missed_late, market_start)

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
