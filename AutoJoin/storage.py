from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

from .model import Meeting, now_jst, validate_schedule


def _crypt(data: str) -> str:
    import win32crypt
    return win32crypt.CryptProtectData(data.encode("utf-8"), None, None, None, None, 0).hex()


def _decrypt(data: str) -> str:
    import win32crypt
    return win32crypt.CryptUnprotectData(bytes.fromhex(data), None, None, None, 0)[1].decode("utf-8")


class Storage:
    def __init__(self, base: Path | None = None):
        self._lock = threading.RLock()
        self.base = base or Path(os.environ["LOCALAPPDATA"]) / "TeamsAutoJoin"
        self.base.mkdir(parents=True, exist_ok=True)
        self.plan_file = self.base / "meetings.json"
        self.log_file = self.base / "history.json"
        self.meetings = self._load_meetings()
        self.history = self._load_history()
        before = len(self.history)
        self._prune_history()
        if len(self.history) != before:
            self._write_atomic(self.log_file, self.history)

    def _load_meetings(self) -> list[Meeting]:
        if not self.plan_file.exists():
            return []
        data = json.loads(self.plan_file.read_text(encoding="utf-8"))
        output = []
        for item in data:
            item = dict(item)
            item["start"] = datetime.fromisoformat(item["start"])
            item["end"] = datetime.fromisoformat(item["end"])
            encrypted = item.pop("secret_dpapi", "")
            item["secret"] = _decrypt(encrypted) if encrypted else ""
            output.append(Meeting(**item))
        return output

    def _load_history(self) -> list[dict]:
        if not self.log_file.exists():
            return []
        return json.loads(self.log_file.read_text(encoding="utf-8"))

    def _write_atomic(self, target: Path, data: object) -> None:
        fd, temp_name = tempfile.mkstemp(prefix="autojoin-", suffix=".tmp", dir=self.base)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def replace_meetings(self, meetings: list[Meeting]) -> None:
        with self._lock:
            validate_schedule(meetings)
            saved = []
            for m in meetings:
                saved.append({
                    "id": m.id, "series_id": m.series_id, "title": m.title,
                    "start": m.start.isoformat(), "end": m.end.isoformat(),
                    "method": m.method, "meeting_id": m.meeting_id,
                    "secret_dpapi": _crypt(m.secret) if m.secret else "",
                    "status": m.status,
                })
            self._write_atomic(self.plan_file, saved)
            self.meetings = meetings

    def record(self, event: str) -> None:
        # History intentionally keeps event codes only: no secrets, links,
        # meeting names, or chat text can be written by a caller.
        with self._lock:
            entry = {"at": now_jst().isoformat(timespec="seconds"), "event": event}
            self.history.append(entry)
            self._prune_history()
            self._write_atomic(self.log_file, self.history)

    def _prune_history(self) -> None:
        boundary = now_jst() - timedelta(days=30)
        self.history = [row for row in self.history if datetime.fromisoformat(row["at"]) >= boundary]
