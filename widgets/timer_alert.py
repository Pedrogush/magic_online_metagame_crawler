"""Timer alert using MTGOSDK runtime clocks."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from loguru import logger

from utils import mtgo_bridge

try:
    import winsound  # type: ignore

    def _beep(frequency: int, duration: int) -> None:
        winsound.Beep(frequency, duration)

except Exception:  # pragma: no cover

    def _beep(frequency: int, duration: int) -> None:
        logger.info("Alert: %s Hz for %s ms", frequency, duration)


class TimerAlertWindow:
    """Polls MTGO match clocks via MTGOSDK and plays alerts."""

    def __init__(self, master: tk.Misc) -> None:
        self.master = master
        self.window = tk.Toplevel(master)
        self.window.title("MTGO Timer Alert")
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.username_var = tk.StringVar()
        self.monitor_var = tk.StringVar(value="self")
        self.thresholds_var = tk.StringVar(value="300,120,60")
        self.alert_on_start_var = tk.BooleanVar(value=True)
        self.frequency_var = tk.IntVar(value=1200)
        self.duration_var = tk.IntVar(value=400)
        self.poll_interval_var = tk.IntVar(value=1000)
        self.status_var = tk.StringVar(value="Set options and click Start to begin monitoring.")

        self.match_var = tk.StringVar(value="All matches")
        self._match_menu: tk.OptionMenu | None = None
        self._match_options: dict[str, dict | None] = {"All matches": None}

        self.monitor_job: str | None = None
        self.last_seconds: int | None = None
        self.triggered_thresholds: set[int] = set()
        self.start_alert_sent = False

        self._build_ui()
    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        frame = tk.Frame(self.window, padx=12, pady=10)
        frame.grid(column=0, row=0, sticky="nsew")

        tk.Label(frame, text="Your MTGO username:").grid(row=0, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.username_var, width=24).grid(row=0, column=1, sticky="ew")

        tk.Label(frame, text="Match:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._match_menu = tk.OptionMenu(frame, self.match_var, *self._match_options.keys())
        self._match_menu.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        self._refresh_match_menu()

        tk.Label(frame, text="Monitor:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        monitor_menu = tk.OptionMenu(frame, self.monitor_var, "self", "opponent", "both")
        monitor_menu.grid(row=2, column=1, sticky="ew", pady=(6, 0))

        tk.Label(frame, text="Thresholds (seconds):").grid(row=3, column=0, sticky="w", pady=(6, 0))
        tk.Entry(frame, textvariable=self.thresholds_var).grid(row=3, column=1, sticky="ew", pady=(6, 0))

        tk.Label(frame, text="Poll interval (ms):").grid(row=4, column=0, sticky="w", pady=(6, 0))
        tk.Entry(frame, textvariable=self.poll_interval_var).grid(row=4, column=1, sticky="ew", pady=(6, 0))

        tk.Label(frame, text="Tone frequency (Hz):").grid(row=5, column=0, sticky="w", pady=(6, 0))
        tk.Entry(frame, textvariable=self.frequency_var).grid(row=5, column=1, sticky="ew", pady=(6, 0))

        tk.Label(frame, text="Tone duration (ms):").grid(row=6, column=0, sticky="w", pady=(6, 0))
        tk.Entry(frame, textvariable=self.duration_var).grid(row=6, column=1, sticky="ew", pady=(6, 0))

        tk.Checkbutton(
            frame,
            text="Alert when timer starts counting down",
            variable=self.alert_on_start_var,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))

        buttons = tk.Frame(frame)
        buttons.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        buttons.grid_columnconfigure((0, 1, 2), weight=1)

        tk.Button(buttons, text="Start", command=self.start_monitoring).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Button(buttons, text="Stop", command=self.stop_monitoring).grid(row=0, column=1, sticky="ew")
        tk.Button(buttons, text="Test Alert", command=self.test_alert).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        tk.Label(frame, textvariable=self.status_var, anchor="w", justify="left", wraplength=320).grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

    # ----------------------------------------------------------------- logic
    def start_monitoring(self) -> None:
        if self.monitor_job is not None:
            self.status_var.set("Already monitoring the timer.")
            return

        thresholds = self._parse_thresholds()
        if not thresholds:
            messagebox.showwarning("Timer Alert", "Please enter at least one numeric threshold.")
            return

        try:
            poll_interval = max(250, int(self.poll_interval_var.get()))
        except (TypeError, ValueError):
            messagebox.showwarning("Timer Alert", "Invalid poll interval.")
            return

        self.triggered_thresholds = set()
        self.start_alert_sent = False
        self.last_seconds = None
        self.status_var.set("Monitoring MTGO match clocks…")

        def _poll() -> None:
            self._monitor_timer(thresholds)
            self.monitor_job = self.window.after(poll_interval, _poll)

        self.monitor_job = self.window.after(0, _poll)

    def stop_monitoring(self) -> None:
        if self.monitor_job is not None:
            self.window.after_cancel(self.monitor_job)
            self.monitor_job = None
        self.status_var.set("Timer monitoring stopped.")

    def test_alert(self) -> None:
        _beep(self.frequency_var.get(), self.duration_var.get())

    def close(self) -> None:
        self.stop_monitoring()
        try:
            self.window.destroy()
        except Exception:
            pass

    # ----------------------------------------------------------------- internals
    def _monitor_timer(self, thresholds: list[int]) -> None:
        try:
            ready, error = mtgo_bridge.ensure_runtime_ready()
            if not ready:
                self.status_var.set(f"MTGOSDK runtime unavailable: {error or 'see logs'}")
                return
            matches = mtgo_bridge.list_active_matches()
        except Exception as exc:
            logger.error(f"Timer alert failed to query MTGO state: {exc}")
            self.status_var.set(f"Failed to query MTGO state: {exc}")
            return

        self._update_available_matches(matches)

        if not matches:
            self.status_var.set("No active matches detected. Join an event or match to monitor clocks.")
            self.last_seconds = None
            self.triggered_thresholds.clear()
            return

        selection_label = self.match_var.get()
        if selection_label not in self._match_options:
            selection_label = "All matches"
            self.match_var.set(selection_label)

        selected_matches = []
        if selection_label == "All matches":
            selected_matches = matches
        else:
            match_entry = self._match_options.get(selection_label)
            if match_entry:
                selected_matches = [match_entry]
            else:
                selected_matches = matches

        username = (self.username_var.get() or "").strip().lower()
        monitor = self.monitor_var.get()

        targets = []
        status_lines = []
        for match in selected_matches:
            players = match.get("players") or []
            line_parts = []
            for player in players:
                if not isinstance(player, dict):
                    continue
                name = player.get("name") or "Unknown"
                is_self = bool(player.get("isSelf"))
                if username and name.lower() == username:
                    is_self = True
                player["isSelf"] = is_self
                if monitor == "self" and not is_self:
                    continue
                if monitor == "opponent" and is_self:
                    continue
                targets.append(player)
                clock = player.get("clockSeconds")
                clock_display = f"{clock}s" if isinstance(clock, int) else "—"
                prefix = "You" if is_self else name
                line_parts.append(f"{prefix}: {clock_display}")
            label = self._format_match_label(match)
            if line_parts:
                status_lines.append(f"{label} — {' / '.join(line_parts)}")
            else:
                status_lines.append(f"{label} — awaiting clock data")

        if not targets:
            if monitor == "self":
                self.status_var.set("Waiting for MTGO to detect your account in the active matches.")
            else:
                self.status_var.set("Waiting for opponent clocks to appear.")
            return

        seconds_values = [p.get("clockSeconds") for p in targets if isinstance(p.get("clockSeconds"), int)]
        if not seconds_values:
            self.status_var.set("Unable to read clock values yet.")
            return

        current_seconds = max(min(seconds_values), 0)
        current_seconds = max(min(seconds_values), 0)
        self.status_var.set("\n".join(status_lines))
        if self.alert_on_start_var.get() and not self.start_alert_sent:
            self._trigger_alert("Countdown started")
            self.start_alert_sent = True

        for threshold in thresholds:
            if threshold < 0 or threshold in self.triggered_thresholds:
                continue
            if current_seconds <= threshold:
                self._trigger_alert(f"Timer reached {threshold} seconds")
                self.triggered_thresholds.add(threshold)

        self.last_seconds = current_seconds

    def _trigger_alert(self, message: str) -> None:
        logger.debug(f"Timer alert: {message}")
        _beep(self.frequency_var.get(), self.duration_var.get())

    def _parse_thresholds(self) -> list[int]:
        raw = self.thresholds_var.get()
        thresholds: list[int] = []
        for chunk in raw.split(','):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                thresholds.append(int(chunk))
            except ValueError:
                logger.warning(f"Skipping invalid threshold value: {chunk}")
        thresholds.sort(reverse=True)
        return thresholds

    def _update_available_matches(self, matches: list[dict]) -> None:
        options: dict[str, dict | None] = {"All matches": None}
        used_labels: set[str] = set()
        for match in matches:
            label = self._format_match_label(match)
            base_label = label
            counter = 2
            while label in used_labels or label in options:
                label = f"{base_label} ({counter})"
                counter += 1
            options[label] = match
            used_labels.add(label)
        if set(options.keys()) != set(self._match_options.keys()) or any(self._match_options.get(label) is not options[label] for label in options):
            self._match_options = options
            self._refresh_match_menu()

    def _refresh_match_menu(self) -> None:
        if not self._match_menu:
            return
        menu = self._match_menu["menu"]
        menu.delete(0, "end")
        for label in self._match_options:
            menu.add_command(label=label, command=tk._setit(self.match_var, label))
        if self.match_var.get() not in self._match_options:
            self.match_var.set(next(iter(self._match_options)))

    def _format_match_label(self, match: dict) -> str:
        event_desc = match.get("eventDescription") or match.get("format") or "Match"
        opponents = [
            player.get("name")
            for player in match.get("players") or []
            if isinstance(player, dict) and not player.get("isSelf")
        ]
        opponent = opponents[0] if opponents else "Unknown"
        match_id = match.get("id") or match.get("eventId")
        if opponent and opponent != "Unknown":
            return f"{event_desc} vs {opponent}"
        if match_id:
            return f"{event_desc} ({match_id})"
        return str(event_desc)
