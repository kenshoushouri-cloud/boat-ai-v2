#!/usr/bin/env python3
"""Offline-only contract for Railway DB -> private Drive backup selection.

No DB connector, Google client, I/O except environment. Expected folder IDs
are compared by SHA256 so their raw IDs are not committed to GitHub.
"""
from __future__ import annotations

from hashlib import sha256
import os
import sys


class BindingError(ValueError):
    pass


# Service UUIDs are historical identity pins, not proof of the live DB endpoint.
# Folder hash pins are based on previously verified private folder identifiers;
# re-check account ownership, OAuth remote and current IDs before any online run.
TARGETS = {
    "v3": {
        "service": "03652c28-20fa-4807-aa8c-8e71b6f21d26",
        "remote": "boat-drive-v3",
        "folder_sha256": "c9a1145f79c4c298fd3c2eec3951f12576ffb1620477f770940bab35b8f487f2",
        "recipient_sha256": "da094443ccc50f1e0d253d02c670c52bedeb64ac2c479888659a62e05d978234",
    },
    "archive": {
        "service": "f2586b91-9381-4269-b473-42b121782c4e",
        "remote": "boat-drive-archive",
        "folder_sha256": "ab97ffb1cf234d72d8f9a2b651a901dfbe3485332f28517a1afbc856fe6b41cb",
        "recipient_sha256": "7c92ab52ed14f95552540e9aa0b57c98f909be9626d27c0a334441017768591b",
    },
    "v4": {
        "service": "29eb7f33-bfd0-4d45-8893-ffe40b4e1c52",
        "remote": "boat-drive-v4",
        "folder_sha256": "f6abf9ed8c46f69f539c31325d5eb7f051c61d84a09a846575b0178fac0bb716",
        "recipient_sha256": "7c92ab52ed14f95552540e9aa0b57c98f909be9626d27c0a334441017768591b",
    },
    "v5": {
        "service": "79a434b5-b9de-40ef-aa23-d393b245f830",
        "remote": "boat-drive-v5",
        "folder_sha256": "31381f10c3958b87361ea8d3c024762a9891ca48eb327c2221a44b09fdbeb094",
        "recipient_sha256": "7c92ab52ed14f95552540e9aa0b57c98f909be9626d27c0a334441017768591b",
    },
}


def validate_binding(*, target: str, mode: str, service_id: str,
                     remote: str, folder_id: str, recipient_hash: str,
                     target_approval: str) -> None:
    if target not in TARGETS:
        raise BindingError("unknown_target")
    if mode not in ("validate", "preflight", "execute"):
        raise BindingError("invalid_mode")
    expected = TARGETS[target]
    if service_id != expected["service"]:
        raise BindingError("source_service_mismatch")
    if remote != expected["remote"]:
        raise BindingError("drive_remote_mismatch")
    if sha256(folder_id.encode("utf-8")).hexdigest() != expected["folder_sha256"]:
        raise BindingError("drive_folder_pin_mismatch")
    # Reject swapped recipient fingerprints for every pinned backup target.
    if expected["recipient_sha256"] is not None and recipient_hash != expected["recipient_sha256"]:
        raise BindingError("recovery_recipient_pin_mismatch")
    if mode == "execute":
        if target_approval != f"YES_SINGLE_{target.upper()}_ENCRYPTED_SNAPSHOT":
            raise BindingError("target_specific_approval_required")
        # Keep future unpinned targets in fail-closed state.
        if expected["recipient_sha256"] is None:
            raise BindingError("recovery_recipient_not_pinned_for_target")


def main() -> int:
    if len(sys.argv) != 4:
        print("BACKUP_BINDING_ABORT=usage", file=sys.stderr)
        return 64
    target, mode, remote = sys.argv[1:]
    try:
        validate_binding(
            target=target,
            mode=mode,
            service_id=os.environ.get("SOURCE_EXPECTED_SERVICE_ID", ""),
            remote=remote,
            folder_id=os.environ.get("DRIVE_EXPECTED_FOLDER_ID", ""),
            recipient_hash=os.environ.get("AGE_EXPECTED_RECIPIENT_SHA256", ""),
            target_approval=os.environ.get("BACKUP_EXECUTE_TARGET_APPROVED", ""),
        )
    except BindingError as exc:
        print(f"BACKUP_BINDING_ABORT={exc}", file=sys.stderr)
        return 78
    print(f"BACKUP_BINDING=PASS_STATIC target:{target} mode:{mode}")
    print("BACKUP_BINDING_LIVE_DB_IDENTITY=NOT_VERIFIED")
    print("BACKUP_BINDING_DRIVE_OWNER=NOT_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
