"""
Deck Notes Panel - Simple text editor for deck notes.

Allows users to write and save notes about their decks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import wx

from utils.stylize import stylize_button, stylize_textctrl
from utils.ui_constants import DARK_PANEL

if TYPE_CHECKING:
    from widgets.deck_selector import MTGDeckSelectionFrame


class DeckNotesPanel(wx.Panel):
    """Panel for editing and saving deck notes."""

    def __init__(self, parent: wx.Window, deck_selector_frame: MTGDeckSelectionFrame):
        """
        Initialize the deck notes panel.

        Args:
            parent: Parent window
            deck_selector_frame: Reference to the main deck selector frame
        """
        super().__init__(parent)
        self.SetBackgroundColour(DARK_PANEL)

        self.deck_selector_frame = deck_selector_frame

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
        self.deck_selector_frame._save_current_notes()
