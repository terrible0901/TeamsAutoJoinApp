from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from AutoJoin.bootstrap import init_deps

init_deps()

from AutoJoin.engine import ExitRule
from AutoJoin.model import Meeting, validate_schedule, weekly_occurrences
from AutoJoin.storage import Storage


class ScheduleTests(unittest.TestCase):
    def meeting(self, start: datetime, end: datetime) -> Meeting:
        return Meeting.create("会議", start, end, "id", "123456", "private-pass")

    def test_gap_boundary_and_overlap(self):
        first = self.meeting(datetime(2026, 10, 1, 9), datetime(2026, 10, 1, 10))
        exact = self.meeting(datetime(2026, 10, 1, 10, 10), datetime(2026, 10, 1, 11))
        validate_schedule([first, exact])
        too_close = self.meeting(datetime(2026, 10, 1, 10, 9), datetime(2026, 10, 1, 11))
        with self.assertRaises(ValueError):
            validate_schedule([first, too_close])

    def test_weekly_expansion_and_gap(self):
        base = self.meeting(datetime(2026, 10, 1, 9), datetime(2026, 10, 1, 10))
        series = weekly_occurrences(base, datetime(2026, 10, 15))
        self.assertEqual(len(series), 3)
        self.assertEqual(len({m.series_id for m in series}), 1)
        self.assertEqual(len({m.id for m in series}), 3)
        validate_schedule(series)

    def test_password_is_encrypted_on_disk_and_not_logged(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(Path(folder))
            meeting = self.meeting(datetime(2026, 10, 1, 9), datetime(2026, 10, 1, 10))
            store.replace_meetings([meeting])
            raw = store.plan_file.read_text(encoding="utf-8")
            self.assertNotIn("private-pass", raw)
            self.assertEqual(Storage(Path(folder)).meetings[0].secret, "private-pass")
            store.record("joined")
            self.assertNotIn("private-pass", store.log_file.read_text(encoding="utf-8"))


class ExitRuleTests(unittest.TestCase):
    def test_strict_quarter_and_tenth(self):
        rule = ExitRule()
        self.assertIsNone(rule.sample(20, 0))
        self.assertIsNone(rule.sample(5, 10))  # quarter exactly
        self.assertIsNone(rule.sample(4, 20))
        self.assertIsNone(rule.sample(2, 30))  # tenth exactly, wait persists
        self.assertEqual(rule.sample(2, 50), "leave")
        fresh = ExitRule()
        fresh.sample(20, 0)
        self.assertEqual(fresh.sample(1, 10), "leave_fast")

    def test_missing_count_resets_timer_and_warns_once(self):
        rule = ExitRule()
        rule.sample(20, 0)
        rule.sample(4, 10)
        self.assertIsNone(rule.sample(None, 20))
        self.assertEqual(rule.sample(None, 80), "count_unavailable")
        self.assertIsNone(rule.sample(None, 90))
        self.assertIsNone(rule.sample(4, 100))
        self.assertEqual(rule.sample(4, 130), "leave")


if __name__ == "__main__":
    unittest.main()
