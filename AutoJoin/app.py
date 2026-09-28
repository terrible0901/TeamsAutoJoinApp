from __future__ import annotations

import calendar
import queue
import sys
import tkinter as tk
import winsound
from dataclasses import replace
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk

from .engine import Engine
from .model import Meeting, now_jst, weekly_occurrences
from .storage import Storage
from .teams import TeamsAdapter, TeamsError

METHOD_LABELS = {"id": "会議IDとパスワード", "link": "会議リンク", "calendar": "Teamsの参加ボタン"}
LABEL_METHODS = {label: value for value, label in METHOD_LABELS.items()}


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")


class MeetingForm(tk.Toplevel):
    def __init__(self, parent, default_start: datetime, original: Meeting | None = None,
                 weekly_end: date | None = None):
        super().__init__(parent)
        self.title("予約の編集" if original else "予約の追加")
        self.resizable(False, False)
        self.result: tuple[Meeting, date | None] | None = None
        self.original = original
        start = original.start if original else default_start
        end = original.end if original else start + timedelta(hours=1)
        self.title_value = tk.StringVar(value=original.title if original else "")
        self.start_value = tk.StringVar(value=start.strftime("%Y-%m-%d %H:%M"))
        self.end_value = tk.StringVar(value=end.strftime("%Y-%m-%d %H:%M"))
        self.method_value = tk.StringVar(value=METHOD_LABELS[original.method] if original else METHOD_LABELS["id"])
        self.meeting_id_value = tk.StringVar(value=original.meeting_id if original else "")
        self.secret_value = tk.StringVar(value=original.secret if original else "")
        self.repeat_value = tk.BooleanVar(value=bool(weekly_end))
        self.until_value = tk.StringVar(value=weekly_end.strftime("%Y-%m-%d") if weekly_end else "")
        fields = [
            ("会議名", self.title_value), ("開始（日本時間）", self.start_value),
            ("終了予定（日本時間）", self.end_value), ("会議ID", self.meeting_id_value),
            ("パスワード / 参加リンク", self.secret_value),
        ]
        main = ttk.Frame(self, padding=14)
        main.grid(sticky="nsew")
        for row, (label, variable) in enumerate(fields[:3]):
            ttk.Label(main, text=label).grid(row=row, column=0, padx=6, pady=5, sticky="w")
            ttk.Entry(main, textvariable=variable, width=36).grid(row=row, column=1, padx=6, pady=5)
        ttk.Label(main, text="参加方式").grid(row=3, column=0, padx=6, pady=5, sticky="w")
        ttk.Combobox(main, textvariable=self.method_value, values=list(METHOD_LABELS.values()),
                     state="readonly", width=33).grid(row=3, column=1, padx=6, pady=5)
        ttk.Label(main, text="参加ボタン方式では、Teamsの予定表に同名・同時刻の会議が必要です。").grid(
            row=4, column=0, columnspan=2, sticky="w", padx=6)
        for row, (label, variable) in enumerate(fields[3:], 5):
            ttk.Label(main, text=label).grid(row=row, column=0, padx=6, pady=5, sticky="w")
            ttk.Entry(main, textvariable=variable, width=36, show="*" if row == 6 else "").grid(
                row=row, column=1, padx=6, pady=5)
        ttk.Checkbutton(main, text="毎週繰り返す", variable=self.repeat_value).grid(
            row=7, column=0, padx=6, pady=5, sticky="w")
        ttk.Entry(main, textvariable=self.until_value, width=36).grid(row=7, column=1, padx=6, pady=5)
        ttk.Label(main, text="繰り返し終了日（YYYY-MM-DD）").grid(row=8, column=1, sticky="w", padx=6)
        bar = ttk.Frame(main)
        bar.grid(row=9, column=0, columnspan=2, pady=(12, 2))
        ttk.Button(bar, text="保存", command=self._save).pack(side="left", padx=8)
        ttk.Button(bar, text="キャンセル", command=self.destroy).pack(side="left", padx=8)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _save(self):
        try:
            start = _parse_date(self.start_value.get())
            end = _parse_date(self.end_value.get())
            if start <= now_jst() and not self.original:
                raise ValueError("開始日時を未来にしてください。")
            method = LABEL_METHODS[self.method_value.get()]
            secret = self.secret_value.get().strip() if method != "calendar" else ""
            meeting_id = self.meeting_id_value.get().strip() if method == "id" else ""
            template = Meeting.create(self.title_value.get(), start, end, method, meeting_id,
                                      secret, self.original.series_id if self.original else "")
            if self.original:
                template = replace(template, id=self.original.id, status=self.original.status)
            through = None
            if self.repeat_value.get():
                through = date.fromisoformat(self.until_value.get().strip())
                if through < start.date():
                    raise ValueError("繰り返し終了日は開始日以降にしてください。")
            self.result = template, through
            self.destroy()
        except ValueError as exc:
            messagebox.showerror("入力エラー", str(exc), parent=self)


class App:
    def __init__(self):
        self.storage = Storage()
        self.events: queue.Queue = queue.Queue()
        self.root = tk.Tk()
        self.root.title("Teams 自動入退室")
        self.root.minsize(900, 620)
        self.day = now_jst().date()
        self.month = self.day.replace(day=1)
        self.selected: list[Meeting] = []
        self.state_text = tk.StringVar(value="一時停止中")
        self.next_text = tk.StringVar(value="次回予約: なし")
        self._tray_added = False
        self.engine: Engine | None = None
        self._build_ui()
        self._refresh()
        self._add_tray()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(250, self._process_events)

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, textvariable=self.state_text, font=("Segoe UI", 12, "bold")).pack(side="left", padx=8)
        ttk.Button(top, text="自動運転開始", command=self._enable).pack(side="right", padx=5)
        ttk.Button(top, text="一時停止", command=self._pause).pack(side="right", padx=5)
        ttk.Label(outer, textvariable=self.next_text).pack(anchor="w", pady=(8, 8))
        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        nav = ttk.Frame(left)
        nav.pack(fill="x")
        ttk.Button(nav, text="‹", command=lambda: self._move_month(-1)).pack(side="left")
        self.month_label = ttk.Label(nav, font=("Segoe UI", 12, "bold"))
        self.month_label.pack(side="left", expand=True)
        ttk.Button(nav, text="›", command=lambda: self._move_month(1)).pack(side="right")
        self.grid_frame = ttk.Frame(left)
        self.grid_frame.pack(fill="both", expand=True, pady=8)
        right = ttk.Frame(body, width=350)
        right.pack(side="left", fill="both", padx=(15, 0))
        self.day_label = ttk.Label(right, font=("Segoe UI", 11, "bold"))
        self.day_label.pack(anchor="w")
        self.listbox = tk.Listbox(right, width=44, height=14)
        self.listbox.pack(fill="both", expand=True, pady=7)
        bar = ttk.Frame(right)
        bar.pack(fill="x")
        ttk.Button(bar, text="追加", command=self._add).pack(side="left", padx=2)
        ttk.Button(bar, text="編集", command=self._edit).pack(side="left", padx=2)
        ttk.Button(bar, text="削除", command=self._delete).pack(side="left", padx=2)
        ttk.Label(outer, text="実行履歴").pack(anchor="w", pady=(12, 2))
        self.history = tk.Text(outer, height=7, state="disabled")
        self.history.pack(fill="x")

    def _move_month(self, offset):
        year = self.month.year + (self.month.month - 1 + offset) // 12
        month = (self.month.month - 1 + offset) % 12 + 1
        self.month = date(year, month, 1)
        self._refresh()

    def _select_day(self, selected: date):
        self.day = selected
        self.month = selected.replace(day=1)
        self._refresh()

    def _refresh(self):
        self.month_label.config(text=self.month.strftime("%Y年 %m月"))
        for child in self.grid_frame.winfo_children():
            child.destroy()
        for col, name in enumerate("月火水木金土日"):
            ttk.Label(self.grid_frame, text=name, anchor="center").grid(row=0, column=col, sticky="nsew")
            self.grid_frame.columnconfigure(col, weight=1)
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self.month.year, self.month.month)
        for row, week in enumerate(weeks, 1):
            self.grid_frame.rowconfigure(row, weight=1)
            for col, day in enumerate(week):
                events = [m for m in self.storage.meetings if m.start.date() == day]
                text = str(day.day) + (f" ●{len(events)}" if events else "")
                button = ttk.Button(self.grid_frame, text=text, command=lambda value=day: self._select_day(value))
                button.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
                if day.month != self.month.month:
                    button.state(["disabled"])
        self.day_label.config(text=self.day.strftime("%Y-%m-%d の予約"))
        self.selected = sorted([m for m in self.storage.meetings if m.start.date() == self.day], key=lambda m: m.start)
        self.listbox.delete(0, "end")
        for m in self.selected:
            self.listbox.insert("end", f"{m.start:%H:%M}–{m.end:%H:%M}  {m.title}  [{METHOD_LABELS[m.method]}]")
        upcoming = sorted([m for m in self.storage.meetings if m.start >= now_jst()], key=lambda m: m.start)
        self.next_text.set("次回予約: " + (f"{upcoming[0].start:%Y-%m-%d %H:%M} {upcoming[0].title}" if upcoming else "なし"))
        self.history.config(state="normal")
        self.history.delete("1.0", "end")
        for row in self.storage.history[-50:]:
            self.history.insert("end", f"{row['at']}  {row['event']}\n")
        self.history.config(state="disabled")

    def _chosen(self) -> Meeting | None:
        indexes = self.listbox.curselection()
        return self.selected[indexes[0]] if indexes else None

    def _scope(self, meeting: Meeting, verb: str) -> str | None:
        if not meeting.series_id:
            return "one"
        answer = messagebox.askyesnocancel(verb, "この回のみを対象にしますか？\n「いいえ」はシリーズ全体です。")
        return "one" if answer is True else "series" if answer is False else None

    def _active_ids(self) -> set[str]:
        if not self.engine:
            return set()
        with self.engine.state_lock:
            return {m.id for m in (self.engine.active, self.engine.joining) if m}

    def _add(self):
        start = datetime.combine(self.day, datetime.min.time()).replace(hour=9)
        if start <= now_jst():
            start = (now_jst() + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        form = MeetingForm(self.root, start)
        self.root.wait_window(form)
        if not form.result:
            return
        template, until = form.result
        additions = weekly_occurrences(template, datetime.combine(until, datetime.min.time())) if until else [template]
        self._store(self.storage.meetings + additions)

    def _edit(self):
        chosen = self._chosen()
        if not chosen:
            return
        if chosen.id in self._active_ids():
            messagebox.showerror("編集できません", "実行中の予約は変更できません。")
            return
        scope = self._scope(chosen, "予約の編集")
        if scope is None:
            return
        members = sorted([m for m in self.storage.meetings if m.series_id == chosen.series_id and m.start > now_jst()], key=lambda m: m.start) if scope == "series" else [chosen]
        if not members or any(m.id in self._active_ids() for m in members):
            messagebox.showerror("編集できません", "実行中の予約が含まれます。")
            return
        base = members[0]
        form = MeetingForm(self.root, base.start, base, members[-1].start.date() if scope == "series" else None)
        self.root.wait_window(form)
        if not form.result:
            return
        template, until = form.result
        if scope == "series" and until:
            additions = weekly_occurrences(template, datetime.combine(until, datetime.min.time()))
        else:
            additions = [template]
        self._store([m for m in self.storage.meetings if m.id not in {item.id for item in members}] + additions)

    def _delete(self):
        chosen = self._chosen()
        if not chosen:
            return
        scope = self._scope(chosen, "予約の削除")
        if scope is None:
            return
        members = [m for m in self.storage.meetings if m.series_id == chosen.series_id and m.start > now_jst()] if scope == "series" else [chosen]
        if any(m.id in self._active_ids() for m in members):
            messagebox.showerror("削除できません", "実行中の予約は削除できません。")
            return
        if messagebox.askyesno("確認", f"{len(members)}件の予約を削除しますか？"):
            self._store([m for m in self.storage.meetings if m.id not in {item.id for item in members}])

    def _store(self, meetings: list[Meeting]):
        try:
            self.storage.replace_meetings(meetings)
            self._refresh()
        except Exception as exc:
            messagebox.showerror("保存できません", str(exc))

    def _enable(self):
        try:
            if self.engine is None:
                self.engine = Engine(self.storage, self.events, TeamsAdapter())
                self.engine.start()
            self.engine.set_enabled(True)
        except TeamsError as exc:
            messagebox.showerror("自動運転を開始できません", str(exc))

    def _pause(self):
        if self.engine:
            self.engine.set_enabled(False)
        self.state_text.set("一時停止中")

    def _process_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "notify":
                    self._notify(value)
                elif kind == "state":
                    self.state_text.set(value)
                elif kind == "history":
                    self._refresh()
        except queue.Empty:
            pass
        self.root.after(250, self._process_events)

    def _add_tray(self):
        try:
            import win32con
            import win32gui
            self._tray_id = (self.root.winfo_id(), 1001)
            icon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD,
                                      (self._tray_id[0], self._tray_id[1],
                                       win32gui.NIF_ICON | win32gui.NIF_TIP,
                                       0, icon, "Teams 自動入退室"))
            self._tray_added = True
        except Exception:
            self._tray_added = False

    def _notify(self, message: str):
        winsound.MessageBeep()
        if self._tray_added:
            try:
                import win32con
                import win32gui
                icon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
                win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY,
                                          (self._tray_id[0], self._tray_id[1],
                                           win32gui.NIF_INFO | win32gui.NIF_ICON | win32gui.NIF_TIP,
                                           0, icon, "Teams 自動入退室", message[:240], 5000,
                                           "Teams 自動入退室", win32gui.NIIF_INFO))
            except Exception:
                pass
        tip = tk.Toplevel(self.root)
        tip.title("Teams 自動入退室")
        ttk.Label(tip, text=message, padding=18, wraplength=350).pack()
        tip.after(8000, tip.destroy)

    def _close(self):
        if self.engine:
            self.engine.stop()
        if self._tray_added:
            try:
                import win32gui
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, self._tray_id)
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()
