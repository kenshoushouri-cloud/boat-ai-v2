"""Fail-closed guard against legacy public tables reappearing during V5 migration.

Only the explicit V5 cutover flag changes behavior. With flag absent, existing
realtime collector remains identical. This guard does NOT perform migration,
does NOT rewrite writes/reads and must never be enabled before a cutover plan.
"""
from __future__ import annotations

import os

GUARD_FLAG = "V5_BLOCK_LEGACY_REALTIME_DDL"


def require_legacy_realtime_ddl_allowed() -> None:
    """Stop BEFORE CREATE/ALTER if a V5 cutover has blocked legacy DDL."""
    flag = os.environ.get(GUARD_FLAG, "")
    if flag not in ("", "0", "NO", "YES"):
        raise RuntimeError(f"STOP: invalid {GUARD_FLAG} value; expected YES or unset")
    if flag == "YES":
        raise RuntimeError(
            "STOP: legacy realtime CREATE/ALTER blocked for V5 migration; "
            "do not recreate public.v2_realtime_* tables"
        )
