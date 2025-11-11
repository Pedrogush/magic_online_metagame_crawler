"""Metagame analysis widget for visualizing archetype distribution over time."""

from __future__ import annotations

import threading
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

import wx
from loguru import logger
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure

from navigators.mtggoldfish import get_archetype_stats

DARK_BG = wx.Colour(20, 22, 27)
DARK_PANEL = wx.Colour(34, 39, 46)
DARK_ALT = wx.Colour(40, 46, 54)
LIGHT_TEXT = wx.Colour(236, 236, 236)
SUBDUED_TEXT = wx.Colour(185, 191, 202)


class MetagameAnalysisFrame(wx.Frame):
    """Widget for displaying metagame archetype distribution and changes over time."""

    def __init__(self, parent: wx.Window | None = None) -> None:
        style = wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP
        super().__init__(parent, title="Metagame Analysis", size=(950, 650), style=style)

        self.current_format: str = "modern"
        self.current_days: int = 1
        self.current_data: dict[str, int] = {}
        self.previous_data: dict[str, int] = {}
        self.stats_data: dict[str, Any] = {}

        self._build_ui()
        self.Centre(wx.BOTH)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        wx.CallAfter(self.refresh_data)

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DARK_BG)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(main_sizer)

        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(toolbar, 0, wx.ALL | wx.EXPAND, 10)

        toolbar.Add(
            wx.StaticText(panel, label="Format:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5
        )
        self.format_choice = wx.Choice(
            panel,
            choices=[
                "Modern",
                "Standard",
                "Pioneer",
                "Legacy",
                "Vintage",
                "Pauper",
            ],
        )
        self.format_choice.SetSelection(0)
        self.format_choice.SetBackgroundColour(DARK_ALT)
        self.format_choice.SetForegroundColour(LIGHT_TEXT)
        self.format_choice.Bind(wx.EVT_CHOICE, self.on_format_change)
        toolbar.Add(self.format_choice, 0, wx.RIGHT, 15)

        toolbar.Add(
            wx.StaticText(panel, label="Time Window (days):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.days_spin = wx.SpinCtrl(panel, value="1", min=1, max=7, initial=1)
        self.days_spin.SetBackgroundColour(DARK_ALT)
        self.days_spin.SetForegroundColour(LIGHT_TEXT)
        self.days_spin.Bind(wx.EVT_SPINCTRL, self.on_days_change)
        toolbar.Add(self.days_spin, 0, wx.RIGHT, 15)

        self.refresh_button = wx.Button(panel, label="Refresh Data")
        self._stylize_button(self.refresh_button)
        self.refresh_button.Bind(wx.EVT_BUTTON, lambda _evt: self.refresh_data())
        toolbar.Add(self.refresh_button, 0, wx.RIGHT, 10)

        toolbar.AddStretchSpacer(1)

        self.status_label = wx.StaticText(panel, label="Ready")
        self.status_label.SetForegroundColour(SUBDUED_TEXT)
        toolbar.Add(self.status_label, 0, wx.ALIGN_CENTER_VERTICAL)

        content_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(content_sizer, 1, wx.ALL | wx.EXPAND, 10)

        self.figure = Figure(figsize=(6, 5), facecolor="#14161b")
        self.canvas = FigureCanvas(panel, -1, self.figure)
        self.canvas.SetBackgroundColour(DARK_PANEL)
        content_sizer.Add(self.canvas, 1, wx.EXPAND | wx.RIGHT, 10)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor("#14161b")

        right_panel = wx.Panel(panel)
        right_panel.SetBackgroundColour(DARK_PANEL)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        right_panel.SetSizer(right_sizer)
        content_sizer.Add(right_panel, 0, wx.EXPAND)

        changes_label = wx.StaticText(right_panel, label="Metagame Changes")
        changes_label.SetForegroundColour(LIGHT_TEXT)
        font = changes_label.GetFont()
        font.MakeBold()
        font.PointSize += 2
        changes_label.SetFont(font)
        right_sizer.Add(changes_label, 0, wx.ALL, 10)

        self.changes_text = wx.TextCtrl(
            right_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
        )
        self.changes_text.SetBackgroundColour(DARK_ALT)
        self.changes_text.SetForegroundColour(LIGHT_TEXT)
        right_sizer.Add(self.changes_text, 1, wx.ALL | wx.EXPAND, 10)

    def _stylize_button(self, button: wx.Button) -> None:
        button.SetBackgroundColour(DARK_PANEL)
        button.SetForegroundColour(LIGHT_TEXT)
        font = button.GetFont()
        font.MakeBold()
        button.SetFont(font)

    def on_format_change(self, event: wx.CommandEvent) -> None:
        self.current_format = self.format_choice.GetStringSelection().lower()
        self.refresh_data()

    def on_days_change(self, event: wx.SpinEvent) -> None:
        self.current_days = self.days_spin.GetValue()
        self.update_visualization()

    def refresh_data(self) -> None:
        if not self or not self.IsShown():
            return
        self._set_busy(True, "Fetching metagame data from MTGGoldfish...")

        def worker() -> None:
            try:
                stats = get_archetype_stats(self.current_format)
                logger.debug(f"Loaded archetype stats for {self.current_format}")
            except Exception as exc:
                logger.exception("Failed to fetch metagame data")
                wx.CallAfter(self._handle_error, str(exc))
                return
            wx.CallAfter(self._populate_data, stats)

        threading.Thread(target=worker, daemon=True).start()

    def _handle_error(self, message: str) -> None:
        if not self or not self.IsShown():
            return
        self._set_busy(False)
        wx.MessageBox(
            f"Unable to load metagame data:\n{message}", "Metagame Analysis", wx.OK | wx.ICON_ERROR
        )

    def _populate_data(self, stats: dict[str, Any]) -> None:
        if not self or not self.IsShown():
            return

        self.stats_data = stats
        format_stats = stats.get(self.current_format, {})
        archetype_count = len([k for k in format_stats.keys() if k != "timestamp"])
        self._set_busy(False, f"Loaded {archetype_count} archetypes")
        self.update_visualization()

    def _aggregate_for_days(self, days: int) -> dict[str, int]:
        """Aggregate deck counts for the specified number of days."""
        format_stats = self.stats_data.get(self.current_format, {})
        today = datetime.now().date()

        archetype_counts = Counter()
        for archetype_name, archetype_data in format_stats.items():
            if archetype_name == "timestamp":
                continue

            results = archetype_data.get("results", {})
            for day_offset in range(days):
                date_str = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
                count = results.get(date_str, 0)
                archetype_counts[archetype_name] += count

        return dict(archetype_counts)

    def update_visualization(self) -> None:
        if not self.stats_data:
            return

        self.current_data = self._aggregate_for_days(self.current_days)

        # Calculate previous period (same length, immediately before current period)
        previous_start = self.current_days
        previous_end = self.current_days * 2

        format_stats = self.stats_data.get(self.current_format, {})
        today = datetime.now().date()

        previous_counts = Counter()
        for archetype_name, archetype_data in format_stats.items():
            if archetype_name == "timestamp":
                continue

            results = archetype_data.get("results", {})
            for day_offset in range(previous_start, previous_end):
                date_str = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
                count = results.get(date_str, 0)
                previous_counts[archetype_name] += count

        self.previous_data = dict(previous_counts)

        self._draw_pie_chart()
        self._update_changes_display()

    def _calculate_percentages(self, counts: dict[str, int]) -> dict[str, float]:
        """Calculate percentage share for each archetype."""
        total = sum(counts.values())
        if total == 0:
            return {}
        return {archetype: (count / total) * 100 for archetype, count in counts.items()}

    def _draw_pie_chart(self) -> None:
        self.ax.clear()

        if not self.current_data or sum(self.current_data.values()) == 0:
            self.ax.text(
                0.5,
                0.5,
                "No data available for selected period",
                ha="center",
                va="center",
                color="#b9bfca",
                fontsize=14,
            )
            self.canvas.draw()
            return

        percentages = self._calculate_percentages(self.current_data)
        sorted_archetypes = sorted(percentages.items(), key=lambda x: x[1], reverse=True)

        top_archetypes = sorted_archetypes[:10]
        other_pct = sum(pct for _, pct in sorted_archetypes[10:])

        labels = [f"{arch} ({pct:.1f}%)" for arch, pct in top_archetypes]
        sizes = [pct for _, pct in top_archetypes]

        if other_pct > 0:
            labels.append(f"Other ({other_pct:.1f}%)")
            sizes.append(other_pct)

        colors = [
            "#FF6B6B",
            "#4ECDC4",
            "#45B7D1",
            "#FFA07A",
            "#98D8C8",
            "#F7DC6F",
            "#BB8FCE",
            "#85C1E2",
            "#F8B88B",
            "#ABEBC6",
            "#D5DBDB",
        ]

        wedges, texts = self.ax.pie(
            sizes,
            labels=labels,
            colors=colors[: len(sizes)],
            startangle=90,
            textprops={"color": "#ecececec", "fontsize": 9},
        )

        self.ax.axis("equal")
        title = f"{self.current_format.title()} Metagame (Last {self.current_days} day{'s' if self.current_days > 1 else ''})"
        self.ax.set_title(title, color="#ecececec", fontsize=12, pad=20)

        self.canvas.draw()

    def _update_changes_display(self) -> None:
        if not self.current_data or not self.previous_data:
            self.changes_text.SetValue("No comparison data available")
            return

        current_pct = self._calculate_percentages(self.current_data)
        previous_pct = self._calculate_percentages(self.previous_data)

        all_archetypes = set(current_pct.keys()) | set(previous_pct.keys())
        changes = {}
        for archetype in all_archetypes:
            current = current_pct.get(archetype, 0.0)
            previous = previous_pct.get(archetype, 0.0)
            changes[archetype] = current - previous

        sorted_changes = sorted(changes.items(), key=lambda x: abs(x[1]), reverse=True)

        lines = [f"Changes vs previous {self.current_days} day period:\n"]
        for archetype, change in sorted_changes[:15]:
            if abs(change) < 0.1:
                continue
            symbol = "+" if change > 0 else ""
            current_val = current_pct.get(archetype, 0.0)
            lines.append(f"{symbol}{change:+.1f}% {archetype} (now {current_val:.1f}%)")

        if len(lines) == 1:
            lines.append("No significant changes")

        self.changes_text.SetValue("\n".join(lines))

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        if self.refresh_button:
            self.refresh_button.Enable(not busy)
        if message:
            self.status_label.SetLabel(message)
        elif busy:
            self.status_label.SetLabel("Loading...")
        else:
            self.status_label.SetLabel("Ready")

    def on_close(self, event: wx.CloseEvent) -> None:
        event.Skip()


__all__ = ["MetagameAnalysisFrame"]
