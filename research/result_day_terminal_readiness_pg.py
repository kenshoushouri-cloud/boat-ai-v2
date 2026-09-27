# -*- coding: utf-8 -*-
"""Read-only terminal-result readiness guard for a target race date."""
from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _ticket_ok(value: Any) -> bool:
    xs = re.findall(r"[1-6]", str(value or ""))
    return len(xs) >= 3 and len(set(xs[:3])) == 3


def classify_result(row: dict[str, Any]) -> str:
    result_status = str(row.get("result_status") or "").strip().lower()
    race_status = str(row.get("race_status") or "").strip().lower()
    payout = int(row.get("trifecta_payout_yen") or 0)

    if (
        result_status == "official"
        and race_status == "official"
        and _ticket_ok(row.get("trifecta_ticket"))
        and payout > 0
    ):
        return "OFFICIAL"

    cancelled = {"cancelled", "canceled"}
    if result_status in cancelled and race_status in cancelled:
        return "VOID"

    if not row.get("result_present"):
        return "MISSING"

    return "PENDING"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"OFFICIAL": 0, "VOID": 0, "PENDING": 0, "MISSING": 0}
    pending = []
    for row in rows:
        status = classify_result(row)
        counts[status] += 1
        if status not in {"OFFICIAL", "VOID"}:
            pending.append({
                "race_id": str(row.get("race_id") or ""),
                "classification": status,
                "result_status": str(row.get("result_status") or ""),
                "race_status": str(row.get("race_status") or ""),
            })
    total = len(rows)
    terminal = counts["OFFICIAL"] + counts["VOID"]
    return {
        "races": total,
        "official": counts["OFFICIAL"],
        "void": counts["VOID"],
        "pending": counts["PENDING"],
        "missing": counts["MISSING"],
        "terminal": terminal,
        "ready": total > 0 and terminal == total,
        "nonterminal_races": pending,
    }


def main() -> None:
    target = date.fromisoformat((os.getenv("TARGET_DATE") or "").strip())
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("RESULT_DAY_READINESS_POLICY=ALL_TARGET_RACES_TERMINAL_FAIL_CLOSED", flush=True)
    print("RESULT_DAY_READINESS_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute(
                """
                select r.race_id,
                       (res.race_id is not null) as result_present,
                       res.result_status,
                       res.race_status,
                       res.trifecta_ticket,
                       res.trifecta_payout_yen
                  from v2_races r
                  left join v2_results res on res.race_id=r.race_id
                 where r.race_date=%s
                 order by r.venue_id,r.race_no
                """,
                (target,),
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.rollback()

    out = summarize(rows)
    out["target_date"] = target.isoformat()
    print("RESULT_DAY_READINESS_JSON=" + json.dumps(out, sort_keys=True), flush=True)
    print(
        "RESULT_DAY_READINESS_RESULT="
        + ("READY" if out["ready"] else "NOT_READY_FAIL_CLOSED"),
        flush=True,
    )
    if not out["ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
