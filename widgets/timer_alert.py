"""Utility window for monitoring the MTGO challenge timer via OCR."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox

import pyautogui
import pytesseract
from PIL import Image
from loguru import logger

from navigators.mtgo import wait_for_click

try:
    import winsound  # type: ignore

    def _beep(frequency: int, duration: int) -> None:
        winsound.Beep(frequency, duration)

except Exception:  # pragma: no cover - non-Windows platforms

    def _beep(frequency: int, duration: int) -> None:
        logger.info("Alert: %s Hz for %s ms", frequency, duration)


TIMER_OCR_CONFIG = "-c tessedit_char_whitelist=0123456789: --psm 7"


class TimerAlertWindow:
    """Small controller that watches a screen region for the MTGO timer."""

    def __init__(self, master: tk.Misc) -> None:
        self.master = master
        self.window = tk.Toplevel(master)
        self.window.title("MTGO Timer Alert")
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.region_var = tk.StringVar(value="0,0,200,60")
        self.thresholds_var = tk.StringVar(value="300,120,60")
        self.alert_on_start_var = tk.BooleanVar(value=True)
        self.frequency_var = tk.IntVar(value=1200)
        self.duration_var = tk.IntVar(value=400)
        self.poll_interval_var = tk.IntVar(value=1000)
        self.status_var = tk.StringVar(value="Enter region and thresholds, then click Start.")

        self.monitor_job: str | None = None
        self.last_seconds: int | None = None
        self.triggered_thresholds: set[int] = set()
        self.start_alert_sent = False
        self.region: tuple[int, int, int, int] = (0, 0, 0, 0)

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        frame = tk.Frame(self.window, padx=10, pady=10)
        frame.grid(column=0, row=0, sticky="nsew")
        for i in range(3):
            frame.grid_columnconfigure(i, weight=1 if i == 1 else 0)

        tk.Label(frame, text="Timer Region (x,y,w,h):").grid(row=0, column=0, sticky="w")
        region_entry = tk.Entry(frame, textvariable=self.region_var, width=18)
        region_entry.grid(row=0, column=1, sticky="ew")
        tk.Button(frame, text="Select…", command=self.pick_region).grid(row=0, column=2, sticky="w", padx=(6, 0))

        tk.Label(frame, text="Thresholds (seconds, comma separated):").grid(row=1, column=0, sticky="w", pady=(6, 0))
        thresholds_entry = tk.Entry(frame, textvariable=self.thresholds_var)
        thresholds_entry.grid(row=1, column=1, sticky="ew", pady=(6, 0))

        tk.Label(frame, text="Poll interval (ms):").grid(row=2, column=0, sticky="w", pady=(6, 0))
        poll_entry = tk.Entry(frame, textvariable=self.poll_interval_var)
        poll_entry.grid(row=2, column=1, sticky="ew", pady=(6, 0))

        tk.Label(frame, text="Tone frequency (Hz):").grid(row=3, column=0, sticky="w", pady=(6, 0))
        freq_entry = tk.Entry(frame, textvariable=self.frequency_var)
        freq_entry.grid(row=3, column=1, sticky="ew", pady=(6, 0))

        tk.Label(frame, text="Tone duration (ms):").grid(row=4, column=0, sticky="w", pady=(6, 0))
        duration_entry = tk.Entry(frame, textvariable=self.duration_var)
        duration_entry.grid(row=4, column=1, sticky="ew", pady=(6, 0))

        alert_on_start = tk.Checkbutton(frame, text="Alert when timer starts counting down", variable=self.alert_on_start_var)
        alert_on_start.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

        button_row = tk.Frame(frame)
        button_row.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="ew")
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)
        button_row.grid_columnconfigure(2, weight=1)

        tk.Button(button_row, text="Start", command=self.start_monitoring).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Button(button_row, text="Stop", command=self.stop_monitoring).grid(row=0, column=1, sticky="ew")
        tk.Button(button_row, text="Test Alert", command=self.test_alert).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        status_label = tk.Label(frame, textvariable=self.status_var, anchor="w", justify="left", wraplength=300)
        status_label.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        tk.Label(frame, text="Tip: use the MTGO coordinates in x,y,width,height format.", anchor="w", justify="left")\
            .grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    # ----------------------------------------------------------------- logic
    def start_monitoring(self) -> None:
        if self.monitor_job is not None:
            self.status_var.set("Already monitoring the timer.")
            return
        try:
            self.region = self._parse_region(self.region_var.get())
        except ValueError as exc:
            messagebox.showerror("Timer Alert", f"Invalid region: {exc}")
            return

        try:
            thresholds = self._parse_thresholds(self.thresholds_var.get())
        except ValueError as exc:
            messagebox.showerror("Timer Alert", str(exc))
            return
        if not thresholds:
            messagebox.showerror("Timer Alert", "Please enter at least one threshold in seconds.")
            return
        self.threshold_list = thresholds
        self.triggered_thresholds = set()
        self.start_alert_sent = False
        self.last_seconds = None
        self.status_var.set("Monitoring timer... Press Stop to end.")
        self._queue_monitor()

    def stop_monitoring(self) -> None:
        if self.monitor_job is not None:
            try:
                self.window.after_cancel(self.monitor_job)
            except Exception:
                pass
            self.monitor_job = None
        self.status_var.set("Timer monitoring stopped.")

    def _queue_monitor(self) -> None:
        try:
            interval_value = int(self.poll_interval_var.get())
        except (tk.TclError, ValueError):
            interval_value = 1000
            self.poll_interval_var.set(interval_value)
        interval = max(250, interval_value)
        self.monitor_job = self.window.after(interval, self._monitor_timer)

    def _monitor_timer(self) -> None:
        self.monitor_job = None
        seconds = self._read_timer_seconds()
        if seconds is None:
            self.status_var.set("Timer unreadable. Adjust region or lighting.")
            self._queue_monitor()
            return

        if self.last_seconds is None:
            if self.alert_on_start_var.get():
                self._play_alert("Timer started counting down.")
            self.start_alert_sent = True
        elif self.alert_on_start_var.get() and not self.start_alert_sent and seconds < self.last_seconds:
            self._play_alert("Timer started counting down.")
            self.start_alert_sent = True

        for threshold in self.threshold_list:
            if seconds <= threshold and threshold not in self.triggered_thresholds:
                self.triggered_thresholds.add(threshold)
                self._play_alert(f"Timer reached {threshold} seconds")

        if self.last_seconds is not None and seconds > self.last_seconds:
            self.triggered_thresholds = {t for t in self.triggered_thresholds if t <= seconds}
            if seconds > max(self.threshold_list, default=0):
                self.start_alert_sent = False

        mins, secs = divmod(seconds, 60)
        self.status_var.set(f"Timer: {mins:02d}:{secs:02d}")
        self.last_seconds = seconds
        self._queue_monitor()

    def pick_region(self) -> None:
        try:
            self.status_var.set("Click the top-left corner of the timer region…")
            self.window.update_idletasks()
            x1, y1 = wait_for_click()
            self.status_var.set("Now click the bottom-right corner of the timer region…")
            self.window.update_idletasks()
            x2, y2 = wait_for_click()
        except Exception as exc:
            logger.error(f"Failed to capture timer region: {exc}")
            self.status_var.set("Region selection cancelled.")
            return
        if x2 <= x1 or y2 <= y1:
            self.status_var.set("Invalid region selection; try again.")
            return
        region = (x1, y1, x2 - x1, y2 - y1)
        self.region_var.set(",".join(str(v) for v in region))
        self.region = region
        self.status_var.set("Timer region updated.")

    def _read_timer_seconds(self) -> int | None:
        x, y, width, height = self.region
        try:
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
        except Exception as exc:
            logger.error(f"Failed to capture timer region: {exc}")
            return None
        image = screenshot.convert("L")
        image = image.resize((max(1, image.width * 2), max(1, image.height * 2)), Image.LANCZOS)
        text = pytesseract.image_to_string(image, config=TIMER_OCR_CONFIG)
        match = re.search(r"(\d{1,2}):(\d{2})", text)
        if not match:
            return None
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        return minutes * 60 + seconds

    def _parse_region(self, value: str) -> tuple[int, int, int, int]:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if len(parts) != 4:
            raise ValueError("region must be four integers: x,y,width,height")
        coords = tuple(int(p) for p in parts)
        if coords[2] <= 0 or coords[3] <= 0:
            raise ValueError("width and height must be positive")
        return coords  # type: ignore[return-value]

    def _parse_thresholds(self, value: str) -> list[int]:
        thresholds: set[int] = set()
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                thresholds.add(max(0, int(part)))
            except ValueError:
                raise ValueError(f"Invalid threshold: {part}")
        return sorted(thresholds, reverse=True)

    def _play_alert(self, reason: str) -> None:
        try:
            frequency = int(self.frequency_var.get())
        except (tk.TclError, ValueError):
            frequency = 1000
            self.frequency_var.set(frequency)
        try:
            duration = int(self.duration_var.get())
        except (tk.TclError, ValueError):
            duration = 400
            self.duration_var.set(duration)
        frequency = max(100, frequency)
        duration = max(50, duration)
        logger.info("Timer alert triggered: %s", reason)
        try:
            _beep(frequency, duration)
        except Exception as exc:  # pragma: no cover - safeguard
            logger.warning(f"Unable to play alert: {exc}")
        self.status_var.set(reason)

    def test_alert(self) -> None:
        self._play_alert("Test alert")

    def close(self) -> None:
        self.stop_monitoring()
        self.window.destroy()

    @property
    def is_open(self) -> bool:
        return bool(self.window) and self.window.winfo_exists()
