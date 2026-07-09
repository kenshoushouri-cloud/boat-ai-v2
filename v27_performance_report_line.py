# -*- coding: utf-8 -*-
"""
v27_performance_report_line.py
Railway Postgres版 月次成績レポートLINE通知。Supabaseは使用しません。
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from psycopg.types.json import Jsonb
except Exception:
    Jsonb = lambda x: json.dumps(x, ensure_ascii=False)  # type: ignore

from db_pg import execute, fetch_all, fetch_one

JST = timezone(timedelta(hours=9))
now_jst = datetime.now(JST)
prev_month = now_jst.replace(day=1) - timedelta(days=1)
TARGET_MONTH = os.getenv("TARGET_MONTH") or prev_month.strftime("%Y-%m")
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"
DRY_RUN = os.getenv("DRY_RUN", "1").strip() in ("1", "true", "True", "yes", "YES")
TEST_MODE = os.getenv("TEST_MODE", "1").strip() not in ("0", "false", "False", "no", "NO")
REPORT_DAILY_LINE_LIMIT = int(os.getenv("REPORT_DAILY_LINE_LIMIT", os.getenv("DAILY_LINE_LIMIT", "1")))
MONTHLY_LINE_LIMIT = int(os.getenv("MONTHLY_LINE_LIMIT", "150"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "35"))
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_TO = (os.getenv("LINE_TO") or os.getenv("LINE_USER_ID") or os.getenv("LINE_GROUP_ID") or "").strip()


def _month_bounds(ym: str) -> Tuple[str, str]:
    y, m = int(ym[:4]), int(ym[5:7])
    start = f"{y:04d}-{m:02d}-01"
    end = f"{y + 1:04d}-01-01" if m == 12 else f"{y:04d}-{m + 1:02d}-01"
    return start, end


PERIOD_START, PERIOD_END = _month_bounds(TARGET_MONTH)
CURRENT_MONTH_START, CURRENT_MONTH_END = _month_bounds(now_jst.strftime("%Y-%m"))


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(str(v).replace(",", "")))
    except Exception:
        return default


def _yen(v: int) -> str:
    return f"{int(v):,}円"


def _pct(num: int, den: int) -> str:
    return "-" if den <= 0 else f"{num / den * 100:.1f}%"


def _roi(ret: int, inv: int) -> str:
    return "-" if inv <= 0 else f"{ret / inv * 100:.1f}%"


def _now_iso() -> str:
    return datetime.now(JST).isoformat()


def _require_settings() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")
    if not DRY_RUN and (not LINE_CHANNEL_ACCESS_TOKEN or not LINE_TO):
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN と LINE_TO/LINE_USER_ID が必要です。")


def _ensure_line_schema() -> None:
    ddl = [
        "create table if not exists v2_line_notifications (id bigserial primary key);",
        "alter table v2_line_notifications add column if not exists race_date date;",
        "alter table v2_line_notifications add column if not exists sent_at timestamptz;",
        "alter table v2_line_notifications add column if not exists status text;",
        "alter table v2_line_notifications add column if not exists line_to text;",
        "alter table v2_line_notifications add column if not exists message_type text;",
        "alter table v2_line_notifications add column if not exists message_text text;",
        "alter table v2_line_notifications add column if not exists selector_mode text;",
        "alter table v2_line_notifications add column if not exists line_response_status integer;",
        "alter table v2_line_notifications add column if not exists line_response_body text;",
        "alter table v2_line_notifications add column if not exists error_message text;",
        "alter table v2_line_notifications add column if not exists raw jsonb;",
        "alter table v2_line_notifications add column if not exists created_at timestamptz default now();",
        "alter table v2_line_notifications add column if not exists updated_at timestamptz;",
        "create index if not exists idx_v2_line_notifications_type_date on v2_line_notifications (message_type, race_date, status);",
    ]
    for sql in ddl:
        execute(sql)


def _count(sql: str, params: tuple = ()) -> int:
    row = fetch_one(sql, params)
    return _safe_int(row.get("n") if row else 0)


def _columns(table: str) -> set[str]:
    rows = fetch_all(
        """
        select column_name from information_schema.columns
        where table_schema='public' and table_name=%s;
        """,
        (table,),
    )
    return {str(r.get("column_name")) for r in rows}


def _first_col(table: str, candidates: List[str]) -> Optional[str]:
    cols = _columns(table)
    for c in candidates:
        if c in cols:
            return c
    return None


def _table_exists(table: str) -> bool:
    row = fetch_one(
        """
        select exists(
          select 1 from information_schema.tables
          where table_schema='public' and table_name=%s
        ) as ok;
        """,
        (table,),
    )
    return bool(row and row.get("ok"))


def _usage_guard() -> Optional[str]:
    monthly_report = _count(
        """
        select count(*) as n from v2_line_notifications
        where race_date=%s and status='sent' and message_type='monthly_report';
        """,
        (PERIOD_START,),
    )
    current_month_all = _count(
        """
        select count(*) as n from v2_line_notifications
        where race_date >= %s and race_date < %s and status='sent';
        """,
        (CURRENT_MONTH_START, CURRENT_MONTH_END),
    )
    if monthly_report >= REPORT_DAILY_LINE_LIMIT:
        return f"monthly_report_limit_reached {monthly_report}/{REPORT_DAILY_LINE_LIMIT}"
    if current_month_all >= MONTHLY_LINE_LIMIT:
        return f"monthly_limit_reached {current_month_all}/{MONTHLY_LINE_LIMIT}"
    return None


def _send_line(text: str) -> Dict[str, Any]:
    if DRY_RUN:
        return {"status_code": 200, "body": "DRY_RUN", "dry_run": True}
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"to": LINE_TO, "messages": [{"type": "text", "text": text[:4900]}]}
    r = requests.post(url, headers=headers, data=json.dumps(payload, ensure_ascii=False), timeout=HTTP_TIMEOUT)
    return {"status_code": r.status_code, "body": r.text[:1000], "dry_run": False}


def _insert_report(text: str, status: str, resp: Dict[str, Any], error: str = "") -> None:
    execute(
        """
        insert into v2_line_notifications
          (race_date, sent_at, status, line_to, message_type, message_text,
           selector_mode, line_response_status, line_response_body, error_message, raw, updated_at)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
        """,
        (
            PERIOD_START,
            _now_iso(),
            status,
            LINE_TO if not DRY_RUN else "DRY_RUN",
            "monthly_report",
            text,
            SELECTOR_MODE,
            resp.get("status_code"),
            resp.get("body"),
            error,
            Jsonb({"response": resp, "dry_run": DRY_RUN, "target_month": TARGET_MONTH}),
            _now_iso(),
        ),
    )


def _result_ticket_payout(race_id: str) -> Tuple[str, int]:
    if not race_id or not _table_exists("v2_results"):
        return "", 0
    ticket_col = _first_col("v2_results", ["trifecta_ticket", "sanrentan_ticket", "trifecta_result", "result_ticket", "ticket"])
    payout_col = _first_col("v2_results", ["trifecta_payout_yen", "trifecta_payout", "payout_yen", "return_yen", "trifecta_return_yen"])
    if not ticket_col:
        return "", 0
    payout_sql = f", {payout_col} as payout" if payout_col else ", 0 as payout"
    row = fetch_one(f"select {ticket_col} as ticket {payout_sql} from v2_results where race_id=%s limit 1;", (race_id,))
    if not row:
        return "", 0
    return str(row.get("ticket") or ""), _safe_int(row.get("payout"), 0)


def _fetch_decisions() -> List[Dict[str, Any]]:
    if not _table_exists("v2_realtime_decisions"):
        return []
    cols = _columns("v2_realtime_decisions")
    where = ["race_date >= %s", "race_date < %s"]
    params: List[Any] = [PERIOD_START, PERIOD_END]
    if "selector_mode" in cols:
        where.append("selector_mode=%s")
        params.append(SELECTOR_MODE)
    return fetch_all(f"select * from v2_realtime_decisions where {' and '.join(where)} order by race_date asc, decision_at asc nulls last;", tuple(params))


def _summarize(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    buy = [d for d in decisions if str(d.get("recommendation") or "").lower() == "buy"]
    rank = defaultdict(lambda: {"decisions": 0, "buy": 0, "hit": 0, "investment": 0, "return": 0})
    cache: Dict[str, Tuple[str, int]] = {}
    hit = 0
    ret = 0
    for d in decisions:
        label = str(d.get("mode_label") or d.get("mode_name") or d.get("rank_label") or "未分類")
        rank[label]["decisions"] += 1
        if str(d.get("recommendation") or "").lower() != "buy":
            continue
        rank[label]["buy"] += 1
        rank[label]["investment"] += 100
        rid, ticket = str(d.get("race_id") or ""), str(d.get("ticket") or "")
        if rid not in cache:
            cache[rid] = _result_ticket_payout(rid)
        result_ticket, payout = cache.get(rid, ("", 0))
        if ticket and result_ticket and ticket == result_ticket:
            hit += 1
            ret += payout
            rank[label]["hit"] += 1
            rank[label]["return"] += payout
    inv = len(buy) * 100
    return {"decisions": len(decisions), "buy": len(buy), "hit": hit, "investment": inv, "return": ret, "profit": ret - inv, "rank": rank}


def _build_message(race_count: int, active_days: int, s: Dict[str, Any]) -> str:
    lines = [
        "【競艇AI 月次成績レポート】",
        "※テスト運用中・購入しない集計" if TEST_MODE else "※本番運用集計",
        f"対象月: {TARGET_MONTH}",
        "",
        f"【{TARGET_MONTH} 月間成績】",
        f"稼働日: {active_days}日 / 対象R: {race_count}",
        f"判定: {s['decisions']}件 / BUY: {s['buy']}件",
        f"的中: {s['hit']}件 / 的中率: {_pct(s['hit'], s['buy'])}",
        f"投資: {_yen(s['investment'])}",
        f"回収: {_yen(s['return'])}",
        f"損益: {_yen(s['profit'])}",
        f"回収率: {_roi(s['return'], s['investment'])}",
        "",
        f"【{TARGET_MONTH} ランク別】",
    ]
    if not s["rank"]:
        lines.append("データなし")
    else:
        for label, r in sorted(s["rank"].items(), key=lambda kv: kv[0]):
            lines.append(
                f"{label}: 判定{r['decisions']} / BUY{r['buy']} / 的中{r['hit']} / "
                f"的中率{_pct(r['hit'], r['buy'])} / 回収率{_roi(r['return'], r['investment'])} / "
                f"損益{_yen(r['return'] - r['investment'])}"
            )
    if DRY_RUN:
        lines += ["", "※DRY_RUN：LINE送信なし"]
    return "\n".join(lines)[:4900]


def main() -> None:
    print("✅ v27_performance_report_line.py VERSION 2026-07-09 railway-postgres", flush=True)
    print(f"TARGET_MONTH={TARGET_MONTH} PERIOD={PERIOD_START}..{PERIOD_END} SELECTOR_MODE={SELECTOR_MODE} DRY_RUN={DRY_RUN} TEST_MODE={TEST_MODE} REPORT_DAILY_LINE_LIMIT={REPORT_DAILY_LINE_LIMIT} MONTHLY_LINE_LIMIT={MONTHLY_LINE_LIMIT}", flush=True)
    _require_settings()
    _ensure_line_schema()
    race_count = _count("select count(*) as n from v2_races where race_date >= %s and race_date < %s;", (PERIOD_START, PERIOD_END)) if _table_exists("v2_races") else 0
    active_days = _count("select count(distinct race_date) as n from v2_races where race_date >= %s and race_date < %s;", (PERIOD_START, PERIOD_END)) if _table_exists("v2_races") else 0
    decisions = _fetch_decisions()
    summary = _summarize(decisions)
    msg = _build_message(race_count, active_days, summary)
    print("\n--- monthly report message ---", flush=True)
    print(msg, flush=True)
    guard = None if DRY_RUN else _usage_guard()
    if guard:
        print(f"LINE送信上限ガード: {guard}", flush=True)
        print("=== monthly performance report 終了 ===", flush=True)
        return
    resp = _send_line(msg)
    ok = 200 <= int(resp.get("status_code", 0)) < 300
    status = "dry_run" if DRY_RUN else ("sent" if ok else "failed")
    _insert_report(msg, status, resp, "" if ok else str(resp))
    if not ok:
        raise RuntimeError(f"LINE送信失敗: {resp}")
    print(f"LINE response status={resp.get('status_code')}", flush=True)
    print("✅ monthly report done", flush=True)
    print("=== monthly performance report 終了 ===", flush=True)


if __name__ == "__main__":
    main()