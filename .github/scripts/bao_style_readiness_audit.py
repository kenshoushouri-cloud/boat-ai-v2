# -*- coding: utf-8 -*-
"""Static read-only audit of Bao-style architecture readiness.

No DB access, no network access, no Production/Shadow/LINE changes.
This does not inspect or reproduce proprietary formulas. It only inventories
whether the repository already contains building blocks for a generic
index -> probability -> odds/value -> validation workflow.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
EXCLUDE = {'.git', '.venv', 'venv', '__pycache__', 'archive'}
CATEGORIES = {
    'feature_score': [r'feature', r'score', r'index', r'candidate'],
    'probability_calibration': [r'probab', r'calibrat', r'logit', r'isotonic', r'brier'],
    'odds_value': [r'odds', r'expected.?value', r'\bev\b', r'value.?bet', r'roi'],
    'validation': [r'backtest', r'oos', r'walk.?forward', r'forward', r'shadow'],
    'ticket_selection': [r'ticket', r'buy', r'watch', r'skip', r'bet'],
}


def files():
    for p in ROOT.rglob('*.py'):
        if any(part in EXCLUDE for part in p.parts):
            continue
        yield p


def main():
    print('BAO_READINESS_MODE=static_read_only', flush=True)
    hits = {k: [] for k in CATEGORIES}
    for p in files():
        try:
            text = p.read_text(encoding='utf-8', errors='ignore').lower()
        except OSError:
            continue
        rel = str(p.relative_to(ROOT))
        for cat, pats in CATEGORIES.items():
            if any(re.search(pat, text, re.I) for pat in pats):
                hits[cat].append(rel)

    for cat, paths in hits.items():
        uniq = sorted(set(paths))
        print(f'BAO_READINESS_{cat.upper()}_FILES={len(uniq)}', flush=True)
        for p in uniq[:20]:
            print(f'BAO_READINESS_{cat.upper()}_FILE={p}', flush=True)

    # Gate only on basic architecture presence. Probability calibration may
    # legitimately be absent; that is a finding, not a CI failure.
    required = ('feature_score', 'odds_value', 'validation', 'ticket_selection')
    missing = [k for k in required if not hits[k]]
    print('BAO_READINESS_MISSING_REQUIRED=' + (','.join(missing) if missing else 'NONE'), flush=True)
    print('BAO_READINESS_CALIBRATION_GAP=' + ('YES' if not hits['probability_calibration'] else 'NO'), flush=True)
    if missing:
        print('BAO_READINESS_RESULT=FAIL_ARCHITECTURE_GAP', flush=True)
        raise SystemExit(2)
    print('BAO_READINESS_RESULT=PASS_STATIC', flush=True)


if __name__ == '__main__':
    main()
