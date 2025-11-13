"""
Sideboard Guide Panel - Manages matchup-specific sideboarding strategies.

Allows users to create, edit, and manage guides for different matchups, including cards
to side in/out and matchup notes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import wx
import wx.dataview as dv

from utils.stylize import stylize_button
from utils.ui_constants import DARK_ALT, DARK_PANEL, LIGHT_TEXT, SUBDUED_TEXT
from widgets.dialogs.guide_entry_dialog import GuideEntryDialog

if TYPE_CHECKING:
    from widgets.deck_selector import MTGDeckSelectionFrame


class SideboardGuidePanel(wx.Panel):
    """Panel that manages sideboard guides for matchups."""

    def __init__(
        self,
        parent: wx.Window,
        deck_selector_frame: MTGDeckSelectionFrame,
    ):
        """
        Initialize the sideboard guide panel.

        Args:
            parent: Parent window
            deck_selector_frame: Reference to the main deck selector frame
        """
        super().__init__(parent)
        self.SetBackgroundColour(DARK_PANEL)

        self.deck_selector_frame = deck_selector_frame

        self.entries: list[dict[str, str]] = []
        self.exclusions: list[str] = []

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        # Guide entries list
        self.guide_view = dv.DataViewListCtrl(self, style=dv.DV_ROW_LINES)
        self.guide_view.AppendTextColumn("Archetype", width=200)
        self.guide_view.AppendTextColumn("Cards In", width=200)
        self.guide_view.AppendTextColumn("Cards Out", width=200)
        self.guide_view.AppendTextColumn("Notes", width=220)
        self.guide_view.SetBackgroundColour(DARK_ALT)
        self.guide_view.SetForegroundColour(LIGHT_TEXT)
        sizer.Add(self.guide_view, 1, wx.EXPAND | wx.ALL, 6)

        # Button row
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.add_btn = wx.Button(self, label="Add Entry")
        stylize_button(self.add_btn)
        self.add_btn.Bind(wx.EVT_BUTTON, self._on_add_clicked)
        buttons.Add(self.add_btn, 0, wx.RIGHT, 6)

        self.edit_btn = wx.Button(self, label="Edit Entry")
        stylize_button(self.edit_btn)
        self.edit_btn.Bind(wx.EVT_BUTTON, self._on_edit_clicked)
        buttons.Add(self.edit_btn, 0, wx.RIGHT, 6)

        self.remove_btn = wx.Button(self, label="Remove Entry")
        stylize_button(self.remove_btn)
        self.remove_btn.Bind(wx.EVT_BUTTON, self._on_remove_clicked)
        buttons.Add(self.remove_btn, 0, wx.RIGHT, 6)

        self.exclusions_btn = wx.Button(self, label="Exclude Archetypes")
        stylize_button(self.exclusions_btn)
        self.exclusions_btn.Bind(wx.EVT_BUTTON, self._on_exclusions_clicked)
        buttons.Add(self.exclusions_btn, 0)

        buttons.AddStretchSpacer(1)

        # Exclusions label
        self.exclusions_label = wx.StaticText(self, label="Exclusions: —")
        self.exclusions_label.SetForegroundColour(SUBDUED_TEXT)
        sizer.Add(self.exclusions_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

    # ============= Public API =============

    def set_entries(
        self, entries: list[dict[str, str]], exclusions: list[str] | None = None
    ) -> None:
        """
        Set the guide entries and exclusions.

        Args:
            entries: List of guide entry dictionaries
            exclusions: List of excluded archetype names
        """
        self.entries = entries
        self.exclusions = exclusions or []
        self._refresh_view()

    def get_entries(self) -> list[dict[str, str]]:
        """Get the current guide entries."""
        return self.entries

    def get_exclusions(self) -> list[str]:
        """Get the current excluded archetypes."""
        return self.exclusions

    def get_selected_index(self) -> int | None:
        """
        Get the index of the currently selected entry.

        Returns:
            Index of selected entry, or None if no selection
        """
        item = self.guide_view.GetSelection()
        if not item.IsOk():
            return None
        return self.guide_view.ItemToRow(item)

    def clear(self) -> None:
        """Clear all guide entries."""
        self.entries = []
        self.exclusions = []
        self._refresh_view()

    # ============= Private Methods =============

    def _refresh_view(self) -> None:
        """Refresh the guide view display."""
        self.guide_view.DeleteAllItems()

        # Add entries (skip excluded archetypes)
        for entry in self.entries:
            if entry.get("archetype") in self.exclusions:
                continue
            self.guide_view.AppendItem(
                [
                    entry.get("archetype", ""),
                    entry.get("cards_in", ""),
                    entry.get("cards_out", ""),
                    entry.get("notes", ""),
                ]
            )

        # Update exclusions label
        if self.exclusions:
            text = ", ".join(self.exclusions)
        else:
            text = "—"
        self.exclusions_label.SetLabel(f"Exclusions: {text}")

    def _on_add_clicked(self, _event: wx.Event) -> None:
        """Handle Add Entry button click."""
        self.deck_selector_frame._on_add_guide_entry()

    def _on_edit_clicked(self, _event: wx.Event) -> None:
        """Handle Edit Entry button click."""
        self.deck_selector_frame._on_edit_guide_entry()

    def _on_remove_clicked(self, _event: wx.Event) -> None:
        """Handle Remove Entry button click."""
        self.deck_selector_frame._on_remove_guide_entry()

    def _on_exclusions_clicked(self, _event: wx.Event) -> None:
        """Handle Exclude Archetypes button click."""
        self.deck_selector_frame._on_edit_exclusions()


class SideboardGuideHandlers:
    """Mixin that centralizes guide/outboard interactions for the deck selector."""

    def _persist_outboard_for_current(self) -> None:
        key = self._current_deck_key()
        self.outboard_store[key] = self.zone_cards.get("out", [])
        self._save_store(self.outboard_store_path, self.outboard_store)

    def _load_outboard_for_current(self) -> list[dict[str, Any]]:
        key = self._current_deck_key()
        data = self.outboard_store.get(key, [])
        cleaned: list[dict[str, Any]] = []
        for entry in data:
            name = entry.get("name")
            qty_raw = entry.get("qty", 0)
            try:
                qty_float = float(qty_raw)
                qty = int(qty_float) if qty_float.is_integer() else qty_float
            except (TypeError, ValueError):
                qty = 0
            if name and qty > 0:
                cleaned.append({"name": name, "qty": qty})
        return cleaned

    def _load_guide_for_current(self) -> None:
        key = self._current_deck_key()
        payload = self.guide_store.get(key) or {}
        self.sideboard_guide_entries = payload.get("entries", [])
        self.sideboard_exclusions = payload.get("exclusions", [])
        self.sideboard_guide_panel.set_entries(
            self.sideboard_guide_entries, self.sideboard_exclusions
        )

    def _persist_guide_for_current(self) -> None:
        key = self._current_deck_key()
        self.guide_store[key] = {
            "entries": self.sideboard_guide_entries,
            "exclusions": self.sideboard_exclusions,
        }
        self._save_store(self.guide_store_path, self.guide_store)

    def _refresh_guide_view(self) -> None:
        self.sideboard_guide_panel.set_entries(
            self.sideboard_guide_entries, self.sideboard_exclusions
        )

    def _on_add_guide_entry(self) -> None:
        names = [item.get("name", "") for item in self.archetypes]
        dlg = GuideEntryDialog(self, names)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_data()
            if data.get("archetype"):
                self.sideboard_guide_entries.append(data)
                self._persist_guide_for_current()
                self._refresh_guide_view()
        dlg.Destroy()

    def _on_edit_guide_entry(self) -> None:
        index = self.sideboard_guide_panel.get_selected_index()
        if index is None:
            wx.MessageBox(
                "Select an entry to edit.", "Sideboard Guide", wx.OK | wx.ICON_INFORMATION
            )
            return
        data = self.sideboard_guide_entries[index]
        names = [item.get("name", "") for item in self.archetypes]
        dlg = GuideEntryDialog(self, names, data=data)
        if dlg.ShowModal() == wx.ID_OK:
            updated = dlg.get_data()
            if updated.get("archetype"):
                self.sideboard_guide_entries[index] = updated
                self._persist_guide_for_current()
                self._refresh_guide_view()
        dlg.Destroy()

    def _on_remove_guide_entry(self) -> None:
        index = self.sideboard_guide_panel.get_selected_index()
        if index is None:
            wx.MessageBox(
                "Select an entry to remove.", "Sideboard Guide", wx.OK | wx.ICON_INFORMATION
            )
            return
        del self.sideboard_guide_entries[index]
        self._persist_guide_for_current()
        self._refresh_guide_view()

    def _on_edit_exclusions(self) -> None:
        archetype_names = [item.get("name", "") for item in self.archetypes]
        dlg = wx.MultiChoiceDialog(
            self,
            "Select archetypes to exclude from the printed guide.",
            "Sideboard Guide",
            archetype_names,
        )
        selected_indices = [
            archetype_names.index(name)
            for name in self.sideboard_exclusions
            if name in archetype_names
        ]
        dlg.SetSelections(selected_indices)
        if dlg.ShowModal() == wx.ID_OK:
            selections = dlg.GetSelections()
            self.sideboard_exclusions = [archetype_names[idx] for idx in selections]
            self._persist_guide_for_current()
            self._refresh_guide_view()
        dlg.Destroy()
