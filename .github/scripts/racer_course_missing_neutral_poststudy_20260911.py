# -*- coding: utf-8 -*-
"""Post-study temporal holdout wrapper for the frozen Course neutral rule.

Preregistration: c7f7daf39eaa877fb605e43d52a978b206c87b89
This wrapper changes only the fixed calendar window and minimum sample size for
sensitivity interpretation. The underlying missing-lane rule and coefficient
are imported unchanged from racer_course_missing_neutral_oos_20260911.py.
"""
from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path

PREREG = "c7f7daf39eaa877fb605e43d52a978b206c87b89"
START = date(2026, 8, 25)
END = date(2026, 9, 10)
MIN_MISSING_RACES = 300
MIN_MISSING_DATES = 10

SOURCE = Path(__file__).with_name("racer_course_missing_neutral_oos_20260911.py")
spec = importlib.util.spec_from_file_location("course_neutral_base", SOURCE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

# Fixed post-study sensitivity parameters, frozen before subset outcomes are read.
module.START = START
module.END = END
module.MIN_MISSING_RACES = MIN_MISSING_RACES
module.MIN_MISSING_DATES = MIN_MISSING_DATES


def main() -> None:
    print(f"COURSE_POSTSTUDY_PREREG={PREREG}", flush=True)
    print(f"COURSE_POSTSTUDY_PERIOD={START}..{END}", flush=True)
    print("COURSE_POSTSTUDY_RULE=reuse_frozen_neutral_missing_rule_unchanged", flush=True)
    module.main()


if __name__ == "__main__":
    main()
