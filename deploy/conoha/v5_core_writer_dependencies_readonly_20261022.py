#!/usr/bin/env python3
"""Static source audit for remaining legacy V5 physical migration dependencies.

NO database/network calls, no services started, no writes. Output is only
allowlisted table names, relative source file names and counts; not SQL,
arguments, environment variables, passwords or source file content.
Static search is NOT proof that a source is used at runtime.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLES = (
    "v2_races", "v2_race_entries", "v2_results", "v2_result_entries",
    "v2_venues", "v2_odds_trifecta",
)
ACTIVE_CANDIDATES = (
    "repair_month_all_pg.py",
    "save_k_day_results_pg.py",
    "v21_realtime_collector_pg.py",
    "v21_realtime_collector_pg_safe.py",
    "v5/conoha_realtime_window_pg.py",
    "v5/conoha_midnight_results_pg.py",
)
EXCLUDE = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__", "tests",
    "docs", ".mypy_cache", ".pytest_cache", "site-packages",
})
SUFFIXES = frozenset({".py", ".sh", ".sql"})
MAX_FILE_BYTES = 512000
MAX_FILES = 4000
MAX_DISPLAY = 10
WRITE = re.compile(
    r"\b(?:insert\s+into|update|delete\s+from|merge\s+into"
    r"|truncate(?:\s+table)?|copy)\s+(?:public\.)?{name}\b"
    r"|\b(?:upsert_rows|replace_rows_atomic)\s*\(\s*['\"]{name}['\"]",
    flags=re.I,
)
DDL = re.compile(
    r"\b(?:create\s+table(?:\s+if\s+not\s+exists)?"
    r"|alter\s+table|drop\s+table(?:\s+if\s+exists)?)"
    r"\s+(?:public\.)?{name}\b", re.I,
)
SAFE_PATH = re.compile(r"^[A-Za-z0-9_./-]+$")


def sources():
    total = 0
    skipped_big = 0
    skipped_cap = False
    files = []
    for path in ROOT.rglob("*"):
        try:
            if any(part in EXCLUDE or part.startswith(".") for part in path.relative_to(ROOT).parts):
                continue
            if path.suffix not in SUFFIXES or not path.is_file():
                continue
            if not path.resolve().is_relative_to(ROOT):
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                skipped_big += 1
                continue
            if total >= MAX_FILES:
                skipped_cap = True
                break
            rel = path.relative_to(ROOT).as_posix()
            if not SAFE_PATH.fullmatch(rel):
                continue
            total += 1
            files.append((rel, path.read_text(encoding="utf-8", errors="replace")))
        except (OSError, ValueError):
            continue
    return files, skipped_big, skipped_cap


def main():
    print("MODE=V5_CORE_WRITER_DEPENDENCIES_READ_ONLY", flush=True)
    files, skipped_big, skipped_cap = sources()
    lookup = dict(files)
    print(f"SCANNED_LOCAL_SOURCE_FILES={len(files)} OVERSIZED_SKIPPED={skipped_big} FILE_LIMIT_HIT={int(skipped_cap)}", flush=True)

    print("=== NAMED_RUNTIME_CANDIDATES (static only) ===", flush=True)
    for rel in ACTIVE_CANDIDATES:
        text = lookup.get(rel)
        if text is None:
            print("CANDIDATE|" + rel + "|NOT_SCANNED", flush=True)
            continue
        refs = [t for t in TABLES if re.search(r"\b"+re.escape(t)+r"\b", text)]
        print("CANDIDATE|" + rel + "|refs=" + (",".join(refs) or "-"), flush=True)

    print("=== FULL LOCAL SOURCE DEPENDENCIES (static lexical hints) ===", flush=True)
    for table in TABLES:
        needle = re.compile(r"\b" + re.escape(table) + r"\b", re.I)
        write = re.compile(WRITE.pattern.format(name=re.escape(table)), re.I)
        ddl = re.compile(DDL.pattern.format(name=re.escape(table)), re.I)
        refs, writers, ddl_files = [], [], []
        for rel, data in files:
            if not needle.search(data):
                continue
            refs.append(rel)
            if write.search(data):
                writers.append(rel)
            if ddl.search(data):
                ddl_files.append(rel)
        # Keep output short on mobile; filenames are not executable code.
        print(
            "TABLE|" + table
            + "|REF_FILES=" + str(len(refs))
            + "|WRITE_HINT_FILES=" + str(len(writers))
            + "|DDL_HINT_FILES=" + str(len(ddl_files)),
            flush=True,
        )
        for kind, items in (("WRITE_HINT", writers), ("DDL_HINT", ddl_files)):
            selected = sorted(items, key=lambda x: (x not in ACTIVE_CANDIDATES, x))[:MAX_DISPLAY]
            print(kind + "|" + table + "|" + (",".join(selected) or "-"), flush=True)
            if len(items) > MAX_DISPLAY:
                print(kind + "_MORE|" + table + "|" + str(len(items) - MAX_DISPLAY), flush=True)
    print("STATIC_HINTS_ARE_NOT_RUNTIME_WRITE_PATH_CERTIFICATION", flush=True)
    print("NO_DB_WRITES_NO_SERVICE_CHANGES_NO_SECRETS_PRINTED", flush=True)
    print("V5_CORE_WRITER_DEPENDENCY_AUDIT_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
