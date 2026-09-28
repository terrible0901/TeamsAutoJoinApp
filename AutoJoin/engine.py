from __future__ import annotations

import queue
import threading
import time
from datetime import datetime, timedelta

from .model import Meeting, now_jst
from .storage import Storage
from .system_state import desktop_unlocked
from .teams import TeamsAdapter, TeamsError


class ExitRule:
    def __init__(self):
        self.maximum = 0
        self.below_since: float | None = None
        self.missing_since: float | None = None
        self.missing_notified = False

    def sample(self, count: int | None, at: float) -> str | None:
        if count is None:
            self.below_since = None
            self.missing_since = self.missing_since or at
            if at - self.missing_since >= 60 and not self.missing_notified:
                self.missing_notified = True
                return "count_unavailable"
            return None
        self.missing_since = None
        self.missing_notified = False
        self.maximum = max(self.maximum, count)
        if self.maximum == 0:
            self.below_since = None
            return None
        if 10 * count < self.maximum:
            return "leave_fast"
        if 4 * count < self.maximum:
            self.below_since = self.below_since if self.below_since is not None else at
            if at - self.below_since >= 30:
                return "leave"
        else:
            self.below_since = None
        return None


class Engine:
    def __init__(self, storage: Storage, events: queue.Queue,
                 teams: TeamsAdapter | None = None, clock=now_jst):
        self.storage = storage
        self.events = events
        self.teams = teams or TeamsAdapter()
        self.clock = clock
        self.enabled = False
        self.armed_at = self.clock()
        self.active: Meeting | None = None
        self.joining: Meeting | None = None
        self.rule = ExitRule()
        self.last_sample = 0.0
        self.fired: set[tuple[str, str]] = set()
        self.processed: set[str] = set()
        self.running = True
        self.last_tick_wall = self.clock()
        self.io_lock = threading.RLock()
        self.state_lock = threading.RLock()
        self.thread = threading.Thread(target=self._run, name="scheduler", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join(timeout=2)

    def set_enabled(self, enabled: bool):
        with self.state_lock:
            self.enabled = enabled
            if enabled:
                self.armed_at = self.clock()
            self.events.put(("state", "自動運転中" if enabled else "一時停止中"))

    def _record(self, event: str, meeting: Meeting | None, detail: str = ""):
        # History is intentionally metadata-only: user-entered names, links,
        # passwords and chat content must never reach a log file.
        self.storage.record(event)
        self.events.put(("history", None))

    def _notify(self, event: str, meeting: Meeting | None, message: str):
        self._record(event, meeting, message)
        self.events.put(("notify", message))

    def _once(self, key: str, meeting: Meeting, message: str):
        marker = (meeting.id, key)
        if marker not in self.fired:
            self.fired.add(marker)
            self._notify(key, meeting, message)

    def _run(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            while self.running:
                try:
                    self.tick()
                except Exception:
                    # Never leak URLs, passcodes or chat text through error logging.
                    self._notify("internal_error", None, "内部処理に失敗しました。自動運転を停止します。")
                    with self.state_lock:
                        self.enabled = False
                time.sleep(0.5)
        finally:
            pythoncom.CoUninitialize()

    def tick(self):
        now = self.clock()
        if (now - self.last_tick_wall).total_seconds() > 5 or not desktop_unlocked():
            with self.state_lock:
                was_enabled = self.enabled
                self.enabled = False
                self.active = None
            if was_enabled:
                self._notify("paused_after_lock", None, "ロックまたはスリープを検知したため自動運転を停止しました。")
                self.events.put(("state", "一時停止中"))
        self.last_tick_wall = now
        with self.state_lock:
            enabled = self.enabled
            active = self.active
            joining = self.joining
            armed_at = self.armed_at
        for meeting in list(self.storage.meetings):
            if active and meeting.id == active.id:
                self._ending_notifications(active, now)
                continue
            if meeting.id in self.processed or meeting.status != "pending":
                continue
            if active and now >= meeting.start - timedelta(minutes=5) and now < meeting.start:
                with self.io_lock:
                    still_meeting = self.teams.any_meeting()
                if still_meeting:
                    self._once("overlap", meeting, f"次の会議「{meeting.title}」まで5分です。現在の会議が続いています。")
            if now < meeting.start:
                continue
            self.processed.add(meeting.id)
            if not enabled or meeting.start < armed_at:
                continue
            if (now - meeting.start).total_seconds() > 10:
                self._once("late", meeting, f"「{meeting.title}」は開始処理が10秒以上遅れたためスキップしました。")
                continue
            if active or joining:
                self._once("skipped", meeting, f"「{meeting.title}」は別の会議中のためスキップしました。")
                continue
            with self.io_lock:
                if self.teams.any_meeting():
                    self._once("skipped", meeting, f"「{meeting.title}」は会議中のためスキップしました。")
                    continue
            with self.state_lock:
                self.joining = meeting
            self._record("joining", meeting, "参加を開始します。")
            threading.Thread(target=self._join_worker, args=(meeting,), daemon=True).start()
        if enabled and active and time.monotonic() - self.last_sample >= 10:
            self.last_sample = time.monotonic()
            self._sample_active(active)

    def _ending_notifications(self, meeting: Meeting, now: datetime):
        for minutes in (10, 5):
            when = meeting.end - timedelta(minutes=minutes)
            if when <= now < when + timedelta(seconds=10) and meeting.start <= now:
                with self.io_lock:
                    if self.teams.any_meeting():
                        self._once(f"end_{minutes}", meeting, f"「{meeting.title}」の終了予定まで{minutes}分です。")

    def _join_worker(self, meeting: Meeting):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            for attempt in range(3):
                try:
                    with self.io_lock:
                        self.teams.begin_join(meeting)
                    break
                except TeamsError as exc:
                    # Retry only transient interaction failures, never an ambiguous state.
                    transient = "操作できません" in str(exc) or "画面要素を取得できません" in str(exc)
                    if not transient or attempt == 2:
                        self._notify("join_failed", meeting, "参加を中止しました。Teamsの画面と履歴を確認してください。")
                        return
                    time.sleep(30)
            deadline = time.monotonic() + 600
            with self.io_lock:
                joined = self.teams.wait_joined(deadline)
            if not joined:
                self._notify("lobby_timeout", meeting, "10分以内に入室できなかったため中止しました。")
                return
            with self.state_lock:
                if not self.enabled:
                    return
                self.active = meeting
                self.rule = ExitRule()
                self.last_sample = time.monotonic()
            self._record("joined", meeting, "入室しました。")
            with self.io_lock:
                try:
                    confirmed = self.teams.send_chat("よろしくお願いします")
                except TeamsError:
                    confirmed = False
            self._record("greeting", meeting, "送信済み" if confirmed else "送信結果を確認できません。再送しません。")
        except Exception:
            self._notify("join_failed", meeting, "参加処理に失敗しました。")
        finally:
            with self.state_lock:
                self.joining = None
            pythoncom.CoUninitialize()

    def _sample_active(self, meeting: Meeting):
        with self.io_lock:
            try:
                if not self.teams.any_meeting():
                    if self.teams.app_available():
                        self._record("manual_left", meeting)
                        with self.state_lock:
                            self.active = None
                        return
                    self._notify("disconnected", meeting, "会議への接続が切れました。自動運転を停止します。")
                    with self.state_lock:
                        self.active = None
                        self.enabled = False
                    return
                count = self.teams.participant_count()
            except TeamsError:
                count = None
        result = self.rule.sample(count, time.monotonic())
        if result == "count_unavailable":
            self._once("count_unavailable", meeting, "参加者数を60秒間取得できません。確認を続けます。")
        elif result in {"leave", "leave_fast"}:
            self._leave_active(meeting)

    def _leave_active(self, meeting: Meeting):
        with self.io_lock:
            try:
                confirmed = self.teams.send_chat("ありがとうございました")
            except TeamsError:
                confirmed = False
            self._record("farewell", meeting, "送信済み" if confirmed else "送信結果を確認できません。再送しません。")
            for attempt in range(3):
                try:
                    if self.teams.leave():
                        self._record("left", meeting, "人数条件で退出しました。")
                        with self.state_lock:
                            self.active = None
                        return
                    if attempt < 2 and not self.teams.any_meeting():
                        break
                except TeamsError:
                    break
            self._notify("leave_failed", meeting, "退出を確認できません。自動操作を停止します。")
            with self.state_lock:
                self.enabled = False
