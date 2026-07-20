# -*- coding: utf-8 -*-
"""
list_previous_st_writer_files.py

previous_st の取得・保存に関係する実ファイル名だけを少量表示します。
DB接続・DB更新・外部通信は行いません。

Railway Start Command:
    python -u list_previous_st_writer_files.py

Variables:
    DISCOVER_ROOT=.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT = Path(os.getenv("DISCOVER_ROOT", ".")).resolve()

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".pytest_cache", ".mypy_cache", "site-packages",
}

EXCLUDE_FILES = {
    "list_previous_st_writer_files.py",
    "find_previous_st_writer_pg.py",
    "discover_previous_st_pipeline_pg.py",
    "check_previous_st_coverage_june_2026_pg.py",
    "diagnose_previous_st_sources_pg.py",
}

STRONG_MARKERS = (
    "official_beforeinfo_history",
    "insert into v2_realtime_racer_condition_snapshots",
    "update v2_realtime_racer_condition_snapshots",
)

SUPPORT_MARKERS = (
    "previous_race_no",
    "previous_course",
    "previous_finish",
    "previous_st",
    "v2_realtime_racer_condition_snapshots",
)


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDE_FILES:
            continue
        if path.is_file():
            yield path


def get_function_names(text: str, line_numbers: List[int]) -> List[str]:
    try:
        tree = ast.parse(text)
    except Exception:
        return []

    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", start)
        if any(start <= n <= end for n in line_numbers):
            names.add(node.name)
    return sorted(names)


def scan(path: Path) -> Tuple[List[str], List[str], List[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    low = text.lower()

    strong = [m for m in STRONG_MARKERS if m.lower() in low]
    support = [m for m in SUPPORT_MARKERS if m.lower() in low]

    line_numbers = []
    for i, line in enumerate(text.splitlines(), start=1):
        line_low = line.lower()
        if any(m.lower() in line_low for m in STRONG_MARKERS + SUPPORT_MARKERS):
            line_numbers.append(i)

    functions = get_function_names(text, line_numbers)
    return strong, support, functions


def main() -> None:
    print("✅ list_previous_st_writer_files.py VERSION 2026-07-20 filenames-only-v1", flush=True)
    print(f"ROOT={ROOT}", flush=True)
    print("DB更新・外部通信なし", flush=True)

    strong_candidates = []
    support_candidates = []

    for path in sorted(iter_python_files(ROOT)):
        try:
            strong, support, functions = scan(path)
        except Exception:
            continue

        rel = str(path.relative_to(ROOT))

        if strong:
            strong_candidates.append((rel, strong, functions))
        elif (
            "previous_st" in support
            and "v2_realtime_racer_condition_snapshots" in support
        ):
            support_candidates.append((rel, support, functions))

    print("\n=== STRONG CANDIDATES ===", flush=True)
    if not strong_candidates:
        print("none", flush=True)
    for rel, markers, functions in strong_candidates[:20]:
        print(f"FILE={rel}", flush=True)
        print(f"  MARKERS={','.join(markers)}", flush=True)
        print(f"  FUNCTIONS={','.join(functions) if functions else '(module/unknown)'}", flush=True)

    print("\n=== SUPPORT CANDIDATES ===", flush=True)
    if not support_candidates:
        print("none", flush=True)
    for rel, markers, functions in support_candidates[:20]:
        print(f"FILE={rel}", flush=True)
        print(f"  FUNCTIONS={','.join(functions) if functions else '(module/unknown)'}", flush=True)

    print(
        f"\nstrong_candidate_count={len(strong_candidates)} "
        f"support_candidate_count={len(support_candidates)}",
        flush=True,
    )
    print("=== FINISHED ===", flush=True)


if __name__ == "__main__":
    main()