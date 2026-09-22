# -*- coding: utf-8 -*-
import importlib
import os
import sys
import types

from line_buy_notification_layout import (
    group_notification_decisions,
    point_label,
    select_notification_decisions,
)


def row(race_id, ticket, score):
    venue_id = race_id.split("_")[1]
    race_no = int(race_id.split("_")[2])
    return {
        "id": f"{race_id}:{ticket}",
        "race_id": race_id,
        "venue_id": venue_id,
        "race_no": race_no,
        "ticket": ticket,
        "odds": 4.2,
        "final_score": score,
        "realtime_score": score,
        "mode_name": "test-mode",
        "positive_reasons": ["test"],
        "negative_reasons": [],
        "raw": {"candidate": {"race_title": "fixture"}},
    }


def test_same_race_is_capped_at_two_existing_buy_points():
    rows = [
        row("20260923_02_08", "1-2-3", 10),
        row("20260923_02_08", "1-3-2", 9),
        row("20260923_02_08", "1-2-4", 8),
    ]
    selected, metrics = select_notification_decisions(
        rows,
        sent_keys=set(),
        notified_tickets_by_race={},
        max_send=10,
    )
    assert [r["ticket"] for r in selected] == ["1-2-3", "1-3-2"]
    assert [r["_line_point_order"] for r in selected] == [1, 2]
    assert metrics["extra_point_skipped"] == 1


def test_existing_main_makes_later_second_buy_the_cover_point():
    rows = [
        row("20260923_02_08", "1-3-2", 9),
        row("20260923_02_08", "1-2-4", 8),
    ]
    selected, metrics = select_notification_decisions(
        rows,
        sent_keys=set(),
        notified_tickets_by_race={
            "20260923_02_08": {"1-2-3"},
        },
        max_send=10,
    )
    assert [r["ticket"] for r in selected] == ["1-3-2"]
    assert selected[0]["_line_point_order"] == 2
    assert metrics["extra_point_skipped"] == 1


def test_duplicate_ticket_across_modes_does_not_consume_cover_slot():
    rows = [
        row("20260923_02_08", "1-2-3", 10),
        row("20260923_02_08", "1-2-3", 9.5),
        row("20260923_02_08", "1-3-2", 9),
    ]
    selected, metrics = select_notification_decisions(
        rows,
        sent_keys=set(),
        notified_tickets_by_race={},
        max_send=10,
    )
    assert [r["ticket"] for r in selected] == ["1-2-3", "1-3-2"]
    assert metrics["duplicate_pending_skipped"] == 1


def test_sent_key_and_global_limit_remain_fail_closed():
    rows = [
        row("20260923_02_08", "1-2-3", 10),
        row("20260923_02_08", "1-3-2", 9),
        row("20260923_17_04", "2-3-1", 8),
    ]
    selected, metrics = select_notification_decisions(
        rows,
        sent_keys={"20260923_02_08|1-2-3"},
        notified_tickets_by_race={},
        max_send=2,
    )
    assert [r["ticket"] for r in selected] == ["1-3-2", "2-3-1"]
    assert metrics["sent_key_skipped"] == 1


def test_grouping_and_labels_preserve_main_cover_order():
    decisions = [
        {**row("20260923_02_08", "1-3-2", 9), "_line_point_order": 2},
        {**row("20260923_17_04", "2-3-1", 8), "_line_point_order": 1},
        {**row("20260923_02_08", "1-2-3", 10), "_line_point_order": 1},
    ]
    groups = group_notification_decisions(decisions)
    assert [r["ticket"] for r in groups[0]] == ["1-2-3", "1-3-2"]
    assert point_label(groups[0][0]["_line_point_order"]) == "本線"
    assert point_label(groups[0][1]["_line_point_order"]) == "押さえ"


def _load_notifier_for_format_test(monkeypatch):
    fake_db = types.ModuleType("db_pg")
    fake_db.execute = lambda *args, **kwargs: None
    fake_db.fetch_all = lambda *args, **kwargs: []
    fake_db.fetch_one = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "db_pg", fake_db)

    fake_requests = types.ModuleType("requests")
    fake_requests.post = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    monkeypatch.setenv("DRY_RUN", "1")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("TARGET_DATE", "2026-09-23")
    sys.modules.pop("v23_line_notifier_batch_pg", None)
    return importlib.import_module("v23_line_notifier_batch_pg")


def test_batch_message_shows_main_and_cover(monkeypatch):
    notifier = _load_notifier_for_format_test(monkeypatch)
    decisions = [
        {**row("20260923_02_08", "1-2-3", 10), "_line_point_order": 1},
        {**row("20260923_02_08", "1-3-2", 9), "_line_point_order": 2},
    ]
    message = notifier.build_batch_message(decisions)
    assert "本線: 1-2-3" in message
    assert "押さえ: 1-3-2" in message
    assert "対象: 1レース / 2点" in message
    assert "BUY条件未満の買い目は追加しません" in message


def test_batch_send_marks_only_points_actually_visible(monkeypatch):
    notifier = _load_notifier_for_format_test(monkeypatch)
    monkeypatch.setattr(notifier, "BATCH_NOTIFY", True)
    monkeypatch.setattr(notifier, "MAX_ITEMS_PER_MESSAGE", 1)
    monkeypatch.setattr(notifier, "DRY_RUN", False)
    monkeypatch.setattr(notifier, "_require_settings", lambda: None)
    monkeypatch.setattr(notifier, "_ensure_schema", lambda: None)
    monkeypatch.setattr(notifier, "_usage_guard", lambda: None)

    decisions = [
        {**row("20260923_02_08", "1-2-3", 10), "_line_point_order": 1},
        {**row("20260923_02_08", "1-3-2", 9), "_line_point_order": 2},
        {**row("20260923_17_04", "2-3-1", 8), "_line_point_order": 1},
    ]
    monkeypatch.setattr(notifier, "fetch_buy_decisions", lambda: decisions)
    monkeypatch.setattr(
        notifier,
        "send_line_message",
        lambda text: {"status_code": 200, "body": "ok", "dry_run": False},
    )
    monkeypatch.setattr(notifier, "insert_notification", lambda *args, **kwargs: "n1")
    marked = []
    monkeypatch.setattr(
        notifier,
        "mark_decision_notified",
        lambda decision_id, notification_id: marked.append(
            (decision_id, notification_id)
        ),
    )

    notifier.main()

    assert marked == [
        ("20260923_02_08:1-2-3", "n1"),
        ("20260923_02_08:1-3-2", "n1"),
    ]


def test_batch_message_does_not_invent_cover_when_only_one_buy(monkeypatch):
    notifier = _load_notifier_for_format_test(monkeypatch)
    decisions = [
        {**row("20260923_02_08", "1-2-3", 10), "_line_point_order": 1},
    ]
    message = notifier.build_batch_message(decisions)
    assert "本線: 1-2-3" in message
    assert "押さえ: BUY条件該当なし" in message
