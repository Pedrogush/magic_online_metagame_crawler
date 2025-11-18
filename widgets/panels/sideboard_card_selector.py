"""Card selector widget for sideboard guide entries."""

from __future__ import annotations

from typing import Any

import wx
import wx.lib.scrolledpanel as scrolled

from utils.constants import DARK_ALT, DARK_PANEL, LIGHT_TEXT, SUBDUED_TEXT


class SideboardCardSelector(wx.Panel):
    """A panel that displays cards with quantity controls for sideboard planning."""

    def __init__(
        self,
        parent: wx.Window,
        title: str,
        available_cards: list[dict[str, Any]],
    ):
        """
        Initialize the card selector.

        Args:
            parent: Parent window
            title: Title for this selector (e.g., "Play: Out")
            available_cards: List of cards available to select from (from mainboard or sideboard)
        """
        super().__init__(parent)
        self.SetBackgroundColour(DARK_PANEL)

        self.available_cards = available_cards
        self.selected_cards: dict[str, int] = {}  # name -> quantity

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        # Title
        title_label = wx.StaticText(self, label=title)
        title_label.SetForegroundColour(LIGHT_TEXT)
        title_label.SetFont(title_label.GetFont().Bold())
        sizer.Add(title_label, 0, wx.ALL, 4)

        # Card count
        self.count_label = wx.StaticText(self, label="0 cards selected")
        self.count_label.SetForegroundColour(SUBDUED_TEXT)
        sizer.Add(self.count_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        # Scrolled panel for cards
        self.scroll_panel = scrolled.ScrolledPanel(self, style=wx.VSCROLL)
        self.scroll_panel.SetBackgroundColour(DARK_ALT)
        self.scroll_panel.SetupScrolling(scroll_x=False, scroll_y=True)

        self.card_sizer = wx.BoxSizer(wx.VERTICAL)
        self.scroll_panel.SetSizer(self.card_sizer)
        sizer.Add(self.scroll_panel, 1, wx.EXPAND | wx.ALL, 4)

        self._build_card_list()

    def _build_card_list(self) -> None:
        """Build the list of cards with quantity controls."""
        self.card_sizer.Clear(delete_windows=True)
        self.card_widgets: dict[str, tuple[wx.SpinCtrl, wx.Panel]] = {}

        for card in self.available_cards:
            card_name = card["name"]
            max_qty = card["qty"]

            # Card row panel
            row_panel = wx.Panel(self.scroll_panel)
            row_panel.SetBackgroundColour(DARK_ALT)
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            row_panel.SetSizer(row_sizer)

            # Quantity spinner
            spinner = wx.SpinCtrl(
                row_panel,
                value="0",
                min=0,
                max=max_qty,
                size=(50, -1),
                style=wx.SP_ARROW_KEYS | wx.ALIGN_RIGHT,
            )
            spinner.SetBackgroundColour(DARK_PANEL)
            spinner.SetForegroundColour(LIGHT_TEXT)
            spinner.Bind(wx.EVT_SPINCTRL, lambda evt, name=card_name: self._on_qty_change(name))
            spinner.Bind(wx.EVT_TEXT, lambda evt, name=card_name: self._on_qty_change(name))
            row_sizer.Add(spinner, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

            # Card name
            name_label = wx.StaticText(row_panel, label=f"{card_name} (max {max_qty})")
            name_label.SetForegroundColour(LIGHT_TEXT)
            row_sizer.Add(name_label, 1, wx.ALIGN_CENTER_VERTICAL)

            self.card_sizer.Add(row_panel, 0, wx.EXPAND | wx.BOTTOM, 2)
            self.card_widgets[card_name] = (spinner, row_panel)

        self.scroll_panel.Layout()
        self.scroll_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        self._update_count()

    def _on_qty_change(self, card_name: str) -> None:
        """Handle quantity change for a card."""
        spinner, _ = self.card_widgets[card_name]
        qty = spinner.GetValue()

        if qty > 0:
            self.selected_cards[card_name] = qty
        else:
            self.selected_cards.pop(card_name, None)

        self._update_count()

    def _update_count(self) -> None:
        """Update the card count label."""
        total = sum(self.selected_cards.values())
        self.count_label.SetLabel(f"{total} card{'s' if total != 1 else ''} selected")

    def set_selected_cards(self, cards: dict[str, int]) -> None:
        """
        Set the selected cards.

        Args:
            cards: Dictionary mapping card name to quantity
        """
        self.selected_cards = cards.copy()

        # Update spinners
        for card_name, (spinner, _) in self.card_widgets.items():
            qty = self.selected_cards.get(card_name, 0)
            spinner.SetValue(qty)

        self._update_count()

    def get_selected_cards(self) -> dict[str, int]:
        """Get the selected cards as a dictionary."""
        return self.selected_cards.copy()

    def get_selected_cards_list(self) -> list[dict[str, Any]]:
        """Get the selected cards as a list of dicts with name and qty."""
        return [{"name": name, "qty": qty} for name, qty in sorted(self.selected_cards.items())]
