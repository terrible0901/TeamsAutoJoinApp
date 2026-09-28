"""Fail-closed UI Automation adapter for Japanese Teams desktop.

Selectors use accessibility names and control types, never screen coordinates.
Microsoft changes Teams UI frequently; unknown/ambiguous UI raises TeamsError.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
import time
from urllib.parse import urlparse

from .model import Meeting


class TeamsError(RuntimeError):
    pass


class TeamsAdapter:
    def __init__(self):
        try:
            from pywinauto import Desktop
        except ImportError as exc:
            raise TeamsError("pywinautoが必要です。依存関係をインストールしてください。") from exc
        self.desktop = Desktop(backend="uia")

    @staticmethod
    def _is_teams_process(pid: int) -> bool:
        access = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                        wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            return False
        try:
            size = wintypes.DWORD(32768)
            path = ctypes.create_unicode_buffer(size.value)
            result = kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size))
            return bool(result) and os.path.basename(path.value).lower() == "ms-teams.exe"
        finally:
            kernel32.CloseHandle(handle)

    def _windows(self):
        output = []
        for window in self.desktop.windows():
            try:
                if window.is_visible() and self._is_teams_process(window.element_info.process_id):
                    output.append(window)
            except Exception:
                continue
        return output

    @staticmethod
    def _nodes(root, control_type: str | None = None):
        try:
            nodes = root.descendants()
        except Exception as exc:
            raise TeamsError("Teamsの画面要素を取得できません。") from exc
        if control_type:
            return [n for n in nodes if n.element_info.control_type == control_type]
        return nodes

    @staticmethod
    def _name(node) -> str:
        try:
            return node.window_text().strip()
        except Exception:
            return ""

    def _main_window(self):
        candidates = self._windows()
        if not candidates:
            raise TeamsError("Teamsデスクトップアプリの画面が見つかりません。")
        # Main window has the calendar/navigation button; never guess by position.
        matches = [w for w in candidates if any(re.search(r"^(カレンダー|予定表|Calendar)$", self._name(n), re.I)
                      for n in self._nodes(w, "Button"))]
        if len(matches) != 1:
            raise TeamsError("Teamsのメイン画面を一意に特定できません。")
        return matches[0]

    def _meeting_window(self):
        matches = []
        for window in self._windows():
            names = [self._name(n) for n in self._nodes(window, "Button")]
            if any(re.search(r"^(退出|Leave|会議から退出)$", name, re.I) for name in names):
                matches.append(window)
        if len(matches) > 1:
            raise TeamsError("参加中の会議画面を一意に特定できません。")
        return matches[0] if matches else None

    def any_meeting(self) -> bool:
        return self._meeting_window() is not None

    def app_available(self) -> bool:
        try:
            self._main_window()
            return True
        except TeamsError:
            return False

    def _one(self, root, kind: str, patterns: tuple[str, ...]):
        matches = [node for node in self._nodes(root, kind)
                   if any(re.fullmatch(pattern, self._name(node), re.I) for pattern in patterns)]
        if len(matches) != 1:
            raise TeamsError(f"Teamsの操作対象を一意に特定できません: {patterns[0]}")
        return matches[0]

    def _click(self, root, *patterns: str):
        button = self._one(root, "Button", patterns)
        try:
            root.set_focus()
            button.click_input()
        except Exception as exc:
            raise TeamsError("Teamsのボタンを操作できません。") from exc

    def _edit(self, root, patterns: tuple[str, ...], value: str):
        field = self._one(root, "Edit", patterns)
        try:
            field.set_edit_text(value)
        except Exception as exc:
            raise TeamsError("Teamsの入力欄を操作できません。") from exc

    def _open_by_id(self, meeting: Meeting):
        window = self._main_window()
        self._click(window, r"カレンダー|予定表|Calendar")
        time.sleep(0.5)
        window = self._main_window()
        self._click(window, r"ID.*参加|会議 ID.*参加|Join with.*ID")
        time.sleep(0.5)
        window = self._main_window()
        self._edit(window, (r"会議\s*ID|Meeting\s*ID",), meeting.meeting_id)
        self._edit(window, (r"パスコード|パスワード|Passcode",), meeting.secret)
        self._click(window, r"会議に参加|参加|Join meeting|Join")

    def _open_by_link(self, meeting: Meeting):
        parsed = urlparse(meeting.secret)
        if parsed.scheme != "https" or parsed.hostname != "teams.microsoft.com" or not parsed.path.startswith("/l/meetup-join/"):
            raise TeamsError("デスクトップで開けるTeamsの会議リンクではありません。")
        # Official Teams deep-link scheme opens the installed desktop client.
        os.startfile("msteams://teams.microsoft.com" + parsed.path + ("?" + parsed.query if parsed.query else ""))

    def _open_by_calendar(self, meeting: Meeting):
        window = self._main_window()
        self._click(window, r"カレンダー|予定表|Calendar")
        time.sleep(0.5)
        window = self._main_window()
        date_variants = {
            meeting.start.strftime("%Y/%m/%d"),
            meeting.start.strftime("%Y-%m-%d"),
            f"{meeting.start.year}年{meeting.start.month}月{meeting.start.day}日",
        }
        time_variants = {meeting.start.strftime("%H:%M"), f"{meeting.start.hour}:{meeting.start:%M}"}
        matches = []
        for node in self._nodes(window):
            if node.element_info.control_type not in {"ListItem", "Group"}:
                continue
            names = [self._name(n) for n in [node] + self._nodes(node)]
            text = " ".join(names)
            if meeting.title in names and any(d in text for d in date_variants) and any(t in text for t in time_variants):
                matches.append(node)
        # A Group may contain its matching ListItem; prefer the most specific item.
        matches = [n for n in matches if n.element_info.control_type == "ListItem"] or matches
        if len(matches) != 1:
            raise TeamsError("会議名と開始日時が一致する予定を一意に特定できません。")
        self._click(matches[0], r"参加|Join")

    def _prejoin(self):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            for window in self._windows():
                names = [self._name(n) for n in self._nodes(window, "Button")]
                if any(re.fullmatch(r"今すぐ参加|Join now|参加する", n, re.I) for n in names):
                    return window
            time.sleep(0.5)
        raise TeamsError("参加前の設定画面が見つかりません。")

    def _disable_device(self, window, pattern: str):
        buttons = [n for n in self._nodes(window, "Button") if re.search(pattern, self._name(n), re.I)]
        if len(buttons) != 1:
            raise TeamsError("マイクまたはカメラの設定を一意に確認できません。")
        button = buttons[0]
        try:
            toggle = button.get_toggle_state()
        except Exception as exc:
            raise TeamsError("マイクまたはカメラのオフ状態を確認できません。") from exc
        if toggle:
            button.click_input()
            time.sleep(0.2)
            if button.get_toggle_state():
                raise TeamsError("マイクまたはカメラをオフにできません。")

    def begin_join(self, meeting: Meeting):
        if self.any_meeting():
            raise TeamsError("別の会議に参加中です。")
        if meeting.method == "id":
            self._open_by_id(meeting)
        elif meeting.method == "link":
            self._open_by_link(meeting)
        else:
            self._open_by_calendar(meeting)
        prejoin = self._prejoin()
        self._disable_device(prejoin, r"マイク|Microphone")
        self._disable_device(prejoin, r"カメラ|Camera")
        self._click(prejoin, r"今すぐ参加|Join now|参加する")

    def wait_joined(self, deadline: float) -> bool:
        while time.monotonic() < deadline:
            if self._meeting_window() is not None:
                return True
            time.sleep(1)
        return False

    def send_chat(self, message: str) -> bool:
        window = self._meeting_window()
        if window is None:
            raise TeamsError("会議が終了しています。")
        self._click(window, r"チャット|Chat|会話")
        time.sleep(0.2)
        window = self._meeting_window()
        field = self._one(window, "Edit", (r"メッセージを入力.*|メッセージ.*|Type a message.*",))
        field.set_edit_text(message)
        self._click(window, r"送信|Send")
        # Teams does not expose a stable delivery acknowledgement via UIA.
        return False

    def participant_count(self) -> int:
        window = self._meeting_window()
        if window is None:
            raise TeamsError("会議が終了しています。")
        def read_counts():
            labels = [self._name(n) for n in self._nodes(window)]
            values = []
            for label in labels:
                match = re.fullmatch(r"(?:参加者|People|Participants)\s*[(（]?\s*(\d+)\s*[)）]?", label, re.I)
                if match:
                    values.append(int(match.group(1)))
            return list(set(values))

        counts = read_counts()
        if not counts:
            self._click(window, r"参加者(?:を表示)?|ユーザー|People|Show participants")
            time.sleep(0.2)
            window = self._meeting_window()
            counts = read_counts()
        if len(counts) != 1 or counts[0] < 1:
            raise TeamsError("参加者数を正確に取得できません。")
        return counts[0] - 1  # Teams displays the local user in the total.

    def leave(self) -> bool:
        window = self._meeting_window()
        if window is None:
            return True
        self._click(window, r"退出|Leave|会議から退出")
        time.sleep(0.5)
        return self._meeting_window() is None
