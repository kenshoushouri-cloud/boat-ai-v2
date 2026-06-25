# -*- coding: utf-8 -*-
"""
v26_nightly_results_learning.py

夜の全レース結果取得 + A/Bランク別の日次学習用レポート保存。

Railway Start Command:
    python run_nightly_results_learning.py

処理:
1) repair_month_all_v5_fixed2.py で当日結果を補修
2) v2_realtime_decisions と v2_results を突合
3) v2_learning_daily_reports に selector_mode=ab として保存

購入処理はありません。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
from collections import defaultdict
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

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower()
DECISION_LABEL_PREFIX = os.getenv("DECISION_LABEL_PREFIX", "final").strip()
RUN_REPAIR_RESULTS = os.getenv("RUN_REPAIR_RESULTS", "1").strip() not in ("0", "false", "False", "no", "NO")
UNIT_YEN = int(os.getenv("UNIT_YEN", "100"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "60"))

def _require_settings() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY が必要です。")

def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(str(v).replace(",", "")))
    except Exception:
        return default

def _norm_ticket(v: Any) -> str:
    if not v:
        return ""
    s = str(v).strip().replace(" ", "").replace("－", "-").replace("―", "-").replace("ー", "-")
    if "-" in s:
        parts = [p for p in s.split("-") if p]
    else:
        parts = list(s) if len(s) == 3 and s.isdigit() else []
    if len(parts) != 3:
        return ""
    try:
        nums = [str(int(p)) for p in parts]
    except Exception:
        return ""
    if any(n not in {"1","2","3","4","5","6"} for n in nums):
        return ""
    return "-".join(nums)

def _actual_ticket(r: Dict[str, Any]) -> str:
    t = _norm_ticket(r.get("trifecta_ticket"))
    if t:
        return t
    a,b,c = r.get("first_lane"), r.get("second_lane"), r.get("third_lane")
    if a is not None and b is not None and c is not None:
        return f"{_safe_int(a)}-{_safe_int(b)}-{_safe_int(c)}"
    return ""

def _rest_get(table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
    query = urllib.parse.urlencode(params, safe=",.*()")
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    r = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {table} failed {r.status_code}: {r.text[:1000]}")
    return r.json()

def _rest_upsert(table: str, row: Dict[str, Any], on_conflict: str) -> Optional[Dict[str, Any]]:
    query = urllib.parse.urlencode({"on_conflict": on_conflict})
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    r = requests.post(url, headers=HEADERS, data=json.dumps([row], ensure_ascii=False), timeout=HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"UPSERT {table} failed {r.status_code}: {r.text[:1000]}")
    try:
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
    except Exception:
        return None
    return None

def _run_result_repair() -> None:
    if not RUN_REPAIR_RESULTS:
        print("RUN_REPAIR_RESULTS=0 のため結果補修はスキップ", flush=True)
        return
    env = os.environ.copy()
    env.update({
        "REPAIR_START_DATE": TARGET_DATE,
        "REPAIR_END_DATE": TARGET_DATE,
        "REPAIR_DO_RACES": "0",
        "REPAIR_DO_RESULTS": "1",
        "REPAIR_DO_ODDS": "0",
        "REPAIR_WORKERS": os.getenv("REPAIR_WORKERS", "4"),
        "REPAIR_ODDS_WORKERS": os.getenv("REPAIR_ODDS_WORKERS", "1"),
    })
    print("=== 結果補修開始 ===", flush=True)
    p = subprocess.run([sys.executable, "repair_month_all_v5_fixed2.py"], env=env)
    if p.returncode != 0:
        raise SystemExit(p.returncode)
    print("=== 結果補修終了 ===", flush=True)

def _fetch_total_races() -> int:
    rows = _rest_get("v2_races", {"select": "race_id", "race_date": f"eq.{TARGET_DATE}", "limit": "10000"})
    return len(rows)

def _fetch_decisions() -> List[Dict[str, Any]]:
    # final_ab優先。互換のため final も拾えるよう prefix検索。
    rows = _rest_get(
        "v2_realtime_decisions",
        {
            "select": "*",
            "race_date": f"eq.{TARGET_DATE}",
            "selector_mode": f"eq.{SELECTOR_MODE}",
            "decision_label": f"like.{DECISION_LABEL_PREFIX}*",
            "order": "decision_at.asc",
            "limit": "10000",
        },
    )
    return rows

def _fetch_results_by_race_ids(race_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not race_ids:
        return out
    # race_id in のURL長対策で分割
    for i in range(0, len(race_ids), 80):
        chunk = race_ids[i:i+80]
        in_expr = "(" + ",".join(chunk) + ")"
        rows = _rest_get(
            "v2_results",
            {
                "select": "race_id,result_status,trifecta_ticket,trifecta_payout_yen,first_lane,second_lane,third_lane",
                "race_id": f"in.{in_expr}",
                "limit": "1000",
            },
        )
        for r in rows:
            out[str(r.get("race_id"))] = r
    return out

def _fetch_notifications_count() -> int:
    rows = _rest_get(
        "v2_line_notifications",
        {"select": "id", "race_date": f"eq.{TARGET_DATE}", "status": "eq.sent", "limit": "10000"},
    )
    return len(rows)

def _bucket_mode(label: str, name: str) -> str:
    s = f"{label} {name}"
    if "Aランク" in s or "mode_balanced" in s or "mode_intersection" in s or "mode_general" in s or "mode_strict" in s:
        return "Aランク"
    if "Bランク" in s or "low_exR10_12_base" in s:
        return "Bランク"
    return "その他"

def _calc_report(decisions: List[Dict[str, Any]], results: Dict[str, Dict[str, Any]], total_races: int) -> Dict[str, Any]:
    buy_rows = [d for d in decisions if str(d.get("recommendation")) == "buy"]
    by_mode = defaultdict(lambda: {"decisions": 0, "buy": 0, "hit": 0, "stake_yen": 0, "return_yen": 0, "profit_yen": 0})
    by_venue = defaultdict(lambda: {"buy": 0, "hit": 0, "stake_yen": 0, "return_yen": 0, "profit_yen": 0})
    by_category = defaultdict(lambda: {"buy": 0, "hit": 0, "stake_yen": 0, "return_yen": 0, "profit_yen": 0})

    hit_count = 0
    stake_yen = 0
    return_yen = 0
    top_payout = 0
    top_race_id = ""

    for d in decisions:
        bucket = _bucket_mode(str(d.get("mode_label") or ""), str(d.get("mode_name") or ""))
        by_mode[bucket]["decisions"] += 1

    for d in buy_rows:
        rid = str(d.get("race_id"))
        result = results.get(rid, {})
        actual = _actual_ticket(result)
        ticket = _norm_ticket(d.get("ticket"))
        payout = _safe_int(result.get("trifecta_payout_yen"), 0)
        hit = bool(actual and ticket and actual == ticket)
        ret = payout if hit else 0
        stake = _safe_int(d.get("stake_yen"), UNIT_YEN) or UNIT_YEN

        stake_yen += stake
        return_yen += ret
        if hit:
            hit_count += 1
            if ret > top_payout:
                top_payout = ret
                top_race_id = rid

        bucket = _bucket_mode(str(d.get("mode_label") or ""), str(d.get("mode_name") or ""))
        venue = str(d.get("venue_id") or "").zfill(2)
        raw = d.get("raw") or {}
        cand = raw.get("candidate") if isinstance(raw, dict) else {}
        cat = str(cand.get("event_category") or "unknown") if isinstance(cand, dict) else "unknown"

        for target, key in [(by_mode, bucket), (by_venue, venue), (by_category, cat)]:
            target[key]["buy"] += 1
            target[key]["hit"] += 1 if hit else 0
            target[key]["stake_yen"] += stake
            target[key]["return_yen"] += ret
            target[key]["profit_yen"] += ret - stake

    def finalize(dct):
        out = {}
        for k, v in dct.items():
            stake = v.get("stake_yen", 0)
            v["roi_pct"] = round(v.get("return_yen", 0) / stake * 100, 2) if stake else None
            out[k] = dict(v)
        return out

    profit = return_yen - stake_yen
    roi = round(return_yen / stake_yen * 100, 4) if stake_yen else None
    return {
        "report_date": TARGET_DATE,
        "selector_version": "v26_nightly_results_learning",
        "selector_mode": SELECTOR_MODE,
        "total_races": total_races,
        "candidate_races": len(set(str(d.get("race_id")) for d in decisions)),
        "decision_count": len(decisions),
        "buy_count": len(buy_rows),
        "notified_count": _fetch_notifications_count(),
        "hit_count": hit_count,
        "stake_yen": stake_yen,
        "return_yen": return_yen,
        "profit_yen": profit,
        "roi_pct": roi,
        "max_losing_streak": None,
        "top_payout_yen": top_payout,
        "top_payout_race_id": top_race_id or None,
        "by_mode": finalize(by_mode),
        "by_venue": finalize(by_venue),
        "by_category": finalize(by_category),
        "by_realtime_feature": {},
        "notes": "A/Bランクの日次テスト集計。購入処理なし。",
        "raw": {"decision_labels_prefix": DECISION_LABEL_PREFIX, "test_mode": True},
    }

def main() -> None:
    _require_settings()
    print("✅ v26_nightly_results_learning.py VERSION 2026-06-26 nightly-results-learning", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} SELECTOR_MODE={SELECTOR_MODE} RUN_REPAIR_RESULTS={RUN_REPAIR_RESULTS}", flush=True)
    _run_result_repair()

    total_races = _fetch_total_races()
    decisions = _fetch_decisions()
    race_ids = sorted({str(d.get("race_id")) for d in decisions if d.get("race_id")})
    results = _fetch_results_by_race_ids(race_ids)
    report = _calc_report(decisions, results, total_races)

    print("=== daily learning report ===", flush=True)
    print(f"total_races={report['total_races']} decisions={report['decision_count']} buy={report['buy_count']} hit={report['hit_count']} stake={report['stake_yen']} return={report['return_yen']} profit={report['profit_yen']} roi={report['roi_pct']}", flush=True)
    print(f"by_mode={json.dumps(report['by_mode'], ensure_ascii=False)}", flush=True)

    _rest_upsert("v2_learning_daily_reports", report, "report_date,selector_version,selector_mode")
    print("v2_learning_daily_reports saved", flush=True)
    print("=== v26 夜間結果取得・学習集計終了 ===", flush=True)

if __name__ == "__main__":
    main()