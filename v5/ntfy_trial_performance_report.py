# -*- coding: utf-8 -*-
"""Read-only V5 trial performance report for ConoHa local NTFY me.

No synthetic ROI, V4 decisions, database writes, betting, or LINE.
The input is a separately verified, pre-deadline frozen V5 JSONL ledger.
Without a valid ledger, a preview/send fails closed. Not scheduled by default.

Preview:
  python -m v5.ntfy_trial_performance_report --ledger /path/to/v5-ledger.jsonl --period daily --date 2026-10-20
Real send (ONLY after ledger/secret/idempotency are independently verified):
  V5_NTFY_SEND=YES ... python -m v5.ntfy_trial_performance_report --ledger ... --period daily --date ... --send
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from v5.ntfy_trial_transport import publish
from v5.telegram_trial_performance import aggregate, load_ledger, render_report


def prepare_report(
    ledger: Path, *, period: str, target: str, mode: str = "shadow",
) -> tuple[str, bool]:
    """Return (report body, has_verified_results). No network or DB writes."""
    records = load_ledger(ledger)
    summary = aggregate(records, period=period, target=target, mode=mode)
    return render_report(summary, period=period, target=target, mode=mode), bool(summary["verified"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--period", choices=("daily", "monthly"), required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD or YYYY-MM")
    parser.add_argument("--mode", choices=("shadow", "actual"), default="shadow")
    parser.add_argument("--send", action="store_true", help="opt-in real send; additional env authorization required")
    args = parser.parse_args(argv)
    try:
        report, verified = prepare_report(
            args.ledger, period=args.period, target=args.date, mode=args.mode,
        )
        # Do not send empty/pending-only reports. Missing data is not a 0% ROI.
        if args.send and not verified:
            raise ValueError("verified V5 trial records unavailable; no notification sent")
        label = "V5 Trial Daily" if args.period == "daily" else "V5 Trial Monthly"
        status = publish(report, title=label, allow_send=args.send)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        # No user secrets or exception payloads from remote calls are shown.
        msg = str(exc)
        print(f"V5_NTFY_REPORT_HOLD={msg}", file=sys.stderr)
        return 2
    print(f"V5_NTFY_REPORT_STATUS={status} period={args.period} mode={args.mode}")
    if status == "DRY_RUN":
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
