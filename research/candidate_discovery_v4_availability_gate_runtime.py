# -*- coding: utf-8 -*-
"""Runtime bridge for approved V4 availability eligibility activation.

This module performs only local-file verification and pure availability
evaluation after the prospective V4 artifact has been generated. It has no
network, database, Railway, LINE, candidate generation, rerank, replacement,
result/payout, or purchase surface.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from research.candidate_discovery_v4_availability_guard import (
    evaluate_availability_guard,
)
from research.candidate_discovery_v4_availability_snapshot_binder import (
    bind_availability_snapshot,
)
from research.candidate_discovery_v4_pre_freeze_availability_capture import (
    MANIFEST_CONTRACT,
    REQUEST_CONTRACT,
)

RESULT_CONTRACT = "candidate_discovery_v4_availability_gate_runtime_v1"


class V4AvailabilityGateRuntimeError(ValueError):
    pass


def _load_json(path: Path, *, field: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise V4AvailabilityGateRuntimeError(
            f"{field} is not valid UTF-8 JSON: {path}"
        ) from exc


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_request_manifest_identity(
    request: Any,
    manifest: Any,
) -> None:
    if not isinstance(request, dict) or request.get("contract") != REQUEST_CONTRACT:
        raise V4AvailabilityGateRuntimeError("unexpected capture request contract")
    if not isinstance(manifest, dict) or manifest.get("contract") != MANIFEST_CONTRACT:
        raise V4AvailabilityGateRuntimeError("unexpected capture manifest contract")

    exact_fields = (
        "target_date",
        "venue_ids",
        "scheduled_race_count",
        "race_universe_sha256",
        "hard_stop_at_jst",
        "hard_stop_basis",
    )
    mismatches = [
        field
        for field in exact_fields
        if request.get(field) != manifest.get(field)
    ]
    if mismatches:
        raise V4AvailabilityGateRuntimeError(
            "capture request/manifest identity mismatch: " + ",".join(mismatches)
        )


def _load_payloads(
    manifest: dict[str, Any],
    capture_dir: Path,
) -> dict[str, bytes]:
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise V4AvailabilityGateRuntimeError("capture manifest sources missing")

    payloads: dict[str, bytes] = {}
    seen_filenames: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise V4AvailabilityGateRuntimeError("capture source must be an object")
        filename = source.get("raw_filename")
        if (
            not isinstance(filename, str)
            or not filename
            or Path(filename).name != filename
            or filename in seen_filenames
        ):
            raise V4AvailabilityGateRuntimeError(
                f"invalid/duplicate raw_filename: {filename!r}"
            )
        seen_filenames.add(filename)
        path = capture_dir / filename
        if not path.is_file():
            raise V4AvailabilityGateRuntimeError(
                f"capture raw file missing: {filename}"
            )
        payloads[filename] = path.read_bytes()
    return payloads


def evaluate_gate_files(
    *,
    artifact_path: Path,
    capture_dir: Path,
    request_path: Path,
    snapshot_output: Path,
    result_output: Path,
) -> dict[str, Any]:
    artifact = _load_json(artifact_path, field="formal artifact")
    manifest_path = capture_dir / "manifest.json"
    manifest = _load_json(manifest_path, field="capture manifest")
    request = _load_json(request_path, field="capture request")

    _validate_request_manifest_identity(request, manifest)
    payloads = _load_payloads(manifest, capture_dir)

    snapshot = bind_availability_snapshot(
        artifact,
        manifest,
        payloads,
    )
    guard = evaluate_availability_guard(
        artifact,
        snapshot,
    )

    if guard.get("purchase_action") is not False:
        raise V4AvailabilityGateRuntimeError(
            "availability guard purchase_action must be false"
        )
    if guard.get("replacement_candidates_generated") is not False:
        raise V4AvailabilityGateRuntimeError(
            "availability guard replacement invariant violated"
        )
    if guard.get("ranking_changed") is not False:
        raise V4AvailabilityGateRuntimeError(
            "availability guard ranking invariant violated"
        )

    result = {
        "contract": RESULT_CONTRACT,
        "target_date": guard["target_date"],
        "decision": guard["decision"],
        "eligible_under_guard": guard["eligible_under_guard"],
        "formal_core_races": guard["formal_core_races"],
        "blocked_core_races": guard["blocked_core_races"],
        "artifact_sha256": _file_sha256(artifact_path),
        "capture_request_sha256": _file_sha256(request_path),
        "capture_manifest_sha256": _file_sha256(manifest_path),
        "race_universe_sha256": manifest.get("race_universe_sha256"),
        "snapshot_contract": snapshot["contract"],
        "replacement_candidates_generated": False,
        "ranking_changed": False,
        "purchase_action": False,
        "production_mutation": False,
    }

    snapshot_output.write_text(
        json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result_output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--capture-dir", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--snapshot-output", required=True)
    parser.add_argument("--result-output", required=True)
    args = parser.parse_args()

    result = evaluate_gate_files(
        artifact_path=Path(args.artifact),
        capture_dir=Path(args.capture_dir),
        request_path=Path(args.request),
        snapshot_output=Path(args.snapshot_output),
        result_output=Path(args.result_output),
    )
    print(
        f"CANDIDATE_V4_AVAILABILITY_GATE_DECISION={result['decision']}",
        flush=True,
    )
    print(
        "CANDIDATE_V4_AVAILABILITY_GATE_ELIGIBLE="
        + ("true" if result["eligible_under_guard"] else "false"),
        flush=True,
    )
    print("CANDIDATE_V4_AVAILABILITY_GATE_REPLACEMENT=0", flush=True)
    print("CANDIDATE_V4_AVAILABILITY_GATE_RERANK=0", flush=True)
    print("CANDIDATE_V4_AVAILABILITY_GATE_PURCHASE_ACTION=false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
