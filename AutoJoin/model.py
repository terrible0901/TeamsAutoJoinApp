from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

JST = timezone(timedelta(hours=9))
METHODS = {"id", "link", "calendar"}


def now_jst() -> datetime:
    return datetime.now(JST).replace(tzinfo=None)


@dataclass(frozen=True)
class Meeting:
    id: str
    series_id: str
    title: str
    start: datetime
    end: datetime
    method: str
    meeting_id: str = ""
    secret: str = ""
    status: str = "pending"

    @staticmethod
    def create(title: str, start: datetime, end: datetime, method: str,
               meeting_id: str = "", secret: str = "", series_id: str = "") -> Meeting:
        return Meeting(uuid4().hex, series_id, title.strip(), start, end,
                       method, meeting_id.strip(), secret.strip())


def validate_meeting(meeting: Meeting) -> None:
    if not meeting.title:
        raise ValueError("会議名を入力してください。")
    if meeting.end <= meeting.start:
        raise ValueError("終了予定は開始より後にしてください。")
    if meeting.method not in METHODS:
        raise ValueError("参加方式を選択してください。")
    if meeting.method == "id" and (not meeting.meeting_id or not meeting.secret):
        raise ValueError("会議IDとパスワードを入力してください。")
    if meeting.method == "link":
        from urllib.parse import urlparse
        url = urlparse(meeting.secret)
        if url.scheme != "https" or url.hostname != "teams.microsoft.com" or not url.path.startswith("/l/meetup-join/"):
            raise ValueError("Teamsの会議参加リンクを入力してください。")


def validate_schedule(meetings: list[Meeting]) -> None:
    ordered = sorted(meetings, key=lambda m: m.start)
    for meeting in ordered:
        validate_meeting(meeting)
    for previous, following in zip(ordered, ordered[1:]):
        if following.start - previous.end < timedelta(minutes=10):
            raise ValueError(f"「{previous.title}」と「{following.title}」の間隔を10分以上にしてください。")


def weekly_occurrences(template: Meeting, through: datetime) -> list[Meeting]:
    if through.date() < template.start.date():
        raise ValueError("繰り返し終了日は開始日以降にしてください。")
    if through.date() > (template.start + timedelta(weeks=520)).date():
        raise ValueError("繰り返し期間は10年以内にしてください。")
    group = template.series_id or uuid4().hex
    output: list[Meeting] = []
    current = template
    while current.start.date() <= through.date():
        output.append(replace(current, id=uuid4().hex, series_id=group))
        current = replace(current, start=current.start + timedelta(days=7), end=current.end + timedelta(days=7))
    return output
