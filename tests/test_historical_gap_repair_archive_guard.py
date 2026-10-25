from __future__ import annotations

import pytest

import run_historical_month_gap_repair_pg as mod


def configure(monkeypatch, *, enabled: bool, role: str, archive_active: bool = False, nonprod: bool = False):
    monkeypatch.setattr(mod, "EXPLICIT_ENABLE", enabled)
    monkeypatch.setattr(mod, "SOURCE_ROLE", role)
    monkeypatch.setattr(mod, "ARCHIVE_ACTIVE", archive_active)
    monkeypatch.setattr(mod, "NONPROD_ASSERT", nonprod)


def test_default_disabled_fails_closed(monkeypatch):
    configure(monkeypatch, enabled=False, role="disabled")
    with pytest.raises(RuntimeError, match="HISTORICAL_GAP_REPAIR_ENABLE=1"):
        mod.require_safe_source_role()


def test_prearchive_full_history_allowed_only_before_archive(monkeypatch):
    configure(monkeypatch, enabled=True, role="prearchive_production_full_history", archive_active=False)
    mod.require_safe_source_role()

    configure(monkeypatch, enabled=True, role="prearchive_production_full_history", archive_active=True)
    with pytest.raises(RuntimeError, match="archive is active"):
        mod.require_safe_source_role()


def test_restored_nonproduction_requires_explicit_assert(monkeypatch):
    configure(monkeypatch, enabled=True, role="restored_nonproduction_full_history", nonprod=False)
    with pytest.raises(RuntimeError, match="NONPROD_ASSERT=1"):
        mod.require_safe_source_role()

    configure(monkeypatch, enabled=True, role="restored_nonproduction_full_history", nonprod=True)
    mod.require_safe_source_role()


def test_unknown_role_fails_closed(monkeypatch):
    configure(monkeypatch, enabled=True, role="archive_or_online_unspecified")
    with pytest.raises(RuntimeError, match="refusing ambiguous historical repair"):
        mod.require_safe_source_role()


def test_main_guard_runs_before_any_historical_db_audit(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    configure(monkeypatch, enabled=True, role="prearchive_production_full_history", archive_active=True)

    def must_not_query(*args, **kwargs):
        raise AssertionError("historical DB audit must not run after archive cutover")

    monkeypatch.setattr(mod, "audit", must_not_query)
    monkeypatch.setattr(mod, "targets", must_not_query)

    with pytest.raises(RuntimeError, match="archive is active"):
        mod.main()
