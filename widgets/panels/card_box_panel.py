from collections.abc import Callable
from typing import Any

import wx

from utils.constants import DARK_ACCENT, DARK_ALT, LIGHT_TEXT
from utils.mana_icon_factory import ManaIconFactory


class CardBoxPanel(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        zone: str,
        card: dict[str, Any],
        icon_factory: ManaIconFactory,
        get_metadata: Callable[[str], dict[str, Any] | None],
        owned_status: Callable[[str, int], tuple[str, tuple[int, int, int]]],
        on_delta: Callable[[str, str, int], None],
        on_remove: Callable[[str, str], None],
        on_select: Callable[[str, dict[str, Any], "CardBoxPanel"], None],
        on_hover: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.zone = zone
        self.card = card
        self._get_metadata = get_metadata
        self._owned_status = owned_status
        self._on_delta = on_delta
        self._on_remove = on_remove
        self._on_select = on_select
        self._on_hover = on_hover
        self._active = False

        self.SetBackgroundColour(DARK_ALT)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(row)
        self.SetMinSize((-1, 34))

        base_font = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        # Quantity label
        self.qty_label = wx.StaticText(self, label=str(card["qty"]))
        self.qty_label.SetForegroundColour(LIGHT_TEXT)
        self.qty_label.SetFont(base_font)
        row.Add(self.qty_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        # Get metadata
        meta = get_metadata(card["name"]) or {}
        mana_cost = meta.get("mana_cost", "")

        # Owned status - convert fractional qty to int for collection check
        qty_value = card["qty"]
        qty_for_check = int(qty_value) if isinstance(qty_value, float) else qty_value
        _, owned_colour_rgb = owned_status(card["name"], qty_for_check)

        # Name label
        self.name_label = wx.StaticText(self, label=card["name"], style=wx.ST_NO_AUTORESIZE)
        self.name_label.SetForegroundColour(wx.Colour(*owned_colour_rgb))
        self.name_label.SetFont(base_font)
        self.name_label.Wrap(110)
        row.Add(self.name_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        # Mana cost icons
        mana_panel = icon_factory.render(self, mana_cost)
        row.Add(mana_panel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        # Button panel
        self.button_panel = wx.Panel(self)
        self.button_panel.SetBackgroundColour(DARK_ALT)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_panel.SetSizer(btn_sizer)
        add_btn = wx.Button(self.button_panel, label="+")
        self._style_action_button(add_btn)
        add_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_delta(zone, card["name"], 1))
        btn_sizer.Add(add_btn, 0)
        sub_btn = wx.Button(self.button_panel, label="−")
        self._style_action_button(sub_btn)
        sub_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_delta(zone, card["name"], -1))
        btn_sizer.Add(sub_btn, 0, wx.LEFT, 2)
        rem_btn = wx.Button(self.button_panel, label="×")
        self._style_action_button(rem_btn)
        rem_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_remove(zone, card["name"]))
        btn_sizer.Add(rem_btn, 0, wx.LEFT, 2)
        row.Add(self.button_panel, 0, wx.ALIGN_CENTER_VERTICAL)
        self.button_panel.Hide()

        # Bind click events to all widgets so clicks anywhere on the card work
        self._bind_click_targets([self, self.qty_label, self.name_label, mana_panel])
        self._bind_hover_targets(
            [self, self.qty_label, self.name_label, mana_panel, self.button_panel]
        )

    def update_quantity(
        self, qty: int | float, owned_text: str, owned_colour: tuple[int, int, int]
    ) -> None:
        self.qty_label.SetLabel(str(qty))
        self.name_label.SetForegroundColour(wx.Colour(*owned_colour))
        self.Layout()

    def set_active(self, active: bool) -> None:
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
        for target in targets:
            target.Bind(wx.EVT_LEFT_DOWN, self._handle_click)
            for child in target.GetChildren():
                child.Bind(wx.EVT_LEFT_DOWN, self._handle_click)

    def _bind_hover_targets(self, targets: list[wx.Window]) -> None:
        if self._on_hover is None:
            return
        for target in targets:
            target.Bind(wx.EVT_ENTER_WINDOW, self._handle_hover)
            for child in target.GetChildren():
                child.Bind(wx.EVT_ENTER_WINDOW, self._handle_hover)

    def _handle_click(self, _event: wx.MouseEvent) -> None:
        self._on_select(self.zone, self.card, self)

    def _handle_hover(self, _event: wx.MouseEvent) -> None:
        if self._on_hover:
            self._on_hover(self.zone, self.card)

    def _style_action_button(self, button: wx.Button) -> None:
        button.SetBackgroundColour(DARK_ACCENT)
        button.SetForegroundColour(wx.Colour(12, 14, 18))
        button.SetWindowStyleFlag(wx.BORDER_NONE)
        button.SetMinSize((28, 28))
        font = button.GetFont()
        font.MakeBold()
        button.SetFont(font)
