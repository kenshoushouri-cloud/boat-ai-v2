# -*- coding: utf-8 -*-
"""
run_v23_pg.py

Railway Postgres版 v23 起動ラッパー。
初回テストはDRY_RUN=1で、LINE送信せず本文とDB保存だけ確認します。

Railway Start Command:
    python -u run_v23_pg.py
"""

import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def _assert_pg_file():
    p = Path("v23_line_notifier_batch_pg.py")
    if not p.exists():
        raise RuntimeError("v23_line_notifier_batch_pg.py が見つかりません。")
    s = p.read_text(encoding="utf-8", errors="ignore")
    if "v23_line_notifier_batch_pg.py VERSION 2026-07-05 railway-postgres-fix2" not in s:
        raise RuntimeError("v23_line_notifier_batch_pg.py が古い、またはPG版ではありません。")


os.environ.setdefault("TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))
os.environ.setdefault("DECISION_LABEL", "final_ab")
os.environ.setdefault("SNAPSHOT_LABEL", "final_ab")
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("DRY_RUN", "1")
os.environ.setdefault("MAX_SEND", "10")
os.environ.setdefault("BATCH_NOTIFY", "1")
os.environ.setdefault("MAX_ITEMS_PER_MESSAGE", "6")
os.environ.setdefault("DAILY_LINE_LIMIT", "3")
os.environ.setdefault("MONTHLY_LINE_LIMIT", "180")
os.environ.setdefault("TEST_MODE", "1")

print("✅ run_v23_pg.py", flush=True)
print(f"TARGET_DATE={os.environ.get('TARGET_DATE')}", flush=True)
print(f"DECISION_LABEL={os.environ.get('DECISION_LABEL')}", flush=True)
print(f"SELECTOR_MODE={os.environ.get('SELECTOR_MODE')}", flush=True)
print(f"DRY_RUN={os.environ.get('DRY_RUN')}", flush=True)
print("Railway Postgres版：v23 LINE通知を開始します。", flush=True)

_assert_pg_file()
runpy.run_path("v23_line_notifier_batch_pg.py", run_name="__main__")