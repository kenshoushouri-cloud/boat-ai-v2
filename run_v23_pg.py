# -*- coding: utf-8 -*-
"""
run_v23_pg.py

Railway Postgres版 v23 起動ラッパー。
fix3: v23本体のversion不一致では止めず、検出versionを表示して続行します。

Railway Start Command:
    python -u run_v23_pg.py
"""

import os
import re
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def _check_pg_file():
    p = Path("v23_line_notifier_batch_pg.py")
    if not p.exists():
        raise RuntimeError("v23_line_notifier_batch_pg.py が見つかりません。")

    s = p.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"v23_line_notifier_batch_pg\.py VERSION [^\"]+", s)
    detected = m.group(0) if m else "VERSION行が見つかりません"
    print(f"detected_v23_file={detected}", flush=True)

    if "railway-postgres-fix3" not in s:
        print("WARNING: v23_line_notifier_batch_pg.py がfix3ではない可能性があります。今回は続行します。", flush=True)

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

print("✅ run_v23_pg.py fix3", flush=True)
print(f"TARGET_DATE={os.environ.get('TARGET_DATE')}", flush=True)
print(f"DECISION_LABEL={os.environ.get('DECISION_LABEL')}", flush=True)
print(f"SELECTOR_MODE={os.environ.get('SELECTOR_MODE')}", flush=True)
print(f"DRY_RUN={os.environ.get('DRY_RUN')}", flush=True)
print("Railway Postgres版：v23 LINE通知を開始します。", flush=True)

_check_pg_file()
runpy.run_path("v23_line_notifier_batch_pg.py", run_name="__main__")