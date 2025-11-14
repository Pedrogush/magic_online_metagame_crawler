from collections.abc import Callable
from typing import Any

import wx
import wx.dataview as dv

from utils.game_constants import FORMAT_OPTIONS
from utils.mana_icon_factory import ManaIconFactory
from utils.stylize import (
    stylize_button,
    stylize_choice,
    stylize_label,
    stylize_textctrl,
)
from utils.ui_constants import DARK_ALT, DARK_PANEL, LIGHT_TEXT, SUBDUED_TEXT
from widgets.buttons.mana_button import create_mana_button


class _SearchResultsView(dv.DataViewListCtrl):
    """DataViewListCtrl with legacy ListCtrl helpers used by tests."""

    def GetItemText(self, row: int, col: int = 0) -> str:
        return self.GetTextValue(row, col)


class DeckBuilderPanel(wx.Panel):
    """Panel for searching and filtering MTG cards by various properties."""

    def __init__(
        self,
        parent: wx.Window,
        mana_icons: ManaIconFactory,
        on_switch_to_research: Callable[[], None],
        on_ensure_card_data: Callable[[], None],
        open_mana_keyboard: Callable[[], None],
        on_search: Callable[[], None],
        on_clear: Callable[[], None],
        on_result_selected: Callable[[int], None],
    ) -> None:
        super().__init__(parent)

        # Store dependencies
        self.mana_icons = mana_icons
        self._on_switch_to_research = on_switch_to_research
        self._on_ensure_card_data = on_ensure_card_data
        self._open_mana_keyboard = open_mana_keyboard
        self._on_search_callback = on_search
        self._on_clear_callback = on_clear
        self._on_result_selected_callback = on_result_selected

        # State variables
        self.inputs: dict[str, wx.TextCtrl] = {}
        self.mana_exact_cb: wx.CheckBox | None = None
        self.mv_comparator: wx.Choice | None = None
        self.mv_value: wx.TextCtrl | None = None
        self.format_checks: list[wx.CheckBox] = []
        self.color_checks: dict[str, wx.CheckBox] = {}
        self.color_mode_choice: wx.Choice | None = None
        self.results_ctrl: dv.DataViewListCtrl | None = None
        self.status_label: wx.StaticText | None = None
        self.results_cache: list[dict[str, Any]] = []
        self._mana_icon_cache: dict[str, dv.DataViewIconText] = {}

        # Build the UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the complete UI for the deck builder panel."""
        self.SetBackgroundColour(DARK_PANEL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        # Back button
        back_btn = wx.Button(self, label="Deck Research")
        stylize_button(back_btn)
        back_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_back_clicked())
        sizer.Add(back_btn, 0, wx.EXPAND | wx.ALL, 6)

        # Info label
        info = wx.StaticText(self, label="Deck Builder: search MTG cards by property.")
        stylize_label(info, True)
        sizer.Add(info, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Search fields
        field_specs = [
            ("name", "Card Name", "e.g. Ragavan"),
            ("type", "Type Line", "Artifact Creature"),
            ("mana", "Mana Cost", "Curly braces like {1}{G} or shorthand (e.g. GGG)"),
            ("text", "Oracle Text", "Keywords or abilities"),
        ]
        for key, label_text, hint in field_specs:
            lbl = wx.StaticText(self, label=label_text)
            stylize_label(lbl, True)
            sizer.Add(lbl, 0, wx.LEFT | wx.RIGHT, 6)
            ctrl = wx.TextCtrl(self)
            stylize_textctrl(ctrl)
            ctrl.SetHint(hint)
            sizer.Add(ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
            self.inputs[key] = ctrl

            # Mana cost field gets extra controls
            if key == "mana":
                # Exact match checkbox
                match_row = wx.BoxSizer(wx.HORIZONTAL)
                match_label = wx.StaticText(self, label="Match")
                stylize_label(match_label, True)
                match_row.Add(match_label, 0, wx.RIGHT, 6)
                exact_cb = wx.CheckBox(self, label="Exact symbols")
                exact_cb.SetForegroundColour(LIGHT_TEXT)
                exact_cb.SetBackgroundColour(DARK_PANEL)
                match_row.Add(exact_cb, 0)
                self.mana_exact_cb = exact_cb
                match_row.AddStretchSpacer(1)
                sizer.Add(match_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

                # Mana symbol keyboard
                keyboard_row = wx.BoxSizer(wx.HORIZONTAL)
                keyboard_row.AddStretchSpacer(1)
                for token in ["W", "U", "B", "R", "G", "C", "X"]:
                    btn = create_mana_button(self, token, self._append_mana_symbol, self.mana_icons)
                    keyboard_row.Add(btn, 0, wx.ALL, 2)
                all_btn = wx.Button(self, label="All", size=(52, 28))
                stylize_button(all_btn)
                all_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._open_mana_keyboard())
                keyboard_row.Add(all_btn, 0, wx.ALL, 2)
                keyboard_row.AddStretchSpacer(1)
                sizer.Add(
                    keyboard_row, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4
                )

        # Mana value filter
        mv_row = wx.BoxSizer(wx.HORIZONTAL)
        mv_label = wx.StaticText(self, label="Mana Value Filter")
        stylize_label(mv_label, True)
        mv_row.Add(mv_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        mv_choice = wx.Choice(self, choices=["Any", "<", "≤", "=", "≥", ">"])
        mv_choice.SetSelection(0)
        stylize_choice(mv_choice)
        self.mv_comparator = mv_choice
        mv_row.Add(mv_choice, 0, wx.RIGHT, 6)
        mv_value = wx.TextCtrl(self)
        stylize_textctrl(mv_value)
        mv_value.SetHint("e.g. 3")
        self.mv_value = mv_value
        mv_row.Add(mv_value, 1)
        sizer.Add(mv_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Format checkboxes
        formats_label = wx.StaticText(self, label="Formats")
        stylize_label(formats_label, True)
        sizer.Add(formats_label, 0, wx.LEFT | wx.RIGHT, 6)
        formats_grid = wx.FlexGridSizer(0, 2, 4, 8)
        for fmt in FORMAT_OPTIONS:
            cb = wx.CheckBox(self, label=fmt)
            cb.SetForegroundColour(LIGHT_TEXT)
            cb.SetBackgroundColour(DARK_PANEL)
            formats_grid.Add(cb, 0, wx.RIGHT, 6)
            self.format_checks.append(cb)
        sizer.Add(formats_grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Color identity filter
        color_label = wx.StaticText(self, label="Color Identity Filter")
        stylize_label(color_label, True)
        sizer.Add(color_label, 0, wx.LEFT | wx.RIGHT, 6)

        color_mode = wx.Choice(self, choices=["Any", "At least", "Exactly", "Not these"])
        color_mode.SetSelection(0)
        stylize_choice(color_mode)
        self.color_mode_choice = color_mode
        sizer.Add(color_mode, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        colors_row = wx.BoxSizer(wx.HORIZONTAL)
        for code, label in [
            ("W", "White"),
            ("U", "Blue"),
            ("B", "Black"),
            ("R", "Red"),
            ("G", "Green"),
            ("C", "Colorless"),
        ]:
            cb = wx.CheckBox(self, label=label)
            cb.SetForegroundColour(LIGHT_TEXT)
            cb.SetBackgroundColour(DARK_PANEL)
            colors_row.Add(cb, 0, wx.RIGHT, 6)
            self.color_checks[code] = cb
        sizer.Add(colors_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Search and clear buttons
        controls = wx.BoxSizer(wx.HORIZONTAL)
        search_btn = wx.Button(self, label="Search Cards")
        stylize_button(search_btn)
        search_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_search())
        controls.Add(search_btn, 0, wx.RIGHT, 6)
        clear_btn = wx.Button(self, label="Clear Filters")
        stylize_button(clear_btn)
        clear_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_clear())
        controls.Add(clear_btn, 0)
        controls.AddStretchSpacer(1)
        sizer.Add(controls, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Results list
        results = _SearchResultsView(self, style=dv.DV_ROW_LINES | dv.DV_SINGLE)
        results.AppendTextColumn("Name", width=230)
        results.AppendIconTextColumn("Mana", width=120)
        results.SetBackgroundColour(DARK_ALT)
        results.SetForegroundColour(LIGHT_TEXT)
        results.Bind(dv.EVT_DATAVIEW_SELECTION_CHANGED, self._on_result_item_selected)
        sizer.Add(results, 1, wx.EXPAND | wx.ALL, 6)
        self.results_ctrl = results

        # Status label
        status = wx.StaticText(self, label="Search for cards to populate this list.")
        status.SetForegroundColour(SUBDUED_TEXT)
        sizer.Add(status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        self.status_label = status

    def _on_back_clicked(self) -> None:
        """Handle back button click."""
        self._on_switch_to_research()

    def _on_result_item_selected(self, event: dv.DataViewEvent) -> None:
        """Handle result list item selection."""
        if not self.results_ctrl:
            return
        item = event.GetItem()
        if not item.IsOk():
            return
        idx = self.results_ctrl.ItemToRow(item)
        if idx == wx.NOT_FOUND:
            return
        self._on_result_selected(idx)

    def _append_mana_symbol(self, token: str) -> None:
        """Append a mana symbol to the mana cost field."""
        ctrl = self.inputs.get("mana")
        if not ctrl:
            return
        symbol = token.strip().upper()
        if not symbol:
            return
        text = symbol if symbol.startswith("{") else f"{{{symbol}}}"
        ctrl.ChangeValue(ctrl.GetValue() + text)
        ctrl.SetFocus()

    def get_filters(self) -> dict[str, Any]:
        """Get all current filter values."""
        filters = {key: ctrl.GetValue().strip() for key, ctrl in self.inputs.items()}
        filters["mana_exact"] = self.mana_exact_cb.IsChecked() if self.mana_exact_cb else False
        filters["mv_comparator"] = (
            self.mv_comparator.GetStringSelection() if self.mv_comparator else "Any"
        )
        mv_value_text = self.mv_value.GetValue().strip() if self.mv_value else ""
        filters["mv_value"] = mv_value_text
        filters["formats"] = [cb.GetLabel().lower() for cb in self.format_checks if cb.IsChecked()]
        filters["color_mode"] = (
            self.color_mode_choice.GetStringSelection() if self.color_mode_choice else "Any"
        )
        filters["selected_colors"] = [
            code for code, cb in self.color_checks.items() if cb.IsChecked()
        ]
        return filters

    def clear_filters(self) -> None:
        """Clear all filter controls."""
        for ctrl in self.inputs.values():
            ctrl.ChangeValue("")
        self.results_cache = []
        self._mana_icon_cache.clear()

        if self.status_label:
            self.status_label.SetLabel("Filters cleared.")
        if self.mana_exact_cb:
            self.mana_exact_cb.SetValue(False)
        if self.mv_comparator:
            self.mv_comparator.SetSelection(0)
        if self.mv_value:
            self.mv_value.ChangeValue("")
        for cb in self.format_checks:
            cb.SetValue(False)
        if self.color_mode_choice:
            self.color_mode_choice.SetSelection(0)
        for cb in self.color_checks.values():
            cb.SetValue(False)

    def update_results(self, results: list[dict[str, Any]]) -> None:
        """Update the results list with search results."""
        self.results_cache = results
        if not self.results_ctrl:
            return
        self.results_ctrl.DeleteAllItems()
        for _idx, card in enumerate(results):
            name = card.get("name", "Unknown")
            mana_cost = card.get("mana_cost") or ""
            icon_text = self._get_mana_icon_text(mana_cost)
            self.results_ctrl.AppendItem([name, icon_text])
        if self.status_label:
            count = len(results)
            self.status_label.SetLabel(f"Showing {count} card{'s' if count != 1 else ''}.")

    def get_result_at_index(self, idx: int) -> dict[str, Any] | None:
        """Get the result card data at the given index."""
        if idx < 0 or idx >= len(self.results_cache):
            return None
        return self.results_cache[idx]

    def _on_search(self) -> None:
        """Handle search button click."""
        self._on_search_callback()

    def _on_clear(self) -> None:
        """Handle clear button click."""
        self._on_clear_callback()

    def _on_result_selected(self, idx: int) -> None:
        """Handle result list item selection."""
        self._on_result_selected_callback(idx)

    def _get_mana_icon_text(self, mana_cost: str) -> dv.DataViewIconText:
        """Return cached icon text object for a mana cost."""
        cost_key = mana_cost.strip()
        if cost_key in self._mana_icon_cache:
            return self._mana_icon_cache[cost_key]
        bitmap = self.mana_icons.bitmap_for_cost(cost_key)
        if bitmap:
            icon = wx.Icon()
            icon.CopyFromBitmap(bitmap)
            value = dv.DataViewIconText("", icon)
        else:
            value = dv.DataViewIconText("—", wx.NullIcon)
        self._mana_icon_cache[cost_key] = value
        return value
