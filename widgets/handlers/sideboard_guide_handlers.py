"""Sideboard guide and outboard handlers for the deck selector frame."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import wx

from widgets.dialogs.guide_entry_dialog import GuideEntryDialog

if TYPE_CHECKING:
    from widgets.app_frame import AppFrame


class SideboardGuideHandlers:
    """Mixin that centralizes guide/outboard interactions for the deck selector."""

    def _persist_outboard_for_current(self: AppFrame) -> None:
        key = self.controller.deck_repo.get_current_deck_key()
        self.controller.outboard_store[key] = self.zone_cards.get("out", [])
        self.controller.store_service.save_store(
            self.controller.outboard_store_path, self.controller.outboard_store
        )

    def _load_outboard_for_current(self: AppFrame) -> list[dict[str, Any]]:
        key = self.controller.deck_repo.get_current_deck_key()
        data = self.controller.outboard_store.get(key, [])
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

    def _load_guide_for_current(self: AppFrame) -> None:
        key = self.controller.deck_repo.get_current_deck_key()
        payload = self.controller.guide_store.get(key) or {}
        self.sideboard_guide_entries = payload.get("entries", [])
        self.sideboard_exclusions = payload.get("exclusions", [])
        self.sideboard_guide_panel.set_entries(
            self.sideboard_guide_entries, self.sideboard_exclusions
        )

    def _persist_guide_for_current(self: AppFrame) -> None:
        key = self.controller.deck_repo.get_current_deck_key()
        self.controller.guide_store[key] = {
            "entries": self.sideboard_guide_entries,
            "exclusions": self.sideboard_exclusions,
        }
        self.controller.store_service.save_store(
            self.controller.guide_store_path, self.controller.guide_store
        )

    def _refresh_guide_view(self: AppFrame) -> None:
        self.sideboard_guide_panel.set_entries(
            self.sideboard_guide_entries, self.sideboard_exclusions
        )

    def _on_add_guide_entry(self: AppFrame) -> None:
        names = [item.get("name", "") for item in self.archetypes]
        dlg = GuideEntryDialog(self, names)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_data()
            if data.get("archetype"):
                self.sideboard_guide_entries.append(data)
                self._persist_guide_for_current()
                self._refresh_guide_view()
        dlg.Destroy()

    def _on_edit_guide_entry(self: AppFrame) -> None:
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

    def _on_remove_guide_entry(self: AppFrame) -> None:
        index = self.sideboard_guide_panel.get_selected_index()
        if index is None:
            wx.MessageBox(
                "Select an entry to remove.", "Sideboard Guide", wx.OK | wx.ICON_INFORMATION
            )
            return
        del self.sideboard_guide_entries[index]
        self._persist_guide_for_current()
        self._refresh_guide_view()

    def _on_edit_exclusions(self: AppFrame) -> None:
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

    def _on_export_guide(self: AppFrame) -> None:
        wx.MessageBox(
            "Guide export is not yet implemented on this branch.",
            "Sideboard Guide",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _on_import_guide(self: AppFrame) -> None:
        wx.MessageBox(
            "Guide import is not yet implemented on this branch.",
            "Sideboard Guide",
            wx.OK | wx.ICON_INFORMATION,
        )
