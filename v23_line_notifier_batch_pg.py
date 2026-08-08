# -*- coding: utf-8 -*-
"""
v23_line_notifier_batch_pg.py

Railway Postgres版。
v22_realtime_decisions の BUY 判定だけを LINE Messaging API で通知します。

2026-07-09 修正:
- 最終BUY通知のLINE上限を仮候補通知と分離。
- FINAL_IGNORE_DAILY_LIMIT=1 の場合、最終BUY通知は日次上限では止めず、月間上限のみ確認。
- FINAL_DAILY_LINE_LIMIT は FINAL_IGNORE_DAILY_LIMIT=0 の場合だけ使用。
- MONTHLY_LINE_LIMIT のデフォルトを150に変更。

Railway Start Command:
    python -u v23_line_notifier_batch_pg.py

通常は run_v23_pg.py / v25_final_realtime_pipeline_pg.py から起動してください。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import requests

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    Jsonb = lambda x: json.dumps(x, ensure_ascii=False)  # type: ignore

from db_pg import execute, fetch_all, fetch_one

JST = timezone(timedelta(hours=9))

VENUE_NAMES = {
    "01": "桐生",
    "02": "戸田",
    "03": "江戸川",
    "04": "平和島",
    "05": "多摩川",
    "06": "浜名湖",
    "07": "蒲郡",
    "08": "常滑",
    "09": "津",
    "10": "三国",
    "11": "びわこ",
    "12": "住之江",
    "13": "尼崎",
    "14": "鳴門",
    "15": "丸亀",
    "16": "児島",
    "17": "宮島",
    "18": "徳山",
    "19": "下関",
    "20": "若松",
    "21": "芦屋",
    "22": "福岡",
    "23": "唐津",
    "24": "大村",
}


def _venue_display(venue_id: object) -> str:
    code = str(venue_id or "").zfill(2)
    name = VENUE_NAMES.get(code)
    return f"{name}（{code}）" if name else f"{code}場"


def _parse_target_race_ids() -> set[str]:
    raw = (os.getenv("TARGET_RACE_IDS") or "").strip()
    if not raw:
        return set()
    return {
        value.strip()
        for value in re.split(r"[,\s]+", raw)
        if value.strip()
    }


TARGET_RACE_ID_SET = _parse_target_race_ids()


LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_TO = (
    os.getenv("LINE_TO")
    or os.getenv("LINE_USER_ID")
    or os.getenv("LINE_GROUP_ID")
    or ""
).strip()

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
DECISION_LABEL = os.getenv("DECISION_LABEL", os.getenv("SNAPSHOT_LABEL", "final_ab")).strip()
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower()

DRY_RUN = os.getenv("DRY_RUN", "1").strip() in ("1", "true", "True", "yes", "YES")
MAX_SEND = int(os.getenv("MAX_SEND", "10"))
BATCH_NOTIFY = os.getenv("BATCH_NOTIFY", "1").strip() not in ("0", "false", "False", "no", "NO")
MAX_ITEMS_PER_MESSAGE = int(os.getenv("MAX_ITEMS_PER_MESSAGE", "6"))

# final BUY通知は仮候補通知と上限を分離する。
# FINAL_IGNORE_DAILY_LIMIT=1 なら、日次上限では止めず月間上限だけ確認する。
FINAL_DAILY_LINE_LIMIT = int(os.getenv("FINAL_DAILY_LINE_LIMIT", os.getenv("DAILY_LINE_LIMIT", "5")))
FINAL_IGNORE_DAILY_LIMIT = os.getenv("FINAL_IGNORE_DAILY_LIMIT", "1").strip() in ("1", "true", "True", "yes", "YES")
MONTHLY_LINE_LIMIT = int(os.getenv("MONTHLY_LINE_LIMIT", "150"))

# 互換表示用。内部の上限判定では FINAL_* を使用する。
DAILY_LINE_LIMIT = FINAL_DAILY_LINE_LIMIT

TEST_MODE = os.getenv("TEST_MODE", "1").strip() not in ("0", "false", "False", "no", "NO")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "35"))


def _require_settings() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")
    if not DRY_RUN and (not LINE_CHANNEL_ACCESS_TOKEN or not LINE_TO):
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN と LINE_TO/LINE_USER_ID が必要です。DRY_RUN=1なら送信せず確認できます。")


def _now_iso() -> str:
    return datetime.now(JST).isoformat()


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(str(v).replace(",", "")))
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace(",", ""))
    except Exception:
        return default


def _month_next(date_str: str) -> str:
    y = int(date_str[:4])
    m = int(date_str[5:7])
    if m == 12:
        return f"{y + 1:04d}-01-01"
    return f"{y:04d}-{m + 1:02d}-01"


def _month_start(date_str: str) -> str:
    return date_str[:7] + "-01"


def _ensure_schema() -> None:
    ddl = [
        """
        create table if not exists v2_line_notifications (
            id bigserial primary key
        );
        """,
        "alter table v2_line_notifications add column if not exists race_id text;",
        "alter table v2_line_notifications add column if not exists race_date date;",
        "alter table v2_line_notifications add column if not exists venue_id text;",
        "alter table v2_line_notifications add column if not exists venue_code text;",
        "alter table v2_line_notifications add column if not exists race_no integer;",
        "alter table v2_line_notifications add column if not exists decision_id text;",
        "alter table v2_line_notifications add column if not exists sent_at timestamptz;",
        "alter table v2_line_notifications add column if not exists status text;",
        "alter table v2_line_notifications add column if not exists line_to text;",
        "alter table v2_line_notifications add column if not exists message_type text;",
        "alter table v2_line_notifications add column if not exists message_text text;",
        "alter table v2_line_notifications add column if not exists selector_version text;",
        "alter table v2_line_notifications add column if not exists selector_mode text;",
        "alter table v2_line_notifications add column if not exists mode_name text;",
        "alter table v2_line_notifications add column if not exists ticket text;",
        "alter table v2_line_notifications add column if not exists odds numeric;",
        "alter table v2_line_notifications add column if not exists line_response_status integer;",
        "alter table v2_line_notifications add column if not exists line_response_body text;",
        "alter table v2_line_notifications add column if not exists error_message text;",
        "alter table v2_line_notifications add column if not exists raw jsonb;",
        "alter table v2_line_notifications add column if not exists created_at timestamptz default now();",
        "alter table v2_line_notifications add column if not exists updated_at timestamptz;",
        "alter table v2_realtime_decisions add column if not exists notification_id text;",
        "alter table v2_realtime_decisions add column if not exists updated_at timestamptz;",
        "create index if not exists idx_v2_line_notifications_date_status on v2_line_notifications (race_date, status);",
        "create index if not exists idx_v2_line_notifications_race_ticket on v2_line_notifications (race_date, race_id, ticket, status);",
    ]
    for sql in ddl:
        execute(sql)


def count_sent_notifications() -> Dict[str, int]:
    day = fetch_all(
        """
        select id
        from v2_line_notifications
        where race_date = %s and status = 'sent';
        """,
        (TARGET_DATE,),
    )
    month = fetch_all(
        """
        select id
        from v2_line_notifications
        where race_date >= %s and race_date < %s and status = 'sent';
        """,
        (_month_start(TARGET_DATE), _month_next(TARGET_DATE)),
    )
    return {"day": len(day), "month": len(month)}


def _usage_guard() -> Optional[str]:
    counts = count_sent_notifications()

    # final BUY通知は重要度が高いので、デフォルトでは日次上限では止めない。
    # 月間上限だけはLINE Developers側の上限保護として確認する。
    if not FINAL_IGNORE_DAILY_LIMIT and counts["day"] >= FINAL_DAILY_LINE_LIMIT:
        return f"final_daily_limit_reached {counts['day']}/{FINAL_DAILY_LINE_LIMIT}"

    if counts["month"] >= MONTHLY_LINE_LIMIT:
        return f"monthly_limit_reached {counts['month']}/{MONTHLY_LINE_LIMIT}"

    return None


def _already_sent_keys_for_date() -> Set[str]:
    """
    final BUY通知の重複だけを防ぐ。

    fix2:
    - DRY_RUN時は本文確認を優先するため重複除外しない。
    - pre候補通知とfinal BUY通知は別物なので、pre候補のsent履歴では弾かない。
    - 本送信時は final_buy 系、または v22 selector_version の通知履歴だけで重複除外する。
    """
    if DRY_RUN:
        return set()

    rows = fetch_all(
        """
        select race_id, ticket, status, message_type, selector_version
        from v2_line_notifications
        where race_date = %s
          and status = 'sent'
          and (
                coalesce(message_type, '') in ('final_buy', 'final_buy_batch')
                or coalesce(selector_version, '') in ('v22_realtime_decision_engine', 'v22_realtime_decision_engine_pg')
          );
        """,
        (TARGET_DATE,),
    )
    keys: Set[str] = set()
    for r in rows:
        rid = str(r.get("race_id") or "")
        ticket = str(r.get("ticket") or "")
        if rid and ticket:
            keys.add(f"{rid}|{ticket}")
    return keys


def fetch_buy_decisions() -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        select *
        from v2_realtime_decisions
        where race_date = %s
          and decision_label = %s
          and selector_mode = %s
          and recommendation = 'buy'
          and coalesce(was_notified, false) = false
        order by final_score desc nulls last, decision_at asc nulls last
        limit %s;
        """,
        (TARGET_DATE, DECISION_LABEL, SELECTOR_MODE, MAX_SEND * 3),
    )
    # v25 targeted pipelineから渡された今回の締切ウィンドウ対象だけを通知対象にする。
    # TARGET_RACE_IDSが空の場合は「今回対象0件」と解釈し、過去の未通知BUYを送らない。
    if "TARGET_RACE_IDS" in os.environ:
        if not TARGET_RACE_ID_SET:
            print(
                "TARGET_RACE_IDS is empty: 今回の締切ウィンドウ対象0件のため、"
                "過去の未通知BUYは送信しません。",
                flush=True,
            )
            return []
        before_target_filter = len(rows)
        rows = [
            row for row in rows
            if str(row.get("race_id") or "") in TARGET_RACE_ID_SET
        ]
        print(
            f"TARGET_RACE_IDS filter: before={before_target_filter} "
            f"after={len(rows)} targets={len(TARGET_RACE_ID_SET)}",
            flush=True,
        )

    sent_keys = _already_sent_keys_for_date()
    if DRY_RUN:
        print("DRY_RUNのため重複通知チェックはスキップします。", flush=True)

    filtered: List[Dict[str, Any]] = []
    skipped_dup = 0
    for r in rows:
        key = f"{r.get('race_id')}|{r.get('ticket')}"
        if key in sent_keys:
            skipped_dup += 1
            continue
        filtered.append(r)
        if len(filtered) >= MAX_SEND:
            break
    if skipped_dup:
        print(f"final_buy_dedup_skipped={skipped_dup}", flush=True)
    return filtered


def _reasons_text(v: Any) -> str:
    if isinstance(v, list):
        return " / ".join(str(x) for x in v[:4] if x)
    if isinstance(v, str):
        return v
    return ""


def build_message(d: Dict[str, Any]) -> str:
    raw = d.get("raw") or {}
    candidate = raw.get("candidate") if isinstance(raw, dict) else {}
    race_title = candidate.get("race_title") if isinstance(candidate, dict) else ""

    race_id = d.get("race_id", "")
    venue_id = str(d.get("venue_id", "")).zfill(2)
    race_no = _safe_int(d.get("race_no"), 0)
    ticket = d.get("ticket", "")
    odds = _safe_float(d.get("odds"), 0.0)
    expected = _safe_int(d.get("expected_return_yen"), int(round(odds * 100)))
    mode_label = d.get("mode_label") or d.get("mode_name") or ""
    final_score = _safe_float(d.get("final_score"), 0.0)
    rt_score = _safe_float(d.get("realtime_score"), 0.0)
    prob_rank = _safe_int(d.get("prob_rank"), 999)
    market_rank = _safe_int(d.get("market_rank"), 999)
    pos = _reasons_text(d.get("positive_reasons"))
    neg = _reasons_text(d.get("negative_reasons"))

    lines = [
        "【競艇AI テストBUY通知・購入しない】" if TEST_MODE else "【競艇AI BUY通知】",
        f"{TARGET_DATE} {_venue_display(venue_id)} {race_no}R",
        f"買い目: {ticket}",
        f"オッズ: {odds:.1f}倍 / 想定回収: {expected}円",
        f"モード: {mode_label}",
        f"rank: prob={prob_rank} market={market_rank}",
        f"score: final={final_score:g} realtime={rt_score:g}",
    ]
    if race_title:
        lines.append(f"開催: {race_title}")
    if pos:
        lines.append(f"プラス: {pos}")
    if neg:
        lines.append(f"注意: {neg}")
    lines.append(f"race_id: {race_id}")
    return "\n".join(lines)


def build_batch_message(decisions: List[Dict[str, Any]]) -> str:
    lines = [
        "【競艇AI テストBUY通知まとめ・購入しない】" if TEST_MODE else "【競艇AI BUY通知まとめ】",
        f"{TARGET_DATE} / {DECISION_LABEL} / {SELECTOR_MODE}",
        f"対象: {len(decisions)}件",
        "",
    ]
    for idx, d in enumerate(decisions[:MAX_ITEMS_PER_MESSAGE], start=1):
        raw = d.get("raw") or {}
        candidate = raw.get("candidate") if isinstance(raw, dict) else {}
        race_title = candidate.get("race_title") if isinstance(candidate, dict) else ""
        venue_id = str(d.get("venue_id", "")).zfill(2)
        race_no = _safe_int(d.get("race_no"), 0)
        ticket = d.get("ticket", "")
        odds = _safe_float(d.get("odds"), 0.0)
        mode_label = d.get("mode_label") or d.get("mode_name") or ""
        rt_score = _safe_float(d.get("realtime_score"), 0.0)
        pos = _reasons_text(d.get("positive_reasons"))
        neg = _reasons_text(d.get("negative_reasons"))
        lines.append(f"{idx}. {_venue_display(venue_id)} {race_no}R {ticket} / {odds:.1f}倍")
        lines.append(f"   {mode_label} / score={rt_score:g}")
        if pos:
            lines.append(f"   + {pos}")
        if neg:
            lines.append(f"   注意: {neg}")
        if race_title:
            lines.append(f"   {race_title[:40]}")
        lines.append("")
    if len(decisions) > MAX_ITEMS_PER_MESSAGE:
        lines.append(f"他 {len(decisions) - MAX_ITEMS_PER_MESSAGE}件あり")
    lines.append("※1回の通知にまとめて送信")
    if TEST_MODE:
        lines.append("※テスト期間中：購入しない")
    if DRY_RUN:
        lines.append("※DRY_RUN：LINE送信なし")
    return "\n".join(lines)[:4900]


def send_line_message(text: str) -> Dict[str, Any]:
    if DRY_RUN:
        return {"dry_run": True, "status_code": 200, "body": "DRY_RUN"}
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"to": LINE_TO, "messages": [{"type": "text", "text": text[:4900]}]}
    r = requests.post(url, headers=headers, data=json.dumps(payload, ensure_ascii=False), timeout=HTTP_TIMEOUT)
    return {"dry_run": False, "status_code": r.status_code, "body": r.text[:1000]}


def insert_notification(decision: Dict[str, Any], message_text: str, status: str, resp: Dict[str, Any], error: str = "", batch: bool = False) -> Optional[str]:
    row = fetch_one(
        """
        insert into v2_line_notifications (
            race_id, race_date, venue_id, venue_code, race_no,
            decision_id, sent_at, status, line_to, message_type, message_text,
            selector_version, selector_mode, mode_name, ticket, odds,
            line_response_status, line_response_body, error_message, raw, updated_at
        )
        values (
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s
        )
        returning id;
        """,
        (
            decision.get("race_id"),
            decision.get("race_date"),
            str(decision.get("venue_id") or "").zfill(2),
            str(decision.get("venue_id") or "").zfill(2),
            decision.get("race_no"),
            str(decision.get("id") or ""),
            _now_iso(),
            status,
            LINE_TO if not DRY_RUN else "DRY_RUN",
            "final_buy_batch" if batch else "final_buy",
            message_text,
            decision.get("selector_version"),
            decision.get("selector_mode"),
            decision.get("mode_name"),
            decision.get("ticket"),
            decision.get("odds"),
            resp.get("status_code"),
            resp.get("body"),
            error,
            Jsonb({"response": resp, "dry_run": DRY_RUN}),
            _now_iso(),
        ),
    )
    if row and row.get("id") is not None:
        return str(row.get("id"))
    return None


def mark_decision_notified(decision_id: str, notification_id: Optional[str]) -> None:
    if not decision_id:
        return
    execute(
        """
        update v2_realtime_decisions
        set was_notified = true,
            notification_id = %s,
            updated_at = %s
        where id = %s;
        """,
        (str(notification_id or ""), _now_iso(), decision_id),
    )


def main() -> None:
    _require_settings()
    _ensure_schema()
    print("✅ v23_line_notifier_batch_pg.py VERSION 2026-08-08 venue-name-target-scope-v2", flush=True)
    print(
        f"TARGET_DATE={TARGET_DATE} DECISION_LABEL={DECISION_LABEL} SELECTOR_MODE={SELECTOR_MODE} "
        f"DRY_RUN={DRY_RUN} MAX_SEND={MAX_SEND} BATCH_NOTIFY={BATCH_NOTIFY} "
        f"FINAL_DAILY_LINE_LIMIT={FINAL_DAILY_LINE_LIMIT} FINAL_IGNORE_DAILY_LIMIT={FINAL_IGNORE_DAILY_LIMIT} "
        f"MONTHLY_LINE_LIMIT={MONTHLY_LINE_LIMIT} TEST_MODE={TEST_MODE}",
        flush=True,
    )
    if "TARGET_RACE_IDS" in os.environ:
        print(
            f"TARGET_RACE_IDS scope enabled: {len(TARGET_RACE_ID_SET)} races",
            flush=True,
        )
    else:
        print("TARGET_RACE_IDS scope disabled", flush=True)

    # DRY_RUNではLINE送信しないため、送信上限ガードは通さない。
    # 本送信時だけ月間上限、必要ならfinal日次上限を確認する。
    guard = None if DRY_RUN else _usage_guard()
    if guard:
        print(f"LINE送信上限ガード: {guard}", flush=True)
        print("=== v23 PG batch LINE通知終了 ===", flush=True)
        return
    if DRY_RUN:
        print("DRY_RUNのためLINE送信上限ガードはスキップします。", flush=True)
    elif FINAL_IGNORE_DAILY_LIMIT:
        print("FINAL_IGNORE_DAILY_LIMIT=1 のためfinal BUYの日次上限ガードはスキップします。月間上限のみ確認します。", flush=True)

    decisions = fetch_buy_decisions()
    print(f"pending_buy_decisions={len(decisions)}", flush=True)
    if not decisions:
        print("LINE通知対象はありません。見送りです。", flush=True)
        print("=== v23 PG batch LINE通知終了 ===", flush=True)
        return

    decisions = decisions[:MAX_SEND]
    sent_api_calls = 0
    failed = 0
    dry_run_records = 0

    if BATCH_NOTIFY:
        msg = build_batch_message(decisions)
        print("\n--- batch message ---", flush=True)
        print(msg, flush=True)
        try:
            resp = send_line_message(msg)
            ok = 200 <= int(resp.get("status_code", 0)) < 300
            status = "dry_run" if DRY_RUN else ("sent" if ok else "failed")
            nid = insert_notification(decisions[0], msg, status, resp, batch=True)
            if ok and not DRY_RUN:
                for d in decisions:
                    mark_decision_notified(str(d.get("id")), nid)
                sent_api_calls = 1
            elif ok and DRY_RUN:
                dry_run_records = 1
            else:
                failed = 1
                print(f"LINE送信失敗: {resp}", flush=True)
        except Exception as e:
            failed = 1
            try:
                insert_notification(decisions[0], msg, "failed", {"status_code": 0, "body": ""}, error=repr(e), batch=True)
            except Exception:
                pass
            print(f"ERROR: {repr(e)}", flush=True)
    else:
        for i, d in enumerate(decisions, start=1):
            msg = build_message(d)
            print(f"\n--- message {i}/{len(decisions)} ---", flush=True)
            print(msg, flush=True)
            try:
                resp = send_line_message(msg)
                ok = 200 <= int(resp.get("status_code", 0)) < 300
                status = "dry_run" if DRY_RUN else ("sent" if ok else "failed")
                nid = insert_notification(d, msg, status, resp)
                if ok and not DRY_RUN:
                    mark_decision_notified(str(d.get("id")), nid)
                    sent_api_calls += 1
                elif ok and DRY_RUN:
                    dry_run_records += 1
                else:
                    failed += 1
                    print(f"LINE送信失敗: {resp}", flush=True)
            except Exception as e:
                failed += 1
                try:
                    insert_notification(d, msg, "failed", {"status_code": 0, "body": ""}, error=repr(e))
                except Exception:
                    pass
                print(f"ERROR: {repr(e)}", flush=True)

    print("\n=== v23 PG batch LINE通知 summary ===", flush=True)
    print(f"sent_api_calls={sent_api_calls} failed={failed} dry_run={DRY_RUN} dry_run_records={dry_run_records} batch={BATCH_NOTIFY}", flush=True)
    print("=== v23 PG batch LINE通知終了 ===", flush=True)


if __name__ == "__main__":
    main()