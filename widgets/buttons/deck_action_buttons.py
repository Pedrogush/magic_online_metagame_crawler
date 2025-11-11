"""
Deck Action Buttons - Group of buttons for deck operations.

Provides Load, Copy, Save, and Today's Average buttons with callback support.
"""

from typing import Callable

import wx

from utils.stylize import stylize_button


class DeckActionButtons(wx.Panel):
    """Panel containing deck action buttons (Load, Copy, Save, Today's Average)."""

    def __init__(
        self,
        parent: wx.Window,
        on_load: Callable[[], None] | None = None,
        on_copy: Callable[[], None] | None = None,
        on_save: Callable[[], None] | None = None,
        on_daily_average: Callable[[], None] | None = None,
    ):
        """
        Initialize the deck action buttons panel.

        Args:
            parent: Parent window
            on_load: Callback when Load Deck button clicked
            on_copy: Callback when Copy button clicked
            on_save: Callback when Save Deck button clicked
            on_daily_average: Callback when Today's Average button clicked
        """
        super().__init__(parent)

        self.on_load = on_load
        self.on_copy = on_copy
        self.on_save = on_save
        self.on_daily_average = on_daily_average

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the button panel UI."""
        button_row = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(button_row)

        # Load Deck button
        self.load_button = wx.Button(self, label="Load Deck")
        stylize_button(self.load_button)
        self.load_button.Disable()
        self.load_button.Bind(wx.EVT_BUTTON, self._on_load_clicked)
        button_row.Add(self.load_button, 0, wx.RIGHT, 6)

        # Today's Average button
        self.daily_average_button = wx.Button(self, label="Today's Average")
        stylize_button(self.daily_average_button)
        self.daily_average_button.Disable()
        self.daily_average_button.Bind(wx.EVT_BUTTON, self._on_daily_average_clicked)
        button_row.Add(self.daily_average_button, 0, wx.RIGHT, 6)

        # Copy button
        self.copy_button = wx.Button(self, label="Copy")
        stylize_button(self.copy_button)
        self.copy_button.Disable()
        self.copy_button.Bind(wx.EVT_BUTTON, self._on_copy_clicked)
        button_row.Add(self.copy_button, 0, wx.RIGHT, 6)

        # Save Deck button
        self.save_button = wx.Button(self, label="Save Deck")
        stylize_button(self.save_button)
        self.save_button.Disable()
        self.save_button.Bind(wx.EVT_BUTTON, self._on_save_clicked)
        button_row.Add(self.save_button, 0)

    # ============= Public API =============

    def enable_load(self, enable: bool = True) -> None:
        """Enable or disable the Load Deck button."""
        if enable:
            self.load_button.Enable()
        else:
            self.load_button.Disable()

    def enable_daily_average(self, enable: bool = True) -> None:
        """Enable or disable the Today's Average button."""
        if enable:
            self.daily_average_button.Enable()
        else:
            self.daily_average_button.Disable()

    def enable_copy(self, enable: bool = True) -> None:
        """Enable or disable the Copy button."""
        if enable:
            self.copy_button.Enable()
        else:
            self.copy_button.Disable()

    def enable_save(self, enable: bool = True) -> None:
        """Enable or disable the Save Deck button."""
        if enable:
            self.save_button.Enable()
        else:
            self.save_button.Disable()

    def enable_deck_actions(self, enable: bool = True) -> None:
        """Enable or disable Copy and Save buttons (for when deck is loaded)."""
        self.enable_copy(enable)
        self.enable_save(enable)

    # ============= Private Methods =============

    def _on_load_clicked(self, _event: wx.Event) -> None:
        """Handle Load Deck button click."""
        if self.on_load:
            self.on_load()

    def _on_daily_average_clicked(self, _event: wx.Event) -> None:
        """Handle Today's Average button click."""
        if self.on_daily_average:
            self.on_daily_average()

    def _on_copy_clicked(self, _event: wx.Event) -> None:
        """Handle Copy button click."""
        if self.on_copy:
            self.on_copy()

    def _on_save_clicked(self, _event: wx.Event) -> None:
        """Handle Save Deck button click."""
        if self.on_save:
            self.on_save()
