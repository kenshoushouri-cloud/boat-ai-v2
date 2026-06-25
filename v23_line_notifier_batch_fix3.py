# -*- coding: utf-8 -*-
"""
v23_line_notifier_batch_fix3.py

競艇AI v2 LINE通知スクリプト。
v22_realtime_decisions の BUY 判定だけを LINE Messaging API で通知する。

Railway Start Command:
    python v23_line_notifier_batch_fix3.py

任意Variables:
    TARGET_DATE=YYYY-MM-DD
    DECISION_LABEL=manual_fix2
    SELECTOR_MODE=balanced
    DRY_RUN=1
    LINE_CHANNEL_ACCESS_TOKEN=...
    LINE_TO=... または LINE_USER_ID=...
"""

from __future__ import annotations

import json
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

JST = timezone(timedelta(hours=9))

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation",
}

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_TO = (
    os.getenv("LINE_TO")
    or os.getenv("LINE_USER_ID")
    or os.getenv("LINE_GROUP_ID")
    or ""
).strip()

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
DECISION_LABEL = os.getenv("DECISION_LABEL", os.getenv("SNAPSHOT_LABEL", "manual_fix2")).strip()
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "balanced").strip().lower()

DRY_RUN = os.getenv("DRY_RUN", "0").strip() in ("1", "true", "True", "yes", "YES")
MAX_SEND = int(os.getenv("MAX_SEND", "10"))
BATCH_NOTIFY = os.getenv("BATCH_NOTIFY", "1").strip() not in ("0", "false", "False", "no", "NO")
MAX_ITEMS_PER_MESSAGE = int(os.getenv("MAX_ITEMS_PER_MESSAGE", "6"))
DAILY_LINE_LIMIT = int(os.getenv("DAILY_LINE_LIMIT", "3"))
MONTHLY_LINE_LIMIT = int(os.getenv("MONTHLY_LINE_LIMIT", "180"))
TEST_MODE = os.getenv("TEST_MODE", "1").strip() not in ("0", "false", "False", "no", "NO")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "35"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "2"))
RETRY_SLEEP_SEC = float(os.getenv("RETRY_SLEEP_SEC", "2.0"))


def _require_settings() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY が必要です。")
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


def _rest_get(table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
    query = urllib.parse.urlencode(params, safe=",.*()")
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    last = None
    for attempt in range(RETRY_MAX + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:600]}")
            return r.json()
        except Exception as e:
            last = e
            if attempt < RETRY_MAX:
                import time
                time.sleep(RETRY_SLEEP_SEC)
    raise RuntimeError(f"GET {table} failed: {last}")


def _rest_insert(table: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(
        url,
        headers=HEADERS,
        data=json.dumps(row, ensure_ascii=False),
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"INSERT {table} failed {r.status_code}: {r.text[:800]}")
    try:
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
    except Exception:
        pass
    return None


def _rest_patch(table: str, params: Dict[str, str], row: Dict[str, Any]) -> int:
    query = urllib.parse.urlencode(params, safe=",.*()")
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    headers = dict(HEADERS)
    headers["Prefer"] = "return=minimal"
    r = requests.patch(
        url,
        headers=headers,
        data=json.dumps(row, ensure_ascii=False),
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"PATCH {table} failed {r.status_code}: {r.text[:800]}")
    return 1



def _month_start(date_str: str) -> str:
    return date_str[:7] + "-01"


def count_sent_notifications() -> Dict[str, int]:
    """DB上の送信履歴で日/月の送信数を確認。LINE公式の実使用数とはズレる可能性あり。"""
    day_rows = _rest_get(
        "v2_line_notifications",
        {
            "select": "id",
            "race_date": f"eq.{TARGET_DATE}",
            "status": "eq.sent",
            "limit": "10000",
        },
    )
    month_rows = _rest_get(
        "v2_line_notifications",
        {
            "select": "id,race_date",
            "race_date": f"gte.{_month_start(TARGET_DATE)}",
            "status": "eq.sent",
            "limit": "10000",
        },
    )
    month_rows = [r for r in month_rows if str(r.get("race_date", ""))[:7] == TARGET_DATE[:7]]
    return {"day": len(day_rows), "month": len(month_rows)}


def _usage_guard() -> Optional[str]:
    counts = count_sent_notifications()
    if counts["day"] >= DAILY_LINE_LIMIT:
        return f"daily_limit_reached {counts['day']}/{DAILY_LINE_LIMIT}"
    if counts["month"] >= MONTHLY_LINE_LIMIT:
        return f"monthly_limit_reached {counts['month']}/{MONTHLY_LINE_LIMIT}"
    return None



def _already_sent_keys_for_date() -> set[str]:
    """同一日・同一race_id・同一ticketの再通知を防ぐ。"""
    rows = _rest_get(
        "v2_line_notifications",
        {
            "select": "race_id,ticket,status,message_type",
            "race_date": f"eq.{TARGET_DATE}",
            "status": "eq.sent",
            "limit": "10000",
        },
    )
    keys: set[str] = set()
    for r in rows:
        rid = str(r.get("race_id") or "")
        ticket = str(r.get("ticket") or "")
        if rid and ticket:
            keys.add(f"{rid}|{ticket}")
    return keys


def fetch_buy_decisions() -> List[Dict[str, Any]]:
    rows = _rest_get(
        "v2_realtime_decisions",
        {
            "select": "*",
            "race_date": f"eq.{TARGET_DATE}",
            "decision_label": f"eq.{DECISION_LABEL}",
            "selector_mode": f"eq.{SELECTOR_MODE}",
            "recommendation": "eq.buy",
            "was_notified": "eq.false",
            "order": "final_score.desc,decision_at.asc",
            "limit": str(MAX_SEND * 3),
        },
    )
    sent_keys = _already_sent_keys_for_date()
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
        print(f"dedup_skipped={skipped_dup}", flush=True)
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
        f"{TARGET_DATE} {venue_id}場 {race_no}R",
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

        lines.append(f"{idx}. {venue_id}場{race_no}R {ticket} / {odds:.1f}倍")
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
    return "\\n".join(lines)[:4900]


def send_line_message(text: str) -> Dict[str, Any]:
    if DRY_RUN:
        return {"dry_run": True, "status_code": 200, "body": "DRY_RUN"}

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": LINE_TO,
        "messages": [{"type": "text", "text": text[:4900]}],
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload, ensure_ascii=False), timeout=HTTP_TIMEOUT)
    return {
        "dry_run": False,
        "status_code": r.status_code,
        "body": r.text[:1000],
    }


def insert_notification(decision: Dict[str, Any], message_text: str, status: str, resp: Dict[str, Any], error: str = "") -> Optional[str]:
    row = {
        "race_id": decision.get("race_id"),
        "race_date": decision.get("race_date"),
        "venue_id": decision.get("venue_id"),
        "race_no": decision.get("race_no"),
        "decision_id": decision.get("id"),
        "sent_at": _now_iso() if status == "sent" else None,
        "status": status,
        "line_to": LINE_TO if not DRY_RUN else "DRY_RUN",
        "message_type": "push",
        "message_text": message_text,
        "selector_version": decision.get("selector_version"),
        "selector_mode": decision.get("selector_mode"),
        "mode_name": decision.get("mode_name"),
        "ticket": decision.get("ticket"),
        "odds": decision.get("odds"),
        "line_response_status": resp.get("status_code"),
        "line_response_body": resp.get("body"),
        "error_message": error,
        "raw": {"response": resp, "dry_run": DRY_RUN},
    }
    inserted = _rest_insert("v2_line_notifications", row)
    if inserted and inserted.get("id"):
        return str(inserted["id"])
    return None


def mark_decision_notified(decision_id: str, notification_id: Optional[str]) -> None:
    if not decision_id:
        return
    patch = {
        "was_notified": True,
        "notification_id": notification_id,
        "updated_at": _now_iso(),
    }
    _rest_patch("v2_realtime_decisions", {"id": f"eq.{decision_id}"}, patch)


def main() -> None:
    _require_settings()
    print("✅ v23_line_notifier_batch_fix3.py VERSION 2026-06-25 batch-line-notifier-dedup", flush=True)
    print(
        f"TARGET_DATE={TARGET_DATE} DECISION_LABEL={DECISION_LABEL} SELECTOR_MODE={SELECTOR_MODE} "
        f"DRY_RUN={DRY_RUN} MAX_SEND={MAX_SEND} BATCH_NOTIFY={BATCH_NOTIFY} "
        f"DAILY_LINE_LIMIT={DAILY_LINE_LIMIT} MONTHLY_LINE_LIMIT={MONTHLY_LINE_LIMIT} TEST_MODE={TEST_MODE}",
        flush=True,
    )

    guard = _usage_guard()
    if guard:
        print(f"LINE送信上限ガード: {guard}", flush=True)
        print("=== v23 batch LINE通知終了 ===", flush=True)
        return

    decisions = fetch_buy_decisions()
    print(f"pending_buy_decisions={len(decisions)}", flush=True)

    if not decisions:
        print("LINE通知対象はありません。見送りです。", flush=True)
        print("=== v23 batch LINE通知終了 ===", flush=True)
        return

    decisions = decisions[:MAX_SEND]
    sent = 0
    failed = 0

    if BATCH_NOTIFY:
        msg = build_batch_message(decisions)
        print("\n--- batch message ---", flush=True)
        print(msg, flush=True)

        try:
            resp = send_line_message(msg)
            ok = 200 <= int(resp.get("status_code", 0)) < 300
            status = "sent" if ok else "failed"

            # 通知履歴は1件だけ作成し、最初のdecision_idに紐づける。
            first = decisions[0]
            nid = insert_notification(first, msg, status, resp)
            if ok:
                for d in decisions:
                    mark_decision_notified(str(d.get("id")), nid)
                sent = 1
            else:
                failed = 1
                print(f"LINE送信失敗: {resp}", flush=True)
        except Exception as e:
            failed = 1
            try:
                insert_notification(decisions[0], msg, "failed", {"status_code": 0, "body": ""}, error=repr(e))
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
                status = "sent" if ok else "failed"
                nid = insert_notification(d, msg, status, resp)
                if ok:
                    mark_decision_notified(str(d.get("id")), nid)
                    sent += 1
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

    print("\n=== v23 batch LINE通知 summary ===", flush=True)
    print(f"sent_api_calls={sent} failed={failed} dry_run={DRY_RUN} batch={BATCH_NOTIFY}", flush=True)
    print("=== v23 batch LINE通知終了 ===", flush=True)


if __name__ == "__main__":
    main()