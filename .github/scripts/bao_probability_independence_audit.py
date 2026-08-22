# -*- coding: utf-8 -*-
"""Static read-only audit of probability generation vs market-odds dependency.

The goal is to establish whether current ticket probabilities can be treated as
independent ability estimates for a Bao-style value layer. This does not execute
Production code and performs no DB access or writes.
"""
from __future__ import annotations

import ast
from pathlib import Path

TARGETS = [
    Path("v24_pre_candidate_notifier_pg.py"),
    Path("collect_v24_motor2_forward_shadow_pg.py"),
    Path("v22_exhibition_shadow_pg.py"),
]

PROB_WORDS = {"prob", "probability", "softmax", "score", "ticket", "rank"}
MARKET_WORDS = {"odds", "market", "raw_ev", "expected_value", "expected_return"}


def names_in(node: ast.AST) -> set[str]:
    out = set()
    for x in ast.walk(node):
        if isinstance(x, ast.Name):
            out.add(x.id.lower())
        elif isinstance(x, ast.Attribute):
            out.add(x.attr.lower())
        elif isinstance(x, ast.Constant) and isinstance(x.value, str):
            s = x.value.lower()
            for w in PROB_WORDS | MARKET_WORDS:
                if w in s:
                    out.add(w)
    return out


def text_of(path: Path, node: ast.AST) -> str:
    src = path.read_text(encoding="utf-8")
    return ast.get_source_segment(src, node) or ""


def audit_file(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    funcs = []
    assignments = []
    permutation_calls = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ns = names_in(node)
            name_l = node.name.lower()
            relevant = bool(PROB_WORDS.intersection(ns) or any(w in name_l for w in PROB_WORDS))
            if relevant:
                market_refs = sorted(MARKET_WORDS.intersection(ns))
                prob_refs = sorted(PROB_WORDS.intersection(ns))
                funcs.append((node.name, node.lineno, prob_refs, market_refs))
        if isinstance(node, ast.Assign):
            targets = []
            for t in node.targets:
                if isinstance(t, ast.Name): targets.append(t.id)
                elif isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant): targets.append(str(t.slice.value))
            tl = " ".join(targets).lower()
            if any(w in tl for w in ("prob", "raw_ev", "expected_value")):
                ns = names_in(node.value)
                assignments.append((node.lineno, targets, sorted(MARKET_WORDS.intersection(ns)), sorted(PROB_WORDS.intersection(ns))))
        if isinstance(node, ast.Call):
            fn = ""
            if isinstance(node.func, ast.Attribute): fn = node.func.attr.lower()
            elif isinstance(node.func, ast.Name): fn = node.func.id.lower()
            if fn == "permutations": permutation_calls += 1

    print(f"BAO_PI_FILE={path} relevant_functions:{len(funcs)} probability_assignments:{len(assignments)} permutation_calls:{permutation_calls}")
    for name, line, prefs, mrefs in funcs:
        print(f"BAO_PI_FUNC=file:{path} line:{line} name:{name} prob_refs:{','.join(prefs) or '-'} market_refs:{','.join(mrefs) or '-'}")
    for line, targets, mrefs, prefs in assignments:
        print(f"BAO_PI_ASSIGN=file:{path} line:{line} targets:{','.join(targets)} prob_refs:{','.join(prefs) or '-'} market_refs:{','.join(mrefs) or '-'}")

    return {"funcs": funcs, "assignments": assignments, "perms": permutation_calls, "source": src}


def main() -> None:
    print("BAO_PI_MODE=static_read_only")
    missing = [str(p) for p in TARGETS if not p.exists()]
    if missing:
        raise SystemExit(f"missing targets: {missing}")

    results = {str(p): audit_file(p) for p in TARGETS}
    v24 = results["v24_pre_candidate_notifier_pg.py"]

    # Conservative readiness gate: we need evidence of 120-ticket construction
    # and at least one probability-related function that does not reference odds/market.
    has_permutations = v24["perms"] > 0 or "itertools.permutations" in v24["source"]
    independent_funcs = [x for x in v24["funcs"] if not x[3] and x[2]]
    market_funcs = [x for x in v24["funcs"] if x[3]]
    raw_ev_market = any("raw_ev" in " ".join(a[1]).lower() and ("odds" in a[2] or "market" in a[2]) for a in v24["assignments"])

    print(f"BAO_PI_V24=permutations:{int(has_permutations)} independent_prob_funcs:{len(independent_funcs)} market_aware_funcs:{len(market_funcs)} raw_ev_uses_market:{int(raw_ev_market)}")
    if independent_funcs:
        print("BAO_PI_INDEPENDENT_CANDIDATES=" + ",".join(x[0] for x in independent_funcs[:20]))

    # We deliberately do not claim full independence solely from AST evidence.
    ready = has_permutations and len(independent_funcs) > 0
    print(f"BAO_PI_REPLAY_READINESS={'CANDIDATE' if ready else 'BLOCKED'}")
    print("BAO_PI_NEXT=runtime_replay_on_fixed_historical_days_without_odds_input")
    print("BAO_PI_RESULT=PASS_STATIC_AUDIT")


if __name__ == "__main__":
    main()
