# -*- coding: utf-8 -*-
"""
evaluate_v24_motor2_forward_shadow_pg.py

v2_v24_motor2_forward_shadow の Forward Shadow 結果評価。

- v2_results の確定三連単結果を突合
- result_ticket / payout_yen / base_hit / motor2_hit / evaluated_at を更新
- BASE と MOTOR2 の LOW / MID / 全候補を比較
- MOTOR2_ONLY / BASE_ONLY / BOTH の成績を集計
- 再実行しても同じ結果になる冪等設計

Railway Start Command:
    python -u evaluate_v24_motor2_forward_shadow_pg.py
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from db_pg import execute, fetch_all

VERSION = "2026-08-20 v24-motor2-forward-evaluator-v1"

TARGET_DATE = (os.getenv("TARGET_DATE") or "").strip()
SNAPSHOT_KEY = (os.getenv("SNAPSHOT_KEY") or "").strip()
RUN_CLASS = (os.getenv("RUN_CLASS") or "").strip()
WINDOW_NAME = (os.getenv("WINDOW_NAME") or "").strip()
UNIT_YEN = max(1, int(os.getenv("MOTOR2_EVAL_UNIT_YEN", "100")))


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _norm_ticket(v: Any) -> str:
    return str(v or "").strip()


def _where_sql(alias: str = "s") -> Tuple[str, List[Any]]:
    conds: List[str] = []
    params: List[Any] = []

    if TARGET_DATE:
        conds.append(f"{alias}.race_date = %s")
        params.append(TARGET_DATE)
    if SNAPSHOT_KEY:
        conds.append(f"{alias}.snapshot_key = %s")
        params.append(SNAPSHOT_KEY)
    if RUN_CLASS:
        conds.append(f"{alias}.run_class = %s")
        params.append(RUN_CLASS)
    if WINDOW_NAME:
        conds.append(f"{alias}.window_name = %s")
        params.append(WINDOW_NAME)

    return ((" AND " + " AND ".join(conds)) if conds else "", params)


def _fetch_targets() -> List[Dict[str, Any]]:
    extra, params = _where_sql("s")
    sql = f"""
        SELECT
            s.id,
            s.race_id,
            s.race_date,
            s.venue_id,
            s.race_no,
            s.ticket,
            s.odds,
            s.market_rank,
            s.base_prob,
            s.base_prob_rank,
            s.base_raw_ev,
            s.motor2_prob,
            s.motor2_prob_rank,
            s.motor2_raw_ev,
            s.base_low_candidate,
            s.motor2_low_candidate,
            s.base_mid_candidate,
            s.motor2_mid_candidate,
            s.candidate_transition,
            s.run_class,
            s.window_name,
            s.session_scope,
            s.snapshot_key,
            s.result_ticket,
            s.payout_yen,
            s.base_hit,
            s.motor2_hit,
            s.evaluated_at,
            r.result_status,
            r.race_status,
            r.trifecta_ticket AS official_ticket,
            r.trifecta_payout_yen AS official_payout
        FROM v2_v24_motor2_forward_shadow s
        LEFT JOIN v2_results r
          ON r.race_id = s.race_id
        WHERE 1=1
          {extra}
        ORDER BY
            s.race_date,
            s.race_id,
            s.ticket,
            s.id
    """
    return fetch_all(sql, tuple(params))


def _is_result_evaluable(row: Dict[str, Any]) -> bool:
    status = str(row.get("result_status") or "").lower()
    race_status = str(row.get("race_status") or "").lower()
    ticket = _norm_ticket(row.get("official_ticket"))
    payout = _safe_int(row.get("official_payout"), 0)
    return (
        status == "official"
        and race_status == "official"
        and bool(ticket)
        and payout > 0
    )


def _update_row(row: Dict[str, Any]) -> None:
    official_ticket = _norm_ticket(row.get("official_ticket"))
    payout = _safe_int(row.get("official_payout"), 0)
    selected_ticket = _norm_ticket(row.get("ticket"))
    ticket_hit = bool(selected_ticket and selected_ticket == official_ticket)

    base_selected = bool(row.get("base_low_candidate")) or bool(row.get("base_mid_candidate"))
    motor2_selected = bool(row.get("motor2_low_candidate")) or bool(row.get("motor2_mid_candidate"))

    base_hit = bool(base_selected and ticket_hit)
    motor2_hit = bool(motor2_selected and ticket_hit)

    execute(
        """
        UPDATE v2_v24_motor2_forward_shadow
        SET
            result_ticket = %s,
            payout_yen = %s,
            base_hit = %s,
            motor2_hit = %s,
            evaluated_at = now(),
            updated_at = now()
        WHERE id = %s
        """,
        (
            official_ticket,
            payout,
            base_hit,
            motor2_hit,
            row["id"],
        ),
    )


def _stat_new() -> Dict[str, int]:
    return {"bets": 0, "hits": 0, "investment": 0, "return": 0}


def _stat_add(stat: Dict[str, int], selected: bool, hit: bool, payout: int) -> None:
    if not selected:
        return
    stat["bets"] += 1
    stat["investment"] += UNIT_YEN
    if hit:
        stat["hits"] += 1
        stat["return"] += payout


def _fmt_stat(name: str, stat: Dict[str, int]) -> str:
    bets = stat["bets"]
    hits = stat["hits"]
    investment = stat["investment"]
    ret = stat["return"]
    hit_rate = hits / bets * 100 if bets else 0.0
    roi = ret / investment * 100 if investment else 0.0
    profit = ret - investment
    return (
        f"{name}: bets={bets} hits={hits} hit_rate={hit_rate:.2f}% "
        f"investment={investment} return={ret} profit={profit} ROI={roi:.2f}%"
    )


def _report(rows: List[Dict[str, Any]]) -> None:
    stats = {
        "BASE_ALL": _stat_new(),
        "MOTOR2_ALL": _stat_new(),
        "BASE_LOW": _stat_new(),
        "MOTOR2_LOW": _stat_new(),
        "BASE_MID": _stat_new(),
        "MOTOR2_MID": _stat_new(),
        "BOTH": _stat_new(),
        "BASE_ONLY": _stat_new(),
        "MOTOR2_ONLY": _stat_new(),
    }

    transition_counts = defaultdict(int)
    evaluated_rows = 0
    pending_rows = 0
    motor2_only_details: List[Dict[str, Any]] = []

    for row in rows:
        result_ticket = _norm_ticket(row.get("result_ticket"))
        payout = _safe_int(row.get("payout_yen"), 0)
        evaluated = bool(row.get("evaluated_at")) and bool(result_ticket) and payout > 0

        if not evaluated:
            pending_rows += 1
            continue

        evaluated_rows += 1
        ticket_hit = _norm_ticket(row.get("ticket")) == result_ticket

        base_low = bool(row.get("base_low_candidate"))
        motor2_low = bool(row.get("motor2_low_candidate"))
        base_mid = bool(row.get("base_mid_candidate"))
        motor2_mid = bool(row.get("motor2_mid_candidate"))

        base_selected = base_low or base_mid
        motor2_selected = motor2_low or motor2_mid

        _stat_add(stats["BASE_ALL"], base_selected, base_selected and ticket_hit, payout)
        _stat_add(stats["MOTOR2_ALL"], motor2_selected, motor2_selected and ticket_hit, payout)
        _stat_add(stats["BASE_LOW"], base_low, base_low and ticket_hit, payout)
        _stat_add(stats["MOTOR2_LOW"], motor2_low, motor2_low and ticket_hit, payout)
        _stat_add(stats["BASE_MID"], base_mid, base_mid and ticket_hit, payout)
        _stat_add(stats["MOTOR2_MID"], motor2_mid, motor2_mid and ticket_hit, payout)

        trans = str(row.get("candidate_transition") or "")
        transition_counts[trans] += 1

        if trans == "BOTH":
            _stat_add(stats["BOTH"], True, ticket_hit, payout)
        elif trans == "BASE_ONLY":
            _stat_add(stats["BASE_ONLY"], True, ticket_hit, payout)
        elif trans == "MOTOR2_ONLY":
            _stat_add(stats["MOTOR2_ONLY"], True, ticket_hit, payout)
            motor2_only_details.append(row)

    print("=== MOTOR2 FORWARD EVALUATION REPORT ===", flush=True)
    print(f"evaluated_rows={evaluated_rows} pending_rows={pending_rows}", flush=True)

    print("--- ALL CANDIDATES ---", flush=True)
    print(_fmt_stat("BASE_ALL", stats["BASE_ALL"]), flush=True)
    print(_fmt_stat("MOTOR2_ALL", stats["MOTOR2_ALL"]), flush=True)

    base_roi = (
        stats["BASE_ALL"]["return"] / stats["BASE_ALL"]["investment"] * 100
        if stats["BASE_ALL"]["investment"] else 0.0
    )
    motor_roi = (
        stats["MOTOR2_ALL"]["return"] / stats["MOTOR2_ALL"]["investment"] * 100
        if stats["MOTOR2_ALL"]["investment"] else 0.0
    )
    print(f"ROI_DELTA MOTOR2-BASE={motor_roi-base_roi:+.2f}pt", flush=True)

    print("--- LOW ---", flush=True)
    print(_fmt_stat("BASE_LOW", stats["BASE_LOW"]), flush=True)
    print(_fmt_stat("MOTOR2_LOW", stats["MOTOR2_LOW"]), flush=True)

    print("--- MID ---", flush=True)
    print(_fmt_stat("BASE_MID", stats["BASE_MID"]), flush=True)
    print(_fmt_stat("MOTOR2_MID", stats["MOTOR2_MID"]), flush=True)

    print("--- TRANSITIONS ---", flush=True)
    for key in ("BOTH", "BASE_ONLY", "MOTOR2_ONLY", "NEITHER"):
        print(f"{key}: rows={transition_counts.get(key, 0)}", flush=True)

    print(_fmt_stat("BOTH", stats["BOTH"]), flush=True)
    print(_fmt_stat("BASE_ONLY", stats["BASE_ONLY"]), flush=True)
    print(_fmt_stat("MOTOR2_ONLY", stats["MOTOR2_ONLY"]), flush=True)

    if motor2_only_details:
        print("--- MOTOR2_ONLY DETAILS ---", flush=True)
        for row in motor2_only_details[:50]:
            print(
                f"{row.get('race_id')} ticket={row.get('ticket')} "
                f"odds={row.get('odds')} market_rank={row.get('market_rank')} "
                f"base_rank={row.get('base_prob_rank')} "
                f"motor2_rank={row.get('motor2_prob_rank')} "
                f"result={row.get('result_ticket')} payout={row.get('payout_yen')} "
                f"hit={row.get('motor2_hit')}",
                flush=True,
            )

    print("=== REVIEW GUIDE ===", flush=True)
    print(
        "10件=動作確認 / 30件=一次評価 / 50件=中間評価 / "
        "100件=本番候補レビュー。少数件ROIだけでは採用しません。",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        f"✅ evaluate_v24_motor2_forward_shadow_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(
        f"TARGET_DATE={TARGET_DATE or 'ALL'} "
        f"SNAPSHOT_KEY={SNAPSHOT_KEY or 'ALL'} "
        f"RUN_CLASS={RUN_CLASS or 'ALL'} "
        f"WINDOW_NAME={WINDOW_NAME or 'ALL'} "
        f"UNIT_YEN={UNIT_YEN}",
        flush=True,
    )
    print(
        "UPDATE_SCOPE=v2_v24_motor2_forward_shadow evaluation columns only",
        flush=True,
    )
    print("LINE=0 BUY=0 PROD_V24_CHANGE=0 N02_CHANGE=0", flush=True)

    rows = _fetch_targets()

    updated_rows = 0
    result_not_ready = 0
    already_evaluated = 0

    for row in rows:
        if not _is_result_evaluable(row):
            result_not_ready += 1
            continue

        if (
            row.get("evaluated_at") is not None
            and _norm_ticket(row.get("result_ticket"))
            == _norm_ticket(row.get("official_ticket"))
            and _safe_int(row.get("payout_yen"), 0)
            == _safe_int(row.get("official_payout"), 0)
        ):
            already_evaluated += 1
            continue

        _update_row(row)
        updated_rows += 1

    print("=== UPDATE SUMMARY ===", flush=True)
    print(f"rows_loaded={len(rows)}", flush=True)
    print(f"updated_rows={updated_rows}", flush=True)
    print(f"already_evaluated={already_evaluated}", flush=True)
    print(f"result_not_ready={result_not_ready}", flush=True)

    rows_after = _fetch_targets()
    _report(rows_after)

    print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()