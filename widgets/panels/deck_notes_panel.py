"""
Deck Notes Panel - Simple text editor for deck notes.

Allows users to write and save notes about their decks.
"""

from collections.abc import Callable

import wx

from utils.stylize import stylize_button, stylize_textctrl
from utils.ui_constants import DARK_PANEL


class DeckNotesPanel(wx.Panel):
    """Panel for editing and saving deck notes."""

    def __init__(self, parent: wx.Window, on_save_callback: Callable[[str], None] | None = None):
        """
        Initialize the deck notes panel.

        Args:
            parent: Parent window
            on_save_callback: Callback when Save Notes button clicked, receives notes text
        """
        super().__init__(parent)
        self.SetBackgroundColour(DARK_PANEL)

        self.on_save = on_save_callback

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        # Text control for notes
        self.notes_text = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        stylize_textctrl(self.notes_text, multiline=True)
        sizer.Add(self.notes_text, 1, wx.EXPAND | wx.ALL, 6)

        # Button row
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.save_btn = wx.Button(self, label="Save Notes")
        stylize_button(self.save_btn)
        self.save_btn.Bind(wx.EVT_BUTTON, self._on_save_clicked)
        buttons.Add(self.save_btn, 0, wx.RIGHT, 6)

        buttons.AddStretchSpacer(1)

    # ============= Public API =============

    def set_notes(self, notes: str) -> None:
        """
        Set the notes text.

        Args:
            notes: Notes text to display
        """
        self.notes_text.ChangeValue(notes)

    def get_notes(self) -> str:
        """
        Get the current notes text.

        Returns:
            Current notes text
        """
        return self.notes_text.GetValue()

    def clear(self) -> None:
        """Clear the notes text."""
        self.notes_text.ChangeValue("")

    # ============= Private Methods =============

    def _on_save_clicked(self, _event: wx.Event) -> None:
        """Handle Save Notes button click."""
        if self.on_save:
            notes = self.get_notes()
            self.on_save(notes)
