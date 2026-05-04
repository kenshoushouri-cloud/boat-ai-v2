# -*- coding: utf-8 -*-
"""
Railway用バックテスト起動ファイル

Start Command を python backtest.py のまま使う場合、
このファイルが scripts/run_backtest_test.py を起動します。

全期間を実行したい場合は Railway の環境変数に
BACKTEST_SCRIPT=scripts/run_backtest_full.py
を設定してください。
"""

import os
import sys
import runpy


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

script = os.environ.get("BACKTEST_SCRIPT", "scripts/run_backtest_test.py")
script_path = os.path.join(PROJECT_ROOT, script)

print("=== BACKTEST LAUNCHER ===", flush=True)
print(f"PROJECT_ROOT: {PROJECT_ROOT}", flush=True)
print(f"BACKTEST_SCRIPT: {script}", flush=True)
print(f"script_path: {script_path}", flush=True)

if not os.path.exists(script_path):
    raise FileNotFoundError(f"Backtest script not found: {script_path}")

runpy.run_path(script_path, run_name="__main__")