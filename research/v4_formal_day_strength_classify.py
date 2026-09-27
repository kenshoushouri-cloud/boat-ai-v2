# -*- coding: utf-8 -*-
"""Pure local-file classifier for a future formal V4 day-strength shadow label."""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from research.v4_formal_day_strength_shadow import (
    classify_future_day,
    extract_formal_day,
)


def load_zip(path: str | Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        return json.loads(zf.read("candidate-discovery-v4-prospective-freeze.json"))


def classify(target_zip: str | Path, prior_dir: str | Path) -> dict:
    current = extract_formal_day(load_zip(target_zip))
    root = Path(prior_dir)
    prior = []
    for path in sorted(root.glob("*.zip")):
        x = extract_formal_day(load_zip(path))
        if x.target_date < current.target_date:
            prior.append(x)
    return classify_future_day(current, prior)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: v4_formal_day_strength_classify.py TARGET.zip PRIOR_DIR"
        )
    result = classify(sys.argv[1], sys.argv[2])
    print("V4_DAY_STRENGTH_CLASSIFICATION=" + json.dumps(result, sort_keys=True))
    print("V4_DAY_STRENGTH_CLASSIFY_PASS_PURE_LOCAL_FILES")


if __name__ == "__main__":
    main()
