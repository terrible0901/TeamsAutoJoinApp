from __future__ import annotations

import queue
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from AutoJoin.bootstrap import init_deps

init_deps()

from AutoJoin.engine import Engine, ExitRule
from AutoJoin.model import Meeting, validate_meeting, validate_schedule, weekly_occurrences
from AutoJoin.storage import Storage


class FakeTeams:
    def __init__(self, in_meeting: bool = False):
        self.in_meeting = in_meeting
        self.join_calls = 0

    def any_meeting(self) -> bool:
        return self.in_meeting

    def begin_join(self, meeting: Meeting) -> None:
        self.join_calls += 1


class FakeStorage:
    def __init__(self, meetings: list[Meeting]):
        self.meetings = meetings
        self.history: list[str] = []

    def record(self, event: str) -> None:
        self.history.append(event)


class RequirementTests(unittest.TestCase):
    def meeting(self, start: datetime, end: datetime | None = None, method: str = "id") -> Meeting:
        return Meeting.create("テスト会議", start, end or start + timedelta(hours=1),
                              method, "123456" if method == "id" else "",
                              "test-pass" if method == "id" else "")

    def test_required_fields_and_link_origin(self):
        start = datetime(2026, 10, 1, 9)
        invalid = [
            Meeting.create("", start, start + timedelta(hours=1), "calendar"),
            self.meeting(start, start),
            Meeting.create("会議", start, start + timedelta(hours=1), "id", "123", ""),
            Meeting.create("会議", start, start + timedelta(hours=1), "link",
                           secret="https://example.com/l/meetup-join/123"),
        ]
        for meeting in invalid:
            with self.subTest(meeting=meeting):
                with self.assertRaises(ValueError):
                    validate_meeting(meeting)
        validate_meeting(Meeting.create("会議", start, start + timedelta(hours=1),
                                        "link", secret="https://teams.microsoft.com/l/meetup-join/123"))

    def test_weekly_occurrence_gap_is_checked(self):
        first = self.meeting(datetime(2026, 10, 1, 9))
        recurring = weekly_occurrences(first, datetime(2026, 10, 15))
        conflict = self.meeting(datetime(2026, 10, 8, 10, 9))
        with self.assertRaises(ValueError):
            validate_schedule(recurring + [conflict])

    def test_exit_rule_all_documented_boundaries(self):
        for maximum, count, expected in [
            (20, 5, None), (20, 4, None), (20, 2, None),
            (20, 1, "leave_fast"), (3, 0, "leave_fast"), (0, 0, None),
        ]:
            with self.subTest(maximum=maximum, count=count):
                rule = ExitRule()
                rule.sample(maximum, 0)
                self.assertEqual(rule.sample(count, 10), expected)
        rule = ExitRule()
        rule.sample(20, 0)
        rule.sample(2, 10)
        self.assertEqual(rule.sample(2, 40), "leave")

    def test_history_prunes_entries_older_than_30_days(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            old = (datetime.now() - timedelta(days=31)).isoformat(timespec="seconds")
            recent = datetime.now().isoformat(timespec="seconds")
            (base / "history.json").write_text(
                '[{"at":"' + old + '","event":"old"},{"at":"' + recent + '","event":"recent"}]',
                encoding="utf-8")
            storage = Storage(base)
            self.assertEqual([item["event"] for item in storage.history], ["recent"])


class SchedulerTests(unittest.TestCase):
    NOW = datetime(2026, 10, 1, 9)

    def meeting(self, start: datetime, end: datetime | None = None) -> Meeting:
        return Meeting.create("予定", start, end or start + timedelta(hours=1),
                              "id", "123456", "test-pass")

    def make_engine(self, meetings: list[Meeting], in_meeting: bool = False):
        storage = FakeStorage(meetings)
        teams = FakeTeams(in_meeting)
        events = queue.Queue()
        engine = Engine(storage, events, teams, clock=lambda: self.NOW)
        return engine, storage, teams

    def test_start_paused_and_no_catch_up_after_enable(self):
        past = self.meeting(self.NOW - timedelta(seconds=5))
        engine, storage, teams = self.make_engine([past])
        self.assertFalse(engine.enabled)
        engine.set_enabled(True)
        with patch("AutoJoin.engine.desktop_unlocked", return_value=True):
            engine.tick()
        self.assertEqual(teams.join_calls, 0)
        self.assertNotIn("joining", storage.history)

    def test_more_than_ten_seconds_late_is_skipped(self):
        late = self.meeting(self.NOW - timedelta(seconds=11))
        engine, storage, teams = self.make_engine([late])
        engine.enabled = True
        engine.armed_at = self.NOW - timedelta(minutes=1)
        with patch("AutoJoin.engine.desktop_unlocked", return_value=True):
            engine.tick()
        self.assertEqual(teams.join_calls, 0)
        self.assertEqual(storage.history, ["late"])

    def test_end_notification_once_and_only_while_in_meeting(self):
        current = self.meeting(self.NOW - timedelta(minutes=20), self.NOW + timedelta(minutes=10))
        engine, storage, teams = self.make_engine([current], in_meeting=True)
        engine.active = current
        with patch("AutoJoin.engine.desktop_unlocked", return_value=True):
            engine.tick()
            engine.tick()
        self.assertEqual(storage.history, ["end_10"])
        teams.in_meeting = False
        engine.clock = lambda: self.NOW + timedelta(minutes=5)
        engine.tick()
        self.assertEqual(storage.history, ["end_10"])

    def test_overlap_notice_once(self):
        current = self.meeting(self.NOW - timedelta(minutes=20))
        following = self.meeting(self.NOW + timedelta(minutes=5))
        engine, storage, _ = self.make_engine([current, following], in_meeting=True)
        engine.active = current
        with patch("AutoJoin.engine.desktop_unlocked", return_value=True):
            engine.tick()
            engine.tick()
        self.assertEqual(storage.history, ["overlap"])


if __name__ == "__main__":
    unittest.main()
