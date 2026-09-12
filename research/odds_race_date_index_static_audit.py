from __future__ import annotations

"""Pure static audit for direct race_date use on v2_odds_trifecta.

This module never connects to PostgreSQL, Railway, or the network. It scans SQL string
constants in repository Python/SQL files and classifies whether the odds table's own
``race_date`` column is referenced in a WHERE clause. The goal is to distinguish true
index consumers from files that merely query ``v2_races.race_date`` elsewhere.
"""

import argparse
import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TABLE = "v2_odds_trifecta"
SELF_PATH = "research/odds_race_date_index_static_audit.py"
TEST_PATH = "tests/test_odds_race_date_index_static_audit.py"

TABLE_REF_RE = re.compile(
    r"\b(?:from|join)\s+v2_odds_trifecta\b(?:\s+(?:as\s+)?([a-z_][a-z0-9_]*))?",
    re.IGNORECASE,
)
UNQUALIFIED_WHERE_RACE_DATE_RE = re.compile(
    r"\bwhere\b[\s\S]*?(?<!\.)\brace_date\b",
    re.IGNORECASE,
)
SQL_ALIAS_STOPWORDS = {
    "where",
    "on",
    "left",
    "right",
    "inner",
    "outer",
    "full",
    "cross",
    "join",
    "order",
    "group",
    "limit",
    "union",
    "having",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    aliases: tuple[str, ...]
    direct_qualified_race_date: bool
    unqualified_where_race_date: bool
    snippet: str

    @property
    def direct_candidate(self) -> bool:
        return self.direct_qualified_race_date or self.unqualified_where_race_date


def _aliases(sql: str) -> tuple[str, ...]:
    aliases: list[str] = []
    for match in TABLE_REF_RE.finditer(sql):
        alias = (match.group(1) or TABLE).lower()
        if alias in SQL_ALIAS_STOPWORDS:
            alias = TABLE
        if alias not in aliases:
            aliases.append(alias)
    return tuple(aliases)


def classify_sql(path: str, line: int, sql: str) -> Finding | None:
    if TABLE not in sql.lower():
        return None
    aliases = _aliases(sql)
    if not aliases:
        return None

    low = sql.lower()
    direct_qualified = bool(re.search(r"\bv2_odds_trifecta\.race_date\b", low))
    for alias in aliases:
        direct_qualified = direct_qualified or bool(
            re.search(rf"\b{re.escape(alias)}\.race_date\b", low)
        )

    unqualified = bool(UNQUALIFIED_WHERE_RACE_DATE_RE.search(low))
    compact = " ".join(sql.split())
    if len(compact) > 240:
        compact = compact[:237] + "..."
    return Finding(
        path=path,
        line=line,
        aliases=aliases,
        direct_qualified_race_date=direct_qualified,
        unqualified_where_race_date=unqualified,
        snippet=compact,
    )


def _python_strings(path: Path) -> Iterable[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((getattr(node, "lineno", 1), node.value))
    return out


def _sql_strings(path: Path) -> Iterable[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out: list[tuple[int, str]] = []
    offset = 0
    for chunk in text.split(";"):
        line = text.count("\n", 0, offset) + 1
        out.append((line, chunk))
        offset += len(chunk) + 1
    return out


def scan_repo(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".py", ".sql"}:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in {SELF_PATH, TEST_PATH}:
            continue
        if any(part in {".git", ".venv", "venv", "node_modules"} for part in path.parts):
            continue
        strings = _python_strings(path) if path.suffix.lower() == ".py" else _sql_strings(path)
        for line, value in strings:
            finding = classify_sql(rel, line, value)
            if finding is not None:
                findings.append(finding)
    return findings


def render(findings: list[Finding]) -> str:
    direct = [f for f in findings if f.direct_candidate]
    qualified = [f for f in findings if f.direct_qualified_race_date]
    unqualified = [f for f in findings if f.unqualified_where_race_date]
    lines = [
        "ODDS_RACE_DATE_STATIC_MODE=PURE_NO_DB_NO_NETWORK",
        f"ODDS_RACE_DATE_SQL_STRINGS={len(findings)}",
        f"ODDS_RACE_DATE_DIRECT_CANDIDATES={len(direct)}",
        f"ODDS_RACE_DATE_QUALIFIED_DIRECT={len(qualified)}",
        f"ODDS_RACE_DATE_UNQUALIFIED_WHERE={len(unqualified)}",
    ]
    for item in direct:
        lines.append(
            "ODDS_RACE_DATE_CANDIDATE="
            f"path:{item.path} line:{item.line} aliases:{','.join(item.aliases)} "
            f"qualified:{str(item.direct_qualified_race_date).lower()} "
            f"unqualified:{str(item.unqualified_where_race_date).lower()} "
            f"sql:{item.snippet}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--assert-no-direct", action="store_true")
    args = parser.parse_args()
    findings = scan_repo(args.root.resolve())
    print(render(findings))
    direct = [f for f in findings if f.direct_candidate]
    if args.assert_no_direct and direct:
        print("ODDS_RACE_DATE_STATIC_RESULT=BLOCK_DIRECT_CONSUMER_FOUND")
        return 2
    print("ODDS_RACE_DATE_STATIC_RESULT=PASS_NO_DIRECT_CONSUMER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
