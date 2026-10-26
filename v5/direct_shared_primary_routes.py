"""V5 canonical *physical* stage routing contract for future native collectors.

This module has NO I/O and is NOT hooked into the running V4/V5 collectors.
It provides the only intended target mapping for the separate V5-primary
pipeline; old collection keeps writing the old namespace during a canary.

Do not confuse boat_data.* legacy VIEWs or v5_data.raw_* historical proposals
with the currently existing physical stage: boat_data_stage.*.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from boat_shared_storage_contract import RELATIONS, assert_contract
from v5.offline_stage_batch_plan import TARGETS as STAGE_PLAN

# The routing contract is intentionally an explicit, fixed allowlist.
# Do not use dynamic SQL identifier input from configuration or official HTML.
_SOURCE_TO_STAGE = {src: pair[0] for src, pair in STAGE_PLAN.items()}
STAGE_ROUTES: Mapping[str, str] = MappingProxyType(_SOURCE_TO_STAGE)
LEGACY_SOURCES = frozenset(STAGE_ROUTES)

# The proposed canary remains DISABLED in the running system, regardless
# of these env names, until a native V5 writer actually calls the contract.
MODE_KEY = "V5_SHARED_PRIMARY_MODE"
GATE_KEY = "CONFIRM_V5_SHARED_PRIMARY_CANARY"
ISOLATION_KEY = "CONFIRM_LEGACY_WRITES_SEPARATELY"


def check_contract() -> None:
    """Offline invariant check only; neither DB metadata nor writer certification."""
    assert_contract()
    expected = {r.legacy for r in RELATIONS}
    if set(STAGE_ROUTES) != expected or len(STAGE_ROUTES) != 13:
        raise RuntimeError("STOP: source allowlist diverged from shared 13-family contract")
    targets = list(STAGE_ROUTES.values())
    if len(set(targets)) != 13:
        raise RuntimeError("STOP: duplicate physical V5 target")
    for source, target in STAGE_ROUTES.items():
        if not source.startswith("public.v2_"):
            raise RuntimeError("STOP: legacy source must remain in public.v2_*")
        if not target.startswith("boat_data_stage.") or target.count(".") != 1:
            raise RuntimeError("STOP: V5 writes must target boat_data_stage physical tables")
        if target in expected or target == source:
            raise RuntimeError("STOP: legacy and V5 target overlap")


def canonical_target(source_relation: str) -> str:
    """Return fixed stage name for known old logical source; unknown names fail."""
    check_contract()
    try:
        return STAGE_ROUTES[source_relation]
    except KeyError as exc:
        raise ValueError("STOP: unapproved V5 source identity") from exc


def canary_target(
    source_relation: str,
    *,
    env: Mapping[str, str],
    verified_physical: bool = False,
    verified_schema_and_keys: bool = False,
    independent_native_writer: bool = False,
    legacy_destination_isolated: bool = False,
    live_buy_disabled: bool = False,
) -> str:
    """Fail-closed authorization handshake for a FUTURE native V5 writer.

    Boolean checks must be supplied by independently tested runtime code;
    environment flags alone are deliberately insufficient. This routine does
    not connect, fetch, write, install services or authorize a production cutover.
    """
    target = canonical_target(source_relation)
    if env.get(MODE_KEY, "OFF") != "CANARY":
        raise RuntimeError("STOP: V5 primary canary not activated")
    if env.get(GATE_KEY) != "YES" or env.get(ISOLATION_KEY) != "YES":
        raise RuntimeError("STOP: explicit canary and legacy-isolation gates missing")
    if not all((verified_physical, verified_schema_and_keys,
                independent_native_writer, legacy_destination_isolated,
                live_buy_disabled)):
        raise RuntimeError("STOP: independent V5 writer or physical safety proof missing")
    return target


if __name__ == "__main__":
    check_contract()
    for source in sorted(STAGE_ROUTES):
        print("V5_ROUTE_PLAN_ONLY|" + source + "|" + STAGE_ROUTES[source])
    print("V5_DIRECT_PRIMARY_CONTRACT_OK_NO_DB_NO_HTTP_NO_WRITES_NO_CUTOVER")
