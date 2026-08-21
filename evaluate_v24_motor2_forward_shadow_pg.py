# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from db_pg import execute, fetch_all

VERSION = "2026-08-21 v24-motor2-forward-evaluator-v3-log-cleanup"
TARGET_DATE = (os.getenv("TARGET_DATE") or "").strip()
SNAPSHOT_KEY = (os.getenv("SNAPSHOT_KEY") or "").strip()
RUN_CLASS = (os.getenv("RUN_CLASS") or "").strip()
WINDOW_NAME = (os.getenv("WINDOW_NAME") or "").strip()
UNIT_YEN = max(
    1,
    int(os.getenv("MOTOR2_EVAL_UNIT_YEN", os.getenv("UNIT_YEN", "100"))),
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except Exception:
        return default


def _norm_ticket(value: Any) -> str:
    return str(value or "").strip()


def _where_sql(alias: str = "s") -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    for value, column in [
        (TARGET_DATE, "race_date"),
        (SNAPSHOT_KEY, "snapshot_key"),
        (RUN_CLASS, "run_class"),
        (WINDOW_NAME, "window_name"),
    ]:
        if value:
            clauses.append(f"{alias}.{column} = %s")
            params.append(value)
    return ((" AND " + " AND ".join(clauses)) if clauses else "", params)


def _fetch_targets():
    extra, params = _where_sql("s")
    return fetch_all(
        f"""
        SELECT
            s.*,
            r.result_status,
            r.race_status,
            r.trifecta_ticket AS official_ticket,
            r.trifecta_payout_yen AS official_payout
        FROM v2_v24_motor2_forward_shadow s
        LEFT JOIN v2_results r ON r.race_id = s.race_id
        WHERE 1=1 {extra}
        ORDER BY s.race_date,s.snapshot_at,s.race_id,s.ticket,s.id
        """,
        tuple(params),
    )


def _evaluable(row: Dict[str, Any]) -> bool:
    return (
        str(row.get("result_status") or "").lower() == "official"
        and str(row.get("race_status") or "").lower() == "official"
        and bool(_norm_ticket(row.get("official_ticket")))
        and _safe_int(row.get("official_payout"), 0) > 0
    )


def _update(row: Dict[str, Any]) -> None:
    official_ticket = _norm_ticket(row.get("official_ticket"))
    official_payout = _safe_int(row.get("official_payout"), 0)
    hit = _norm_ticket(row.get("ticket")) == official_ticket
    base_selected = bool(row.get("base_low_candidate")) or bool(
        row.get("base_mid_candidate")
    )
    motor2_selected = bool(row.get("motor2_low_candidate")) or bool(
        row.get("motor2_mid_candidate")
    )

    execute(
        """
        UPDATE v2_v24_motor2_forward_shadow
        SET result_ticket=%s,
            payout_yen=%s,
            base_hit=%s,
            motor2_hit=%s,
            evaluated_at=now(),
            updated_at=now()
        WHERE id=%s
        """,
        (
            official_ticket,
            official_payout,
            bool(base_selected and hit),
            bool(motor2_selected and hit),
            row["id"],
        ),
    )


def _new() -> Dict[str, int]:
    return {"bets": 0, "hits": 0, "investment": 0, "return": 0}


def _add(stat: Dict[str, int], selected: bool, hit: bool, payout: int) -> None:
    if not selected:
        return
    stat["bets"] += 1
    stat["investment"] += UNIT_YEN
    if hit:
        stat["hits"] += 1
        stat["return"] += payout


def _fmt(name: str, stat: Dict[str, int]) -> str:
    bets = stat["bets"]
    hit_rate = stat["hits"] / bets * 100 if bets else 0.0
    roi = stat["return"] / stat["investment"] * 100 if stat["investment"] else 0.0
    return (
        f"{name}: bets={bets} hits={stat['hits']} hit_rate={hit_rate:.2f}% "
        f"investment={stat['investment']} return={stat['return']} "
        f"profit={stat['return'] - stat['investment']} ROI={roi:.2f}%"
    )


def _scope(label: str, rows) -> None:
    stats = {"BASE": _new(), "MOTOR2": _new()}
    transitions = defaultdict(int)
    evaluated = 0
    pending = 0

    for row in rows:
        result_ticket = _norm_ticket(row.get("result_ticket"))
        payout = _safe_int(row.get("payout_yen"), 0)
        if not (row.get("evaluated_at") and result_ticket and payout > 0):
            pending += 1
            continue

        evaluated += 1
        hit = _norm_ticket(row.get("ticket")) == result_ticket
        base_selected = bool(row.get("base_low_candidate")) or bool(
            row.get("base_mid_candidate")
        )
        motor2_selected = bool(row.get("motor2_low_candidate")) or bool(
            row.get("motor2_mid_candidate")
        )
        _add(stats["BASE"], base_selected, base_selected and hit, payout)
        _add(stats["MOTOR2"], motor2_selected, motor2_selected and hit, payout)
        transitions[str(row.get("candidate_transition") or "")] += 1

    print(f"=== {label} ===", flush=True)
    print(f"rows={len(rows)} evaluated={evaluated} pending={pending}", flush=True)
    print(_fmt("BASE", stats["BASE"]), flush=True)
    print(_fmt("MOTOR2", stats["MOTOR2"]), flush=True)

    base_roi = (
        stats["BASE"]["return"] / stats["BASE"]["investment"] * 100
        if stats["BASE"]["investment"]
        else 0.0
    )
    motor2_roi = (
        stats["MOTOR2"]["return"] / stats["MOTOR2"]["investment"] * 100
        if stats["MOTOR2"]["investment"]
        else 0.0
    )
    print(f"ROI_DELTA MOTOR2-BASE={motor2_roi - base_roi:+.2f}pt", flush=True)
    print(
        "TRANSITIONS "
        f"BOTH={transitions.get('BOTH', 0)} "
        f"BASE_ONLY={transitions.get('BASE_ONLY', 0)} "
        f"MOTOR2_ONLY={transitions.get('MOTOR2_ONLY', 0)} "
        f"NEITHER={transitions.get('NEITHER', 0)}",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        f"OK evaluate_v24_motor2_forward_shadow_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(
        f"TARGET_DATE={TARGET_DATE or 'ALL'} "
        f"SNAPSHOT_KEY={SNAPSHOT_KEY or 'ALL'} "
        f"RUN_CLASS={RUN_CLASS or 'ALL'} "
        f"WINDOW_NAME={WINDOW_NAME or 'ALL'} UNIT_YEN={UNIT_YEN}",
        flush=True,
    )
    print("LINE=0 BUY=0 PROD_V24_CHANGE=0 N02_CHANGE=0", flush=True)

    rows = _fetch_targets()
    updated = 0
    not_ready = 0
    already = 0

    for row in rows:
        if not _evaluable(row):
            not_ready += 1
            continue

        if (
            row.get("evaluated_at") is not None
            and _norm_ticket(row.get("result_ticket"))
            == _norm_ticket(row.get("official_ticket"))
            and _safe_int(row.get("payout_yen"), 0)
            == _safe_int(row.get("official_payout"), 0)
        ):
            already += 1
            continue

        _update(row)
        updated += 1

    print("=== UPDATE SUMMARY ===", flush=True)
    print(
        f"rows_loaded={len(rows)} updated_rows={updated} "
        f"already_evaluated={already} result_not_ready={not_ready}",
        flush=True,
    )

    rows = _fetch_targets()
    _scope("OVERALL", rows)

    grouped = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row.get("run_class") or ""),
                str(row.get("window_name") or ""),
            )
        ].append(row)

    print("=== BY RUN_CLASS / WINDOW ===", flush=True)
    for key in sorted(grouped):
        _scope(f"{key[0]} / {key[1]}", grouped[key])

    print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
