from __future__ import annotations

from collections.abc import Callable
from typing import Any

import wx
import wx.dataview as dv

from services.radar_service import RadarData
from utils.constants import DARK_ALT, DARK_PANEL, FORMAT_OPTIONS, LIGHT_TEXT, SUBDUED_TEXT
from utils.mana_icon_factory import ManaIconFactory
from utils.stylize import (
    stylize_button,
    stylize_choice,
    stylize_label,
    stylize_textctrl,
)
from widgets.buttons.mana_button import create_mana_button


class _SearchResultsView(dv.DataViewListCtrl):
    """DataViewListCtrl with legacy ListCtrl helpers used by tests."""

    def GetItemText(self, row: int, col: int = 0) -> str:
        return self.GetTextValue(row, col)


class DeckBuilderPanel(wx.Panel):
    """Panel for searching and filtering MTG cards by various properties."""

    _MANA_ICON_SCALE = 1  # deck search display needs icons reduced by 70%

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
        on_open_radar_dialog: Callable[[], RadarData | None] | None = None,
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
        self._on_open_radar_dialog = on_open_radar_dialog

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

        # Infinite scroll state
        self._all_results: list[dict[str, Any]] = []
        self._window_size: int = 300
        self._window_start: int = 0
        self._scroll_threshold: int = 50
        self._last_scroll_pos: int = 0

        # Radar state
        self.active_radar: RadarData | None = None
        self.radar_enabled: bool = False
        self.radar_zone: str = "both"  # "mainboard", "sideboard", or "both"

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
        controls.Add(clear_btn, 0, wx.RIGHT, 6)

        # Radar toggle checkbox
        self.radar_cb = wx.CheckBox(self, label="Use Radar Filter")
        self.radar_cb.SetForegroundColour(LIGHT_TEXT)
        self.radar_cb.SetBackgroundColour(DARK_PANEL)
        self.radar_cb.Bind(wx.EVT_CHECKBOX, self._on_radar_toggle)
        controls.Add(self.radar_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        # Radar zone choice
        self.radar_zone_choice = wx.Choice(self, choices=["Both", "Mainboard", "Sideboard"])
        self.radar_zone_choice.SetSelection(0)
        stylize_choice(self.radar_zone_choice)
        self.radar_zone_choice.Enable(False)
        self.radar_zone_choice.Bind(wx.EVT_CHOICE, self._on_radar_zone_changed)
        controls.Add(self.radar_zone_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        # Open Radar button
        self.open_radar_btn = wx.Button(self, label="Open Radar...")
        stylize_button(self.open_radar_btn)
        self.open_radar_btn.Bind(wx.EVT_BUTTON, self._on_open_radar)
        controls.Add(self.open_radar_btn, 0)

        controls.AddStretchSpacer(1)
        sizer.Add(controls, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Results list
        results = _SearchResultsView(self, style=dv.DV_ROW_LINES | dv.DV_SINGLE)
        results.AppendTextColumn("Name", width=230)
        results.AppendIconTextColumn("Mana", width=120)
        results.SetBackgroundColour(DARK_ALT)
        results.SetForegroundColour(LIGHT_TEXT)
        results.Bind(dv.EVT_DATAVIEW_SELECTION_CHANGED, self._on_result_item_selected)
        results.Bind(wx.EVT_SCROLLWIN, self._on_scroll)
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

        # Add radar filter if enabled
        filters["radar_enabled"] = self.radar_enabled
        if self.radar_enabled and self.active_radar:
            from services.radar_service import get_radar_service

            radar_service = get_radar_service()
            filters["radar_cards"] = radar_service.get_radar_card_names(
                self.active_radar, self.radar_zone
            )
        else:
            filters["radar_cards"] = set()

        return filters

    def clear_filters(self) -> None:
        """Clear all filter controls."""
        for ctrl in self.inputs.values():
            ctrl.ChangeValue("")
        self.results_cache = []
        self._all_results = []
        self._window_start = 0
        self._mana_icon_cache.clear()

        if self.results_ctrl:
            self.results_ctrl.DeleteAllItems()

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

        # Clear radar filter
        self.radar_enabled = False
        self.active_radar = None
        if hasattr(self, "radar_cb"):
            self.radar_cb.SetValue(False)
            self.radar_zone_choice.Enable(False)

    def update_results(self, results: list[dict[str, Any]]) -> None:
        """Update the results list with search results."""
        self._all_results = results
        self._window_start = 0
        self.results_cache = []
        if not self.results_ctrl:
            return
        self._load_window()
        if self.status_label:
            count = len(results)
            visible = len(self.results_cache)
            if count > self._window_size:
                self.status_label.SetLabel(
                    f"Showing {visible} of {count} card{'s' if count != 1 else ''} (scroll for more)."
                )
            else:
                self.status_label.SetLabel(f"Showing {count} card{'s' if count != 1 else ''}.")

    def get_result_at_index(self, idx: int) -> dict[str, Any] | None:
        """Get the result card data at the given index (relative to visible window)."""
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

    def _on_scroll(self, event: wx.ScrollWinEvent) -> None:
        """Handle scroll events to implement infinite scroll."""
        event.Skip()
        if not self.results_ctrl or not self._all_results:
            return

        wx.CallAfter(self._check_scroll_position)

    def _check_scroll_position(self) -> None:
        """Check scroll position and load more items if needed."""
        if not self.results_ctrl or not self._all_results:
            return

        total_items = self.results_ctrl.GetItemCount()
        if total_items == 0:
            return

        first_visible = self._get_first_visible_item()
        last_visible = self._get_last_visible_item()

        if first_visible == -1 or last_visible == -1:
            return

        items_from_top = first_visible
        items_from_bottom = total_items - last_visible - 1

        can_load_up = self._window_start > 0
        can_load_down = self._window_start + len(self.results_cache) < len(self._all_results)

        load_more_up = items_from_top < self._scroll_threshold and can_load_up
        load_more_down = items_from_bottom < self._scroll_threshold and can_load_down

        if load_more_up:
            self._shift_window_up()
        elif load_more_down:
            self._shift_window_down()

    def _get_first_visible_item(self) -> int:
        """Get the index of the first visible item in the results list."""
        if not self.results_ctrl:
            return -1

        for i in range(self.results_ctrl.GetItemCount()):
            item = self.results_ctrl.RowToItem(i)
            if item.IsOk():
                rect = self.results_ctrl.GetItemRect(item)
                if rect.GetTop() >= 0:
                    return i
        return 0

    def _get_last_visible_item(self) -> int:
        """Get the index of the last visible item in the results list."""
        if not self.results_ctrl:
            return -1

        client_height = self.results_ctrl.GetClientSize().GetHeight()
        last_visible = -1

        for i in range(self.results_ctrl.GetItemCount()):
            item = self.results_ctrl.RowToItem(i)
            if item.IsOk():
                rect = self.results_ctrl.GetItemRect(item)
                if rect.GetTop() < client_height:
                    last_visible = i
                else:
                    break

        return last_visible

    def _load_window(self) -> None:
        """Load the current window of results into the UI."""
        if not self.results_ctrl:
            return

        window_end = min(self._window_start + self._window_size, len(self._all_results))
        self.results_cache = self._all_results[self._window_start : window_end]

        self.results_ctrl.DeleteAllItems()
        for _idx, card in enumerate(self.results_cache):
            name = card.get("name", "Unknown")
            mana_cost = card.get("mana_cost") or ""
            icon_text = self._get_mana_icon_text(mana_cost)
            self.results_ctrl.AppendItem([name, icon_text])

    def _shift_window_up(self) -> None:
        """Shift the viewing window up to load earlier results."""
        if self._window_start <= 0:
            return

        new_start = max(0, self._window_start - self._window_size)
        self._window_start = new_start
        self._load_window()

    def _shift_window_down(self) -> None:
        """Shift the viewing window down to load later results."""
        max_start = max(0, len(self._all_results) - self._window_size)
        if self._window_start >= max_start:
            return

        new_start = min(max_start, self._window_start + self._window_size)
        self._window_start = new_start
        self._load_window()

    def _get_mana_icon_text(self, mana_cost: str) -> dv.DataViewIconText:
        """Return cached icon text object for a mana cost."""
        cost_key = mana_cost.strip()
        cache_key = f"{cost_key}|{self._MANA_ICON_SCALE}"
        if cache_key in self._mana_icon_cache:
            return self._mana_icon_cache[cache_key]
        bitmap = self.mana_icons.bitmap_for_cost(cost_key)
        if bitmap:
            bitmap = self._scale_bitmap(bitmap, self._MANA_ICON_SCALE)
            icon = wx.Icon()
            icon.CopyFromBitmap(bitmap)
            value = dv.DataViewIconText("", icon)
        else:
            value = dv.DataViewIconText("—", wx.NullIcon)
        self._mana_icon_cache[cache_key] = value
        return value

    def _scale_bitmap(self, bitmap: wx.Bitmap, scale: float) -> wx.Bitmap:
        """Return a bitmap scaled by the provided factor."""
        if scale <= 0:
            return bitmap
        width = max(1, int(bitmap.GetWidth() * scale))
        height = max(1, int(bitmap.GetHeight() * scale))
        if width == bitmap.GetWidth() and height == bitmap.GetHeight():
            return bitmap
        image = bitmap.ConvertToImage()
        scaled = image.Scale(width, height, wx.IMAGE_QUALITY_HIGH)
        return wx.Bitmap(scaled)

    # ============= Radar Integration =============

    def _on_radar_toggle(self, event: wx.Event) -> None:
        """Handle radar filter checkbox toggle."""
        self.radar_enabled = self.radar_cb.IsChecked()
        self.radar_zone_choice.Enable(self.radar_enabled)

        if self.radar_enabled and not self.active_radar:
            wx.MessageBox(
                "Please open a radar using the 'Open Radar...' button.",
                "No Radar Loaded",
                wx.OK | wx.ICON_INFORMATION,
            )
            self.radar_cb.SetValue(False)
            self.radar_enabled = False
            self.radar_zone_choice.Enable(False)

    def _on_radar_zone_changed(self, event: wx.Event) -> None:
        """Handle radar zone selection change."""
        selection = self.radar_zone_choice.GetSelection()
        zone_map = {0: "both", 1: "mainboard", 2: "sideboard"}
        self.radar_zone = zone_map.get(selection, "both")

    def _on_open_radar(self, event: wx.Event) -> None:
        """Handle open radar button click."""
        if self._on_open_radar_dialog:
            radar = self._on_open_radar_dialog()
            if radar:
                self.set_active_radar(radar)

    def set_active_radar(self, radar: RadarData) -> None:
        """
        Set the active radar for filtering.

        Args:
            radar: RadarData to use for filtering
        """
        self.active_radar = radar
        self.radar_enabled = True
        self.radar_cb.SetValue(True)
        self.radar_zone_choice.Enable(True)

        if self.status_label:
            self.status_label.SetLabel(
                f"Radar active: {radar.archetype_name} "
                f"({len(radar.mainboard_cards)} MB, {len(radar.sideboard_cards)} SB cards)"
            )
