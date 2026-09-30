# -*- coding: utf-8 -*-
import pytest

from research.teikoku_motor_batch_crosscheck_pg import (
    MAX_MOTORS,
    MIN_ACCESS_INTERVAL_SEC,
    _motor_int,
    _pid,
)


def test_access_interval_respects_published_minimum():
    assert MIN_ACCESS_INTERVAL_SEC >= 3.0


def test_limit_is_bounded_for_polite_batching():
    assert MAX_MOTORS <= 24


def test_pid_normalization_is_only_boatrace_venues():
    assert _pid("1") == "01"
    assert _pid("24") == "24"
    assert _pid("25") is None
    assert _pid("") is None


def test_motor_normalization():
    assert _motor_int("60") == 60
    assert _motor_int("motor 7") == 7
    assert _motor_int("") is None
    assert _motor_int("0") is None
