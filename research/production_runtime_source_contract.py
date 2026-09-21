# -*- coding: utf-8 -*-
"""Pure contract for Production runtime-source inventory audits.

This module intentionally has no DB, network, Railway, GitHub, subprocess, file-write,
or environment access.  A caller supplies an already-observed inventory snapshot and
this module classifies whether that snapshot is complete enough to support a future
zero-consumer review.

It does not authorize Production mutation.  In particular, PASS here is only a
structural inventory result; archive durability, restore, retained-set sizing,
headroom, and explicit approval remain separate gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


DESTRUCTIVE_INLINE_MARKERS = (
    "drop index",
    "drop table",
    "truncate ",
    "delete from ",
    "alter table",
    "vacuum full",
)

CANDIDATE_SHADOW_WRITER_CAPABILITY = "candidate_shadow_writer"
CANDIDATE_SHADOW_READER_CAPABILITY = "candidate_shadow_reader"


@dataclass(frozen=True)
class Surface:
    name: str
    source_repo: str = ""
    source_branch: str = ""
    source_image: str = ""
    start_command: str = ""
    cron_schedule: str = ""
    replicas: int = 0
    capabilities: tuple[str, ...] = ()
    observed_effects: tuple[str, ...] = ()

    @property
    def source_kind(self) -> str:
        if self.source_repo:
            return "repo"
        if self.source_image:
            return "image"
        return "unknown"

    @property
    def is_executable_surface(self) -> bool:
        return bool(self.start_command.strip())

    @property
    def is_no_cron_executable_surface(self) -> bool:
        return self.is_executable_surface and not self.cron_schedule.strip()

    @property
    def is_resolved(self) -> bool:
        if not self.name.strip():
            return False
        if self.source_kind == "repo":
            return bool(self.source_branch.strip() and self.start_command.strip())
        if self.source_kind == "image":
            # Image-backed services with an empty start command are intentionally
            # unresolved: an auditor must not infer harmlessness from the name.
            return bool(self.start_command.strip())
        return False

    @property
    def has_destructive_inline_command(self) -> bool:
        text = self.start_command.lower()
        return any(marker in text for marker in DESTRUCTIVE_INLINE_MARKERS)

    @property
    def writes_candidate_shadow(self) -> bool:
        return CANDIDATE_SHADOW_WRITER_CAPABILITY in self.capabilities

    @property
    def reads_candidate_shadow(self) -> bool:
        return CANDIDATE_SHADOW_READER_CAPABILITY in self.capabilities


@dataclass(frozen=True)
class InventoryReport:
    observed_services: tuple[str, ...]
    missing_required_services: tuple[str, ...]
    duplicate_services: tuple[str, ...]
    unresolved_services: tuple[str, ...]
    non_main_repo_sources: tuple[str, ...]
    no_cron_executable_surfaces: tuple[str, ...]
    destructive_inline_surfaces: tuple[str, ...]
    candidate_shadow_writer_surfaces: tuple[str, ...]
    candidate_shadow_reader_surfaces: tuple[str, ...]
    runtime_inventory_gate: str
    candidate_shadow_zero_consumer_gate: str

    @property
    def runtime_inventory_passed(self) -> bool:
        return self.runtime_inventory_gate == "PASS"

    @property
    def candidate_shadow_zero_consumer_passed(self) -> bool:
        return self.candidate_shadow_zero_consumer_gate == "PASS"


def _tuple_of_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(item) for item in value if str(item))


def surface_from_mapping(row: Mapping[str, Any]) -> Surface:
    replicas_raw = row.get("replicas", 0)
    try:
        replicas = int(replicas_raw or 0)
    except (TypeError, ValueError):
        replicas = 0
    return Surface(
        name=str(row.get("name") or ""),
        source_repo=str(row.get("source_repo") or ""),
        source_branch=str(row.get("source_branch") or ""),
        source_image=str(row.get("source_image") or ""),
        start_command=str(row.get("start_command") or ""),
        cron_schedule=str(row.get("cron_schedule") or ""),
        replicas=replicas,
        capabilities=_tuple_of_strings(row.get("capabilities")),
        observed_effects=_tuple_of_strings(row.get("observed_effects")),
    )


def audit_runtime_inventory(
    surfaces: Iterable[Surface | Mapping[str, Any]],
    *,
    required_services: Sequence[str],
) -> InventoryReport:
    """Classify one already-observed Production runtime snapshot.

    Fail-closed rules:
    - every required service must appear exactly once;
    - repo-backed services require an explicit branch and start command;
    - image-backed services require an explicit start command;
    - a destructive inline command blocks the runtime-inventory gate;
    - any candidate-shadow writer or reader blocks candidate-shadow zero-consumer proof;
    - non-main branches are surfaced explicitly, not treated as an error by
      themselves, because they must be scanned as part of the final proof.
    """
    normalized = [
        item if isinstance(item, Surface) else surface_from_mapping(item)
        for item in surfaces
    ]

    names = [item.name for item in normalized]
    required = tuple(dict.fromkeys(str(name) for name in required_services))
    missing = sorted(name for name in required if names.count(name) == 0)
    duplicates = sorted({name for name in names if name and names.count(name) > 1})
    unresolved = sorted(item.name or "<unnamed>" for item in normalized if not item.is_resolved)
    non_main = sorted(
        item.name
        for item in normalized
        if item.source_kind == "repo" and item.source_branch.strip() != "main"
    )
    no_cron = sorted(item.name for item in normalized if item.is_no_cron_executable_surface)
    destructive = sorted(item.name for item in normalized if item.has_destructive_inline_command)
    candidate_writers = sorted(item.name for item in normalized if item.writes_candidate_shadow)
    candidate_readers = sorted(item.name for item in normalized if item.reads_candidate_shadow)

    runtime_blockers = bool(missing or duplicates or unresolved or destructive)
    candidate_blockers = bool(runtime_blockers or candidate_writers or candidate_readers)

    return InventoryReport(
        observed_services=tuple(sorted(name for name in names if name)),
        missing_required_services=tuple(missing),
        duplicate_services=tuple(duplicates),
        unresolved_services=tuple(unresolved),
        non_main_repo_sources=tuple(non_main),
        no_cron_executable_surfaces=tuple(no_cron),
        destructive_inline_surfaces=tuple(destructive),
        candidate_shadow_writer_surfaces=tuple(candidate_writers),
        candidate_shadow_reader_surfaces=tuple(candidate_readers),
        runtime_inventory_gate="BLOCK" if runtime_blockers else "PASS",
        candidate_shadow_zero_consumer_gate="BLOCK" if candidate_blockers else "PASS",
    )
