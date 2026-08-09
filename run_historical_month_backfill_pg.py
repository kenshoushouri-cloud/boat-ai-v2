# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import time
from calendar import monthrange
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all, fetch_one

TARGET_MONTH = os.getenv("HISTORICAL_GAP_REPAIR_MONTH", "2026-01").strip()
WORKERS = int(os.getenv("HISTORICAL_GAP_REPAIR_WORKERS", "4"))
ODDS_WORKERS = int(os.getenv("HISTORICAL_GAP_REPAIR_ODDS_WORKERS", "2"))
SLEEP_SEC = float(os.getenv("HISTORICAL_GAP_REPAIR_SLEEP_SEC", "0.1"))
MAX_TARGETS = int(os.getenv("HISTORICAL_GAP_REPAIR_MAX_TARGETS", "0"))


def _month_bounds(ym: str) -> Tuple[str, str, str]:
    dt = datetime.strptime(ym, "%Y-%m")
    last_day = monthrange(dt.year, dt.month)[1]
    start = f"{dt.year:04d}-{dt.month:02d}-01"
    end = f"{dt.year:04d}-{dt.month:02d}-{last_day:02d}"
    next_start = f"{dt.year + 1:04d}-01-01" if dt.month == 12 else f"{dt.year:04d}-{dt.month + 1:02d}-01"
    return start, end, next_start


def _fetch_gap_targets(start_date: str, next_start: str) -> List[Dict[str, Any]]:
    start_rid = start_date.replace("-", "")
    next_rid = next_start.replace("-", "")
    rows = fetch_all(
        '''
        with odds_counts as (
            select race_id, count(distinct ticket) as ticket_count
            from v2_odds_trifecta
            where race_id >= %s and race_id < %s
            group by race_id
        )
        select
            r.race_id, r.race_date, r.venue_id, r.race_no,
            coalesce(o.ticket_count, 0) as ticket_count,
            rs.trifecta_ticket, rs.trifecta_payout_yen
        from v2_races r
        join v2_results rs on rs.race_id = r.race_id
        left join odds_counts o on o.race_id = r.race_id
        where r.race_date >= %s and r.race_date < %s
          and rs.trifecta_ticket is not null
          and rs.trifecta_payout_yen > 0
          and coalesce(o.ticket_count, 0) not in (120, 60, 24)
        order by r.race_date, r.venue_id, r.race_no;
        ''',
        (start_rid, next_rid, start_date, next_start),
    )
    return rows[:MAX_TARGETS] if MAX_TARGETS > 0 else rows


def _audit(start_date: str, next_start: str) -> Dict[str, int]:
    start_rid = start_date.replace("-", "")
    next_rid = next_start.replace("-", "")
    base = fetch_one(
        '''
        select
            count(*) as races,
            count(*) filter (
                where rs.trifecta_ticket is not null
                  and rs.trifecta_payout_yen > 0
            ) as valid_results
        from v2_races r
        left join v2_results rs on rs.race_id = r.race_id
        where r.race_date >= %s and r.race_date < %s;
        ''',
        (start_date, next_start),
    ) or {}
    odds = fetch_all(
        '''
        select race_id, count(distinct ticket) as ticket_count
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        group by race_id;
        ''',
        (start_rid, next_rid),
    )
    return {
        "races": int(base.get("races") or 0),
        "valid_results": int(base.get("valid_results") or 0),
        "odds_races": len(odds),
        "complete_expected": sum(1 for r in odds if int(r.get("ticket_count") or 0) in (120, 60, 24)),
        "partial": sum(1 for r in odds if int(r.get("ticket_count") or 0) not in (120, 60, 24)),
    }


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")

    start_date, end_date, next_start = _month_bounds(TARGET_MONTH)
    print("â run_historical_month_gap_repair_pg.py VERSION 2026-08-10 valid-result-incomplete-odds-v1", flush=True)
    print(f"TARGET_MONTH={TARGET_MONTH} PERIOD={start_date}..{end_date}", flush=True)
    print("å¯¾è±¡: æå¹çµæãã AND ä¸é£åãªããºã120/60/24éãä»¥å¤", flush=True)
    print("æ¬çªå¤å®ã»LINEéç¥ã»è³¼å¥å¦çã«ã¯å½±é¿ãã¾ããã", flush=True)

    before = _audit(start_date, next_start)
    print(
        f"BEFORE races={before['races']} valid_results={before['valid_results']} "
        f"odds_races={before['odds_races']} complete_expected={before['complete_expected']} "
        f"partial={before['partial']}",
        flush=True,
    )

    targets = _fetch_gap_targets(start_date, next_start)
    print(f"gap_targets={len(targets)}", flush=True)
    for row in targets[:30]:
        print(
            f"  {row.get('race_id')} tickets={int(row.get('ticket_count') or 0)} "
            f"result={row.get('trifecta_ticket')} payout={row.get('trifecta_payout_yen')}",
            flush=True,
        )

    if not targets:
        print("åè£ä¿®å¯¾è±¡ã¯ããã¾ãããçµäºãã¾ãã", flush=True)
        return

    base_dir = Path(__file__).resolve().parent
    repair_script = base_dir / "repair_month_all_pg.py"
    if not repair_script.exists():
        raise FileNotFoundError(f"repair_month_all_pg.py ãè¦ã¤ããã¾ãã: {repair_script}")

    env = os.environ.copy()
    env.update({
        "REPAIR_START_DATE": start_date,
        "REPAIR_END_DATE": end_date,
        "REPAIR_RACE_IDS": ",".join(str(r["race_id"]) for r in targets),
        "REPAIR_DO_RACES": "0",
        "REPAIR_DO_RESULTS": "0",
        "REPAIR_DO_ODDS": "1",
        "ODDS_IS_FINAL": "1",
        "REPAIR_WORKERS": str(WORKERS),
        "REPAIR_ODDS_WORKERS": str(ODDS_WORKERS),
        "REPAIR_SLEEP_SEC": str(SLEEP_SEC),
        "PYTHONUNBUFFERED": "1",
    })

    print("=" * 80, flush=True)
    print(f"TARGETED GAP REPAIR START targets={len(targets)}", flush=True)
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-u", str(repair_script)],
        cwd=str(base_dir),
        env=env,
        text=True,
        check=False,
    )
    elapsed = time.monotonic() - started
    print(f"TARGETED GAP REPAIR END returncode={result.returncode} elapsed={elapsed:.1f}s", flush=True)
    print("=" * 80, flush=True)

    if result.returncode != 0:
        raise RuntimeError(f"repair_month_all_pg.py ãå¤±æãã¾ãããreturncode={result.returncode}")

    after = _audit(start_date, next_start)
    remaining = _fetch_gap_targets(start_date, next_start)
    print("=== targeted gap repair audit ===", flush=True)
    print(
        f"AFTER races={after['races']} valid_results={after['valid_results']} "
        f"odds_races={after['odds_races']} complete_expected={after['complete_expected']} "
        f"partial={after['partial']}",
        flush=True,
    )
    print(
        f"gap_targets_before={len(targets)} gap_targets_remaining={len(remaining)} "
        f"improved={len(targets)-len(remaining)}",
        flush=True,
    )
    print("TARGETED_GAP_REPAIR=PASS" if not remaining else "TARGETED_GAP_REPAIR=PARTIAL", flush=True)


if __name__ == "__main__":
    main()