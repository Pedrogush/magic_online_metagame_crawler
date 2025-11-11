"""Card table panel - displays deck zones (mainboard, sideboard) with card grid."""

from __future__ import annotations

from typing import Any, Callable

import wx


# Color constants
DARK_PANEL = wx.Colour(34, 39, 46)
DARK_ALT = wx.Colour(40, 46, 54)
DARK_ACCENT = wx.Colour(59, 130, 246)
LIGHT_TEXT = wx.Colour(236, 236, 236)
SUBDUED_TEXT = wx.Colour(185, 191, 202)


class CardCardPanel(wx.Panel):
    """Individual card display panel within a card table."""

    def __init__(
        self,
        parent: wx.Window,
        zone: str,
        card: dict[str, Any],
        icon_factory: Any,
        get_metadata: Callable[[str], dict[str, Any] | None],
        owned_status: Callable[[str, int], tuple[str, wx.Colour]],
        on_delta: Callable[[str, str, int], None],
        on_remove: Callable[[str, str], None],
        on_select: Callable[[str, dict[str, Any], "CardCardPanel"], None],
    ) -> None:
        """Initialize card panel.

        Args:
            parent: Parent window
            zone: Zone name (main, side, etc.)
            card: Card dictionary with name and qty
            icon_factory: Mana icon factory for rendering mana costs
            get_metadata: Function to get card metadata
            owned_status: Function to get ownership status
            on_delta: Callback for quantity changes
            on_remove: Callback for card removal
            on_select: Callback for card selection
        """
        super().__init__(parent)
        self.zone = zone
        self.card = card
        self._get_metadata = get_metadata
        self._owned_status = owned_status
        self._on_delta = on_delta
        self._on_remove = on_remove
        self._on_select = on_select
        self._active = False

        self.SetBackgroundColour(DARK_ALT)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(row)
        self.SetMinSize((-1, 34))

        base_font = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.qty_label = wx.StaticText(self, label=str(card["qty"]))
        self.qty_label.SetForegroundColour(LIGHT_TEXT)
        self.qty_label.SetFont(base_font)
        row.Add(self.qty_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        meta = get_metadata(card["name"]) or {}
        mana_cost = meta.get("mana_cost", "")

        owned_text, owned_colour = owned_status(card["name"], card["qty"])
        self.name_label = wx.StaticText(self, label=card["name"], style=wx.ST_NO_AUTORESIZE)
        self.name_label.SetForegroundColour(owned_colour)
        self.name_label.SetFont(base_font)
        self.name_label.Wrap(110)
        row.Add(self.name_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        mana_panel = icon_factory.render(self, mana_cost)
        row.Add(mana_panel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        self.button_panel = wx.Panel(self)
        self.button_panel.SetBackgroundColour(DARK_ALT)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_panel.SetSizer(btn_sizer)
        add_btn = wx.Button(self.button_panel, label="+", size=(24, 24))
        add_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_delta(zone, card["name"], 1))
        btn_sizer.Add(add_btn, 0)
        sub_btn = wx.Button(self.button_panel, label="−", size=(24, 24))
        sub_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_delta(zone, card["name"], -1))
        btn_sizer.Add(sub_btn, 0, wx.LEFT, 2)
        rem_btn = wx.Button(self.button_panel, label="×", size=(24, 24))
        rem_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_remove(zone, card["name"]))
        btn_sizer.Add(rem_btn, 0, wx.LEFT, 2)
        row.Add(self.button_panel, 0, wx.ALIGN_CENTER_VERTICAL)
        self.button_panel.Hide()

        self._bind_click_targets([self, self.qty_label, self.name_label, mana_panel])

    def update_quantity(self, qty: int, owned_text: str, owned_colour: wx.Colour) -> None:
        """Update card quantity and ownership display.

        Args:
            qty: New quantity
            owned_text: Ownership status text
            owned_colour: Color for ownership status
        """
        self.qty_label.SetLabel(str(qty))
        self.name_label.SetForegroundColour(owned_colour)
        self.Layout()

    def set_active(self, active: bool) -> None:
        """Set active state (selected/highlighted).

        Args:
            active: Whether panel should be active
        """
        if self._active == active:
            return
        self._active = active
        self.button_panel.Show(active)
        self.button_panel.Enable(active)
        self.button_panel.SetBackgroundColour(DARK_ACCENT if active else DARK_ALT)
        self.SetBackgroundColour(DARK_ACCENT if active else DARK_ALT)
        self.Refresh()
        self.Layout()

    def _bind_click_targets(self, targets: list[wx.Window]) -> None:
        """Bind click events to widgets.

        Args:
            targets: Widgets to bind click events to
        """
        for target in targets:
            target.Bind(wx.EVT_LEFT_DOWN, self._handle_click)
            for child in target.GetChildren():
                child.Bind(wx.EVT_LEFT_DOWN, self._handle_click)

    def _handle_click(self, _event: wx.MouseEvent) -> None:
        """Handle click event."""
        self._on_select(self.zone, self.card, self)


class CardTablePanel(wx.Panel):
    """Panel displaying cards in a grid layout for a deck zone."""

    def __init__(
        self,
        parent: wx.Window,
        zone: str,
        icon_factory: Any,
        get_metadata: Callable[[str], dict[str, Any] | None],
        owned_status: Callable[[str, int], tuple[str, wx.Colour]],
        on_delta: Callable[[str, str, int], None],
        on_remove: Callable[[str, str], None],
        on_add: Callable[[str], None],
        on_select: Callable[[str, dict[str, Any] | None], None],
    ) -> None:
        """Initialize card table panel.

        Args:
            parent: Parent window
            zone: Zone name (main, side, etc.)
            icon_factory: Mana icon factory for rendering mana costs
            get_metadata: Function to get card metadata
            owned_status: Function to get ownership status
            on_delta: Callback for quantity changes
            on_remove: Callback for card removal
            on_add: Callback for adding cards
            on_select: Callback for card selection
        """
        super().__init__(parent)
        self.zone = zone
        self.icon_factory = icon_factory
        self._get_metadata = get_metadata
        self._owned_status = owned_status
        self._on_delta = on_delta
        self._on_remove = on_remove
        self._on_add = on_add
        self._on_select = on_select
        self.cards: list[dict[str, Any]] = []
        self.card_widgets: list[CardCardPanel] = []
        self.active_panel: CardCardPanel | None = None
        self.selected_name: str | None = None

        self.SetBackgroundColour(DARK_PANEL)
        outer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(outer)

        header = wx.BoxSizer(wx.HORIZONTAL)
        self.count_label = wx.StaticText(self, label="0 cards")
        self.count_label.SetForegroundColour(SUBDUED_TEXT)
        header.Add(self.count_label, 0, wx.ALIGN_CENTER_VERTICAL)
        header.AddStretchSpacer(1)
        add_btn = wx.Button(self, label="Add Card")
        add_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_add(self.zone))
        header.Add(add_btn, 0)
        outer.Add(header, 0, wx.EXPAND | wx.BOTTOM, 4)

        self.scroller = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.scroller.SetBackgroundColour(DARK_PANEL)
        self.scroller.SetScrollRate(5, 5)
        self.grid_sizer = wx.GridSizer(0, 4, 8, 8)
        self.scroller.SetSizer(self.grid_sizer)
        outer.Add(self.scroller, 1, wx.EXPAND)

    def set_cards(self, cards: list[dict[str, Any]]) -> None:
        """Update displayed cards.

        Args:
            cards: List of card dictionaries
        """
        self.cards = cards
        self._rebuild_grid()

    def _rebuild_grid(self) -> None:
        """Rebuild the card grid display."""
        self.grid_sizer.Clear(delete_windows=True)
        self.card_widgets = []
        self.active_panel = None
        total = sum(card["qty"] for card in self.cards)
        self.count_label.SetLabel(f"{total} card{'s' if total != 1 else ''}")
        for card in self.cards:
            cell = CardCardPanel(
                self.scroller,
                self.zone,
                card,
                self.icon_factory,
                self._get_metadata,
                self._owned_status,
                self._on_delta,
                self._on_remove,
                self._handle_card_click,
            )
            self.grid_sizer.Add(cell, 0, wx.EXPAND)
            self.card_widgets.append(cell)
        remainder = len(self.cards) % 4
        if remainder:
            for _ in range(4 - remainder):
                spacer = wx.Panel(self.scroller)
                spacer.SetBackgroundColour(DARK_PANEL)
                self.grid_sizer.Add(spacer, 0, wx.EXPAND)
        self.grid_sizer.Layout()
        self.scroller.Layout()
        self.scroller.FitInside()
        self._restore_selection()

    def _handle_card_click(self, zone: str, card: dict[str, Any], panel: CardCardPanel) -> None:
        """Handle card click event.

        Args:
            zone: Zone name
            card: Card dictionary
            panel: CardCardPanel that was clicked
        """
        if self.active_panel is panel:
            return
        if self.active_panel:
            self.active_panel.set_active(False)
        self.active_panel = panel
        self.selected_name = card["name"]
        panel.set_active(True)
        self._notify_selection(card)

    def _restore_selection(self) -> None:
        """Restore previously selected card after rebuild."""
        if not self.selected_name:
            self._notify_selection(None)
            return
        for widget in self.card_widgets:
            if widget.card["name"].lower() == self.selected_name.lower():
                self.active_panel = widget
                widget.set_active(True)
                self._notify_selection(widget.card)
                return
        previously_had_selection = self.selected_name is not None
        self.selected_name = None
        if previously_had_selection:
            self._notify_selection(None)

    def clear_selection(self) -> None:
        """Clear current card selection."""
        if self.active_panel:
            self.active_panel.set_active(False)
        self.active_panel = None
        self.selected_name = None
        self._notify_selection(None)

    def collapse_active(self) -> None:
        """Collapse active card panel without clearing selection."""
        if self.active_panel:
            self.active_panel.set_active(False)
        self.active_panel = None
        self.selected_name = None

    def _notify_selection(self, card: dict[str, Any] | None) -> None:
        """Notify parent of card selection change.

        Args:
            card: Selected card or None
        """
        if self._on_select:
            self._on_select(self.zone, card)
