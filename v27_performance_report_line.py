# -*- coding: utf-8 -*-
"""
v27_performance_report_line.py
競艇AIの月次成績 + 累積成績をLINE配信するスクリプト。
集計元: v2_learning_daily_reports
"""

import os
import json
import calendar
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

JST = timezone(timedelta(hours=9))
VERSION = "2026-06-28 performance-report-line-v1"

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or ""
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or ""
LINE_TO = os.getenv("LINE_TO") or os.getenv("LINE_USER_ID") or ""

PERFORMANCE_START_DATE = os.getenv("PERFORMANCE_START_DATE", "2026-06-28")
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab")
REPORT_MONTH = os.getenv("REPORT_MONTH", "previous")  # previous/current/YYYY-MM
TEST_MODE = os.getenv("TEST_MODE", "1") == "1"
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "60"))

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def _require_settings() -> None:
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


def _ym_range(mode: str, now_jst: Optional[datetime] = None) -> Tuple[date, date, str]:
    now_jst = now_jst or datetime.now(JST)
    today = now_jst.date()
    if mode == "current":
        y, m = today.year, today.month
    elif mode == "previous":
        first_this = date(today.year, today.month, 1)
        prev_last = first_this - timedelta(days=1)
        y, m = prev_last.year, prev_last.month
    else:
        try:
            y, m = map(int, mode.split("-", 1))
        except Exception:
            raise RuntimeError("REPORT_MONTH は previous/current/YYYY-MM のいずれかで指定してください。")
    first = date(y, m, 1)
    last = date(y, m, calendar.monthrange(y, m)[1])
    return first, last, f"{y:04d}-{m:02d}"


def _rest_get_reports(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    url = f"{SUPABASE_URL}/rest/v1/v2_learning_daily_reports"
    query = [
        ("select", "*"),
        ("report_date", f"gte.{start_date.isoformat()}"),
        ("report_date", f"lte.{end_date.isoformat()}"),
        ("selector_mode", f"eq.{SELECTOR_MODE}"),
        ("order", "report_date.asc"),
        ("limit", "1000"),
    ]
    r = requests.get(url, headers=HEADERS, params=query, timeout=HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"GET v2_learning_daily_reports failed {r.status_code}: {r.text[:800]}")
    return r.json() or []


def _num(row: Dict[str, Any], *names: str) -> float:
    for name in names:
        if name in row and row.get(name) is not None:
            try:
                return float(row.get(name) or 0)
            except Exception:
                return 0.0
    return 0.0


def _parse_by_mode(value: Any) -> Dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _empty_summary() -> Dict[str, Any]:
    return {
        "days": 0,
        "total_races": 0,
        "decisions": 0,
        "buy": 0,
        "hit": 0,
        "stake_yen": 0,
        "return_yen": 0,
        "profit_yen": 0,
        "by_mode": {},
    }


def _add_mode(dst: Dict[str, Any], mode_name: str, src: Dict[str, Any]) -> None:
    m = dst.setdefault(mode_name, {
        "decisions": 0,
        "buy": 0,
        "hit": 0,
        "stake_yen": 0,
        "return_yen": 0,
        "profit_yen": 0,
    })
    m["decisions"] += int(_num(src, "decisions", "decision_count"))
    m["buy"] += int(_num(src, "buy", "buy_count"))
    m["hit"] += int(_num(src, "hit", "hit_count"))
    m["stake_yen"] += int(_num(src, "stake_yen", "stake"))
    m["return_yen"] += int(_num(src, "return_yen", "return"))
    m["profit_yen"] += int(_num(src, "profit_yen", "profit"))


def _summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = _empty_summary()
    s["days"] = len({str(r.get("report_date")) for r in rows if r.get("report_date")})
    for r in rows:
        s["total_races"] += int(_num(r, "total_races"))
        s["decisions"] += int(_num(r, "decisions", "decision_count"))
        s["buy"] += int(_num(r, "buy", "buy_count"))
        s["hit"] += int(_num(r, "hit", "hit_count"))
        s["stake_yen"] += int(_num(r, "stake_yen", "stake"))
        s["return_yen"] += int(_num(r, "return_yen", "return"))
        s["profit_yen"] += int(_num(r, "profit_yen", "profit"))
        by_mode = _parse_by_mode(r.get("by_mode"))
        for mode_name, v in by_mode.items():
            if isinstance(v, dict):
                _add_mode(s["by_mode"], str(mode_name), v)
    return s


def _pct(numer: float, denom: float) -> Optional[float]:
    if denom <= 0:
        return None
    return round(numer / denom * 100, 1)


def _yen(v: Any) -> str:
    try:
        return f"{int(v):,}円"
    except Exception:
        return "0円"


def _fmt_pct(v: Optional[float]) -> str:
    return "-" if v is None else f"{v:.1f}%"


def _summary_block(title: str, s: Dict[str, Any]) -> str:
    hit_rate = _pct(s["hit"], s["buy"])
    roi = _pct(s["return_yen"], s["stake_yen"])
    return "\n".join([
        f"【{title}】",
        f"稼働日: {s['days']}日 / 対象R: {s['total_races']}",
        f"判定: {s['decisions']}件 / BUY: {s['buy']}件",
        f"的中: {s['hit']}件 / 的中率: {_fmt_pct(hit_rate)}",
        f"投資: {_yen(s['stake_yen'])}",
        f"回収: {_yen(s['return_yen'])}",
        f"損益: {_yen(s['profit_yen'])}",
        f"回収率: {_fmt_pct(roi)}",
    ])


def _mode_lines(title: str, by_mode: Dict[str, Any]) -> str:
    if not by_mode:
        return f"【{title}】\nデータなし"
    order = ["Aランク", "Bランク"]
    names = [n for n in order if n in by_mode] + [n for n in sorted(by_mode.keys()) if n not in order]
    lines = [f"【{title}】"]
    for name in names:
        m = by_mode[name]
        hit_rate = _pct(m.get("hit", 0), m.get("buy", 0))
        roi = _pct(m.get("return_yen", 0), m.get("stake_yen", 0))
        lines.append(
            f"{name}: 判定{m.get('decisions', 0)} / BUY{m.get('buy', 0)} / "
            f"的中{m.get('hit', 0)} / 的中率{_fmt_pct(hit_rate)} / "
            f"回収率{_fmt_pct(roi)} / 損益{_yen(m.get('profit_yen', 0))}"
        )
    return "\n".join(lines)


def _build_message(month_label: str, month_summary: Dict[str, Any], cumulative_summary: Dict[str, Any]) -> str:
    header = "【競艇AI 月次成績レポート】"
    if TEST_MODE:
        header += "\n※テスト運用中・購入しない集計"
    parts = [
        header,
        f"対象月: {month_label}",
        f"累積開始: {PERFORMANCE_START_DATE}",
        "",
        _summary_block(f"{month_label} 月間成績", month_summary),
        "",
        _summary_block("累積成績", cumulative_summary),
        "",
        _mode_lines(f"{month_label} ランク別", month_summary["by_mode"]),
        "",
        _mode_lines("累積ランク別", cumulative_summary["by_mode"]),
    ]
    msg = "\n".join(parts)
    if len(msg) > 4800:
        msg = msg[:4700] + "\n\n※文字数上限のため一部省略"
    return msg


def _send_line(message: str) -> int:
    if DRY_RUN:
        print("--- performance report message ---")
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


def main() -> None:
    print(f"✅ v27_performance_report_line.py VERSION {VERSION}", flush=True)
    _require_settings()
    month_start, month_end, month_label = _ym_range(REPORT_MONTH)
    cumulative_start = datetime.strptime(PERFORMANCE_START_DATE, "%Y-%m-%d").date()
    cumulative_end = month_end

    month_rows = _rest_get_reports(month_start, month_end)
    cumulative_rows = _rest_get_reports(cumulative_start, cumulative_end)

    month_summary = _summarize(month_rows)
    cumulative_summary = _summarize(cumulative_rows)

    print(
        f"REPORT_MONTH={REPORT_MONTH} month={month_label} "
        f"month_rows={len(month_rows)} cumulative_rows={len(cumulative_rows)}",
        flush=True,
    )
    print(
        "month: buy={buy} hit={hit} stake={stake} return={ret} profit={profit}".format(
            buy=month_summary["buy"],
            hit=month_summary["hit"],
            stake=month_summary["stake_yen"],
            ret=month_summary["return_yen"],
            profit=month_summary["profit_yen"],
        ),
        flush=True,
    )
    print(
        "cumulative: buy={buy} hit={hit} stake={stake} return={ret} profit={profit}".format(
            buy=cumulative_summary["buy"],
            hit=cumulative_summary["hit"],
            stake=cumulative_summary["stake_yen"],
            ret=cumulative_summary["return_yen"],
            profit=cumulative_summary["profit_yen"],
        ),
        flush=True,
    )

    message = _build_message(month_label, month_summary, cumulative_summary)
    status = _send_line(message)
    print(f"LINE report sent dry_run={DRY_RUN} response_status={status}", flush=True)
    print("=== v27 月次・累積成績LINE配信終了 ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("FATAL ERROR", flush=True)
        traceback.print_exc()
        raise