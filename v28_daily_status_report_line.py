# -*- coding: utf-8 -*-
"""
v28_daily_status_report_line.py
夜に1回だけ、競艇AIの日次稼働レポートをLINE配信します。
集計元: v2_learning_daily_reports
"""

import os, json
from datetime import datetime, timedelta, timezone
import requests

JST = timezone(timedelta(hours=9))
VERSION = "2026-06-30 daily-status-report-line-v1"

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or ""
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or ""
LINE_TO = os.getenv("LINE_TO") or os.getenv("LINE_USER_ID") or ""

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab")
TEST_MODE = os.getenv("TEST_MODE", "1") == "1"
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "60"))

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

def require_settings():
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY")
    if not DRY_RUN:
        if not LINE_CHANNEL_ACCESS_TOKEN:
            missing.append("LINE_CHANNEL_ACCESS_TOKEN")
        if not LINE_TO:
            missing.append("LINE_TO/LINE_USER_ID")
    if missing:
        raise RuntimeError("必要な環境変数が不足しています: " + ", ".join(missing))

def num(row, *names):
    for name in names:
        try:
            if isinstance(row, dict) and name in row and row.get(name) is not None:
                return int(float(row.get(name) or 0))
        except Exception:
            return 0
    return 0

def pct(n, d):
    return None if d <= 0 else round(n / d * 100, 1)

def fmt_pct(v):
    return "-" if v is None else f"{v:.1f}%"

def yen(v):
    try:
        return f"{int(v):,}円"
    except Exception:
        return "0円"

def parse_by_mode(v):
    if not v:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            obj = json.loads(v)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}

def get_daily_report():
    url = f"{SUPABASE_URL}/rest/v1/v2_learning_daily_reports"
    query = [
        ("select", "*"),
        ("report_date", f"eq.{TARGET_DATE}"),
        ("selector_mode", f"eq.{SELECTOR_MODE}"),
        ("limit", "1"),
    ]
    r = requests.get(url, headers=HEADERS, params=query, timeout=HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"GET v2_learning_daily_reports failed {r.status_code}: {r.text[:800]}")
    rows = r.json() or []
    return rows[0] if rows else None

def mode_lines(by_mode):
    if not by_mode:
        return "【ランク別】\nデータなし"

    order = ["Aランク", "Bランク"]
    names = [n for n in order if n in by_mode] + [n for n in sorted(by_mode.keys()) if n not in order]
    lines = ["【ランク別】"]
    for name in names:
        m = by_mode.get(name) or {}
        decisions = num(m, "decisions", "decision_count")
        buy = num(m, "buy", "buy_count")
        hit = num(m, "hit", "hit_count")
        stake = num(m, "stake_yen", "stake")
        ret = num(m, "return_yen", "return")
        profit = num(m, "profit_yen", "profit")
        lines.append(
            f"{name}: 判定{decisions} / BUY{buy} / 的中{hit} / "
            f"的中率{fmt_pct(pct(hit, buy))} / 回収率{fmt_pct(pct(ret, stake))} / 損益{yen(profit)}"
        )
    return "\n".join(lines)

def no_report_message():
    header = "【競艇AI 日次稼働レポート】"
    if TEST_MODE:
        header += "\n※テスト運用中・購入しない集計"
    return "\n".join([
        header,
        TARGET_DATE,
        "",
        "⚠️ 夜間学習レポートがまだ保存されていません。",
        "boat-ai-nightly-learning のログを確認してください。",
        "",
        "確認ポイント:",
        "保存結果件数",
        "v2_learning_daily_reports saved",
        "=== v26 夜間結果取得・学習集計終了 ===",
    ])

def build_message(row):
    total_races = num(row, "total_races")
    decisions = num(row, "decisions", "decision_count")
    buy = num(row, "buy", "buy_count")
    hit = num(row, "hit", "hit_count")
    stake = num(row, "stake_yen", "stake")
    ret = num(row, "return_yen", "return")
    profit = num(row, "profit_yen", "profit")
    by_mode = parse_by_mode(row.get("by_mode"))

    header = "【競艇AI 日次稼働レポート】"
    if TEST_MODE:
        header += "\n※テスト運用中・購入しない集計"

    buy_status = "本日は最終BUYなし" if buy == 0 else f"本日は最終BUY {buy}件"

    return "\n".join([
        header,
        str(row.get("report_date") or TARGET_DATE),
        "",
        buy_status,
        "データ取得・結果取得・学習集計は完了",
        "",
        "【日次成績】",
        f"対象R: {total_races}",
        f"直前判定: {decisions}件",
        f"BUY: {buy}件",
        f"的中: {hit}件",
        f"的中率: {fmt_pct(pct(hit, buy))}",
        f"投資: {yen(stake)}",
        f"回収: {yen(ret)}",
        f"損益: {yen(profit)}",
        f"回収率: {fmt_pct(pct(ret, stake))}",
        "",
        mode_lines(by_mode),
    ])

def send_line(message):
    if DRY_RUN:
        print("--- daily status report message ---")
        print(message)
        return 0
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"to": LINE_TO, "messages": [{"type": "text", "text": message}]}
    r = requests.post(url, headers=headers, data=json.dumps(payload, ensure_ascii=False), timeout=HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"LINE push failed {r.status_code}: {r.text[:800]}")
    return r.status_code

def main():
    print(f"✅ v28_daily_status_report_line.py VERSION {VERSION}", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} SELECTOR_MODE={SELECTOR_MODE} DRY_RUN={DRY_RUN} TEST_MODE={TEST_MODE}", flush=True)
    require_settings()
    row = get_daily_report()
    if row is None:
        print("daily report row not found", flush=True)
        msg = no_report_message()
    else:
        print(
            f"daily report found: total_races={num(row,'total_races')} decisions={num(row,'decisions','decision_count')} buy={num(row,'buy','buy_count')} hit={num(row,'hit','hit_count')}",
            flush=True,
        )
        msg = build_message(row)
    status = send_line(msg)
    print(f"LINE daily status sent dry_run={DRY_RUN} response_status={status}", flush=True)
    print("=== v28 日次稼働レポートLINE配信終了 ===", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("FATAL ERROR", flush=True)
        traceback.print_exc()
        raise