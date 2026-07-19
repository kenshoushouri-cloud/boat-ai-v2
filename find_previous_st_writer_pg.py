# -*- coding: utf-8 -*-
"""
find_previous_st_writer_pg.py

既存コードから previous_st の取得・保存処理だけを絞り込んで表示します。
大量ログを避けるため、該当ファイル名・関数名・SQL周辺だけを出力します。

Railway Start Command:
    python -u find_previous_st_writer_pg.py

Variables:
    DISCOVER_ROOT=.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Iterable

ROOT = Path(os.getenv("DISCOVER_ROOT", ".")).resolve()
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".pytest_cache", ".mypy_cache", "site-packages",
}

NEEDLES = (
    "insert into v2_realtime_racer_condition_snapshots",
    "update v2_realtime_racer_condition_snapshots",
    "official_beforeinfo_history",
    "previous_race_no",
    "previous_course",
    "previous_finish",
    "previous_st",
)


def iter_python_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            yield p


def enclosing_function(tree: ast.AST, line_no: int) -> str:
    best = None
    best_span = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start and end and start <= line_no <= end:
                span = end - start
                if best_span is None or span < best_span:
                    best = node.name
                    best_span = span
    return best or "(module)"


def main() -> None:
    print("✅ find_previous_st_writer_pg.py VERSION 2026-07-20 writer-find-v1", flush=True)
    print(f"ROOT={ROOT}", flush=True)

    matched_files = 0

    for path in sorted(iter_python_files(ROOT)):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            tree = ast.parse(text)
        except Exception:
            continue

        hits = []
        for i, line in enumerate(lines, start=1):
            low = line.lower()
            matched = [n for n in NEEDLES if n.lower() in low]
            if matched:
                hits.append((i, matched))

        # 保存・公式履歴のどちらかがあるファイルだけ出す
        file_low = text.lower()
        is_writer_candidate = (
            "v2_realtime_racer_condition_snapshots" in file_low
            and (
                "insert into" in file_low
                or "official_beforeinfo_history" in file_low
            )
        )
        if not is_writer_candidate:
            continue

        matched_files += 1
        rel = path.relative_to(ROOT)
        print(f"\n=== FILE {rel} ===", flush=True)

        shown = set()
        for line_no, matched in hits:
            fn = enclosing_function(tree, line_no)
            key = (fn, line_no)
            if key in shown:
                continue
            shown.add(key)

            start = max(1, line_no - 4)
            end = min(len(lines), line_no + 6)
            print(
                f"FUNCTION={fn} LINE={line_no} MATCH={','.join(matched)}",
                flush=True,
            )
            for n in range(start, end + 1):
                print(f"{n:5d}: {lines[n-1]}", flush=True)

    print(f"\nwriter_candidate_files={matched_files}", flush=True)
    print("=== WRITER FIND FINISHED ===", flush=True)


if __name__ == "__main__":
    main()