# -*- coding: utf-8 -*-
"""Thin adapter over the frozen Opponent Pressure v2 implementation.

Kept separate so historical replay and Forward code share the exact scoring
math without bypassing the Forward timing guard in the live collector.
"""
from __future__ import annotations

from datetime import date

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "opponent_pressure_shadow_v2_compact.py"
spec = importlib.util.spec_from_file_location("frozen_opp_v2", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load frozen opponent v2")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TRAIN_START = mod.TRAIN_START
MIN_MATCHED_OPPONENTS = 4  # frozen V4 consumer threshold
TARGET_DATE = mod.TARGET_DATE


def _sync() -> None:
    mod.TARGET_DATE = TARGET_DATE


def load_targets(conn):
    _sync()
    return mod._load_targets(conn)


def load_effects(conn):
    _sync()
    return mod._load_effects(conn)


def score(rows, effects):
    return mod._score(rows, effects)
