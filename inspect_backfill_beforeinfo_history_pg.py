# -*- coding: utf-8 -*-
"""
inspect_backfill_beforeinfo_history_pg.py

backfill_beforeinfo_history_pg.py の補修実行に必要な部分だけを表示します。
DB接続・DB更新・外部通信は行いません。

Railway Start Command:
    python -u inspect_backfill_beforeinfo_history_pg.py

Variables:
    TARGET_FILE=backfill_beforeinfo_history_pg.py
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

TARGET = Path(os.getenv("TARGET_FILE", "backfill_beforeinfo_history_pg.py")).resolve()

FUNCTIONS = {
    "main",
    "_process",
    "_rows",
    "parse_beforeinfo_extra",
    "cells_of",
}

IMPORTANT_NAMES = {
    "START_DATE",
    "END_DATE",
    "TARGET_DATE",
    "DRY_RUN",
    "WORKERS",
    "SNAPSHOT_LABEL",
    "SOURCE",
}


def print_block(lines, start, end, title):
    print(f"\n=== {title} lines {start}-{end} ===", flush=True)
    for n in range(start, end + 1):
        print(f"{n:5d}: {lines[n-1]}", flush=True)


def main() -> None:
    print("✅ inspect_backfill_beforeinfo_history_pg.py VERSION 2026-07-20 focused-v1", flush=True)
    print(f"TARGET={TARGET}", flush=True)
    print("DB更新・外部通信なし", flush=True)

    if not TARGET.exists():
        raise FileNotFoundError(f"対象ファイルが見つかりません: {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    tree = ast.parse(text)

    print("\n=== IMPORTS / GLOBAL SETTINGS ===", flush=True)
    shown = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            for n in range(start, end + 1):
                print(f"{n:5d}: {lines[n-1]}", flush=True)
            shown += 1
        elif isinstance(node, ast.Assign):
            names = []
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
            if names and any(name in IMPORTANT_NAMES for name in names):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                for n in range(start, end + 1):
                    print(f"{n:5d}: {lines[n-1]}", flush=True)
                shown += 1
    if shown == 0:
        print("重要なグローバル設定は見つかりませんでした。", flush=True)

    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FUNCTIONS:
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            print_block(lines, start, end, f"FUNCTION {node.name}")
            found.add(node.name)

    missing = sorted(FUNCTIONS - found)
    if missing:
        print(f"\nmissing_functions={','.join(missing)}", flush=True)

    print("\n=== ENVIRONMENT VARIABLE REFERENCES ===", flush=True)
    env_lines = []
    for i, line in enumerate(lines, start=1):
        low = line.lower()
        if "os.getenv" in low or "os.environ" in low or "argparse" in low:
            env_lines.append((i, line))
    if not env_lines:
        print("none", flush=True)
    for i, line in env_lines[:80]:
        print(f"{i:5d}: {line}", flush=True)

    print("\n=== SQL WRITE REFERENCES ===", flush=True)
    sql_lines = []
    for i, line in enumerate(lines, start=1):
        low = line.lower()
        if any(token in low for token in (
            "insert into",
            "update ",
            "on conflict",
            "delete from",
            "v2_realtime_racer_condition_snapshots",
        )):
            sql_lines.append((i, line))
    if not sql_lines:
        print("none", flush=True)
    for i, line in sql_lines[:120]:
        print(f"{i:5d}: {line}", flush=True)

    print("\n=== FINISHED ===", flush=True)


if __name__ == "__main__":
    main()