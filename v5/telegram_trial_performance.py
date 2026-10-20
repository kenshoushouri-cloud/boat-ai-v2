# -*- coding: utf-8 -*-
"""V5 trial performance summaries: strict, separated, read-only and no guessed ROI.

Input: independently produced, frozen V5 JSONL ledger; this module never
derives predictions from post-race data nor uses legacy Railway/V4 decisions.
Until ledger and official settlement verification exist, prints 未連携 rather
than inventing a return, hit rate or profit.

Each record (one per race per mode) requires:
  race_id, mode='shadow'|'actual', decision_at, deadline_at,
  prediction_receipt_sha256, stake_yen, status='pending'|'verified',
For verified:
  hit (boolean), return_yen, official_result_receipt_sha256,
  official_payout_receipt_sha256
For actual:
  purchase_receipt_sha256 (an independently verified purchase proof).

The upstream capture pipeline must provide real receipts before inserting
records. This code only validates/shows those records, does not verify
cryptographic preimage origin. Refunds are included in return_yen only if
officially verified. Never silently count an unverified race as a loss.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

JST = timezone(timedelta(hours=9))
HASH = re.compile(r"[0-9a-f]{64}\Z")
RID = re.compile(r"(20\d{6})_(0[1-9]|1\d|2[0-4])_(0[1-9]|1[0-2])\Z")
YEAR_MONTH = re.compile(r"20\d{2}-(?:0[1-9]|1[0-2])\Z")
MODE = ("shadow", "actual")


@dataclass(frozen=True)
class TrialRecord:
    race_id: str
    mode: str
    decision_at: datetime
    deadline_at: datetime
    stake_yen: int
    status: str
    hit: bool | None
    return_yen: int | None


def _utc_dt(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp missing")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("naive timestamp")
    return dt.astimezone(JST)


def _digest(row: dict, key: str) -> None:
    val = row.get(key)
    if not isinstance(val, str) or HASH.fullmatch(val) is None:
        raise ValueError(f"missing or invalid {key}")


def parse_record(raw: Any) -> TrialRecord:
    if not isinstance(raw, dict):
        raise ValueError("row must be object")
    race_id = raw.get("race_id")
    if not isinstance(race_id, str) or RID.fullmatch(race_id) is None:
        raise ValueError("invalid race_id")
    mode = raw.get("mode")
    if mode not in MODE:
        raise ValueError("mode must be shadow or actual")
    decision = _utc_dt(raw.get("decision_at"))
    deadline = _utc_dt(raw.get("deadline_at"))
    if decision >= deadline or decision.date().strftime("%Y%m%d") != race_id[:8]:
        raise ValueError("prediction not frozen before deadline")
    _digest(raw, "prediction_receipt_sha256")
    stake = raw.get("stake_yen")
    if type(stake) is not int or not 0 < stake <= 100000:
        raise ValueError("invalid stake")
    if mode == "actual":
        _digest(raw, "purchase_receipt_sha256")
    status = raw.get("status")
    if status == "pending":
        if raw.get("hit") is not None or raw.get("return_yen") is not None:
            raise ValueError("pending has result or return")
        hit = returned = None
    elif status == "verified":
        _digest(raw, "official_result_receipt_sha256")
        _digest(raw, "official_payout_receipt_sha256")
        hit = raw.get("hit")
        returned = raw.get("return_yen")
        if type(hit) is not bool or type(returned) is not int or returned < 0:
            raise ValueError("unverified settlement")
        # No upper bound: genuine high odds can produce large returns.
    else:
        raise ValueError("status not verified or pending")
    return TrialRecord(race_id, mode, decision, deadline, stake, status, hit, returned)


def load_ledger(path: Path) -> list[TrialRecord]:
    if not path.is_file():
        raise FileNotFoundError("trial ledger not configured")
    rows = []
    seen: set[tuple[str, str]] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = parse_record(json.loads(line))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"invalid trial ledger line {number}: {exc}") from None
        key = (row.race_id, row.mode)
        if key in seen:
            raise ValueError(f"duplicate trial ledger at line {number}")
        seen.add(key)
        rows.append(row)
    return rows


def period_match(row: TrialRecord, period: str, target: str) -> bool:
    race_day = row.race_id[:8]
    if period == "daily":
        return race_day == date.fromisoformat(target).strftime("%Y%m%d")
    if not YEAR_MONTH.fullmatch(target):
        raise ValueError("month must be YYYY-MM")
    return race_day.startswith(target.replace("-", ""))


def aggregate(rows: list[TrialRecord], *, period: str, target: str, mode: str) -> dict[str, int | None]:
    if period not in ("daily", "monthly") or mode not in MODE:
        raise ValueError("invalid period or mode")
    # Validate target even when ledger is empty.
    if period == "daily":
        date.fromisoformat(target)
    elif not YEAR_MONTH.fullmatch(target):
        raise ValueError("month must be YYYY-MM")
    matched = [r for r in rows if r.mode == mode and period_match(r, period, target)]
    completed = [r for r in matched if r.status == "verified"]
    pending = len(matched) - len(completed)
    return {
        "total": len(matched),
        "verified": len(completed),
        "pending": pending,
        "hit": sum(1 for r in completed if r.hit is True),
        "stake": sum(r.stake_yen for r in completed),
        "returned": sum(r.return_yen or 0 for r in completed),
    }


def _pct(n: int, total: int) -> str:
    return "-" if total == 0 else f"{100*n/total:.1f}%"


def render_report(summary: dict[str, int | None], *, period: str, target: str, mode: str) -> str:
    label = "V5試験予想（仮想収支）" if mode == "shadow" else "実購入収支（購入証跡あり）"
    scope = "日次" if period == "daily" else "月次"
    result = [f"【{label}・{scope}】{target}", "参考・検証用／購入推奨ではありません"]
    total = int(summary["total"] or 0)
    settled = int(summary["verified"] or 0)
    pending = int(summary["pending"] or 0)
    result.extend([f"記録レース: {total}件", f"公式照合済み: {settled}件", f"未確定: {pending}件"])
    if not total:
        result.append("的中率・回収率・収支: 算出不可（V5専用台帳未連携）")
        return "\n".join(result)
    if not settled:
        result.append("的中率・回収率・収支: 算出不可（結果未照合）")
        return "\n".join(result)
    hits, stake, returned = int(summary["hit"] or 0), int(summary["stake"] or 0), int(summary["returned"] or 0)
    result.extend([
        f"的中: {hits}/{settled}レース",
        f"的中率: {_pct(hits, settled)}",
        f"投資: {stake:,}円", f"払戻（返還含む）: {returned:,}円",
        f"回収率: {_pct(returned, stake)}",
        f"収支: {returned-stake:+,}円",
    ])
    if pending:
        result.append("※未確定レースは計算から除外。数値は暫定値です")
    if mode == "shadow":
        result.append("※実際の購入・利益を示す数字ではありません")
    return "\n".join(result)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--period", choices=("daily", "monthly"), required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD for daily or YYYY-MM for monthly")
    ap.add_argument("--mode", choices=MODE, default="shadow")
    args = ap.parse_args(argv)
    try:
        rows = load_ledger(args.ledger)
        summary = aggregate(rows, period=args.period, target=args.date, mode=args.mode)
    except (FileNotFoundError, ValueError) as exc:
        # Never send fabricated 0% performance after missing/corrupt data.
        print(f"V5_REPORT_HOLD={exc}")
        return 2
    print(render_report(summary, period=args.period, target=args.date, mode=args.mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
