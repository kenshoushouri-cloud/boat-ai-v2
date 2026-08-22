# -*- coding: utf-8 -*-
"""Static/runtime isolation checks for the optional wave Shadow hook."""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.pop("RUN_WAVE_VL_FINAL_SHADOW", None)
import v25_final_realtime_pipeline_pg as p

print(f"WAVE_HOOK_TEST_DEFAULT_ENABLED={int(p.RUN_WAVE_VL_FINAL_SHADOW)}")
if p.RUN_WAVE_VL_FINAL_SHADOW:
    raise SystemExit("wave hook must default OFF")

ok = p._run_optional_shadow(
    [sys.executable, "-c", "import sys; sys.exit(7)"],
    {"TARGET_DATE": "2099-01-01"},
)
print(f"WAVE_HOOK_TEST_FAILURE_RETURN={ok}")
if ok is not False:
    raise SystemExit("optional runner must return False for failed child")

ok2 = p._run_optional_shadow(
    [sys.executable, "-c", "import sys; sys.exit(0)"],
    {"TARGET_DATE": "2099-01-01"},
)
print(f"WAVE_HOOK_TEST_SUCCESS_RETURN={ok2}")
if ok2 is not True:
    raise SystemExit("optional runner must return True for successful child")

print("WAVE_HOOK_TEST_RESULT=PASS")
