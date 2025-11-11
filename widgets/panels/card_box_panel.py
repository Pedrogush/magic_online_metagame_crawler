import wx

from collections.abc import Callable
from utils.constants import DARK_ALT, DARK_ACCENT, LIGHT_TEXT
from utils.mana_icon_factory import ManaIconFactory
from typing import Any


class CardBoxPanel(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        zone: str,
        card: dict[str, Any],
        icon_factory: ManaIconFactory,
        get_metadata: Callable[[str], dict[str, Any] | None],
        owned_status: Callable[[str, int], tuple[str, wx.Colour]],
        on_delta: Callable[[str, str, int], None],
        on_remove: Callable[[str, str], None],
        on_select: Callable[[str, dict[str, Any], "CardBoxPanel"], None],
    ) -> None:
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

        _, owned_colour = owned_status(card["name"], card["qty"])
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
        self.qty_label.SetLabel(str(qty))
        self.name_label.SetForegroundColour(owned_colour)
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

    def _handle_click(self, _event: wx.MouseEvent) -> None:
        self._on_select(self.zone, self.card, self)