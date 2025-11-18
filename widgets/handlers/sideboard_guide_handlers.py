"""Sideboard guide and outboard handlers for the deck selector frame."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import wx

from widgets.dialogs.guide_entry_dialog import GuideEntryDialog

if TYPE_CHECKING:
    from widgets.deck_selector import MTGDeckSelectionFrame


class SideboardGuideHandlers:
    """Mixin that centralizes guide/outboard interactions for the deck selector."""

    def _persist_outboard_for_current(self: MTGDeckSelectionFrame) -> None:
        key = self.deck_repo.get_current_deck_key()
        self.outboard_store[key] = self.zone_cards.get("out", [])
        self.store_service.save_store(self.outboard_store_path, self.outboard_store)

    def _load_outboard_for_current(self: MTGDeckSelectionFrame) -> list[dict[str, Any]]:
        key = self.deck_repo.get_current_deck_key()
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

    def _load_guide_for_current(self: MTGDeckSelectionFrame) -> None:
        key = self.deck_repo.get_current_deck_key()
        payload = self.guide_store.get(key) or {}
        entries = payload.get("entries", [])

        # Migrate old format entries to new format
        migrated_entries = []
        for entry in entries:
            # Check if entry is in old format (has cards_in/cards_out instead of play_*/draw_*)
            if "cards_in" in entry or "cards_out" in entry:
                # Migrate to new format: copy cards_in/out to both play and draw scenarios
                migrated_entry = {
                    "archetype": entry.get("archetype", ""),
                    "play_out": entry.get("cards_out", ""),
                    "play_in": entry.get("cards_in", ""),
                    "draw_out": entry.get("cards_out", ""),
                    "draw_in": entry.get("cards_in", ""),
                    "notes": entry.get("notes", ""),
                }
                migrated_entries.append(migrated_entry)
            else:
                # Already in new format
                migrated_entries.append(entry)

        self.sideboard_guide_entries = migrated_entries
        self.sideboard_exclusions = payload.get("exclusions", [])
        self.sideboard_guide_panel.set_entries(
            self.sideboard_guide_entries, self.sideboard_exclusions
        )

    def _persist_guide_for_current(self: MTGDeckSelectionFrame) -> None:
        key = self.deck_repo.get_current_deck_key()
        self.guide_store[key] = {
            "entries": self.sideboard_guide_entries,
            "exclusions": self.sideboard_exclusions,
        }
        self.store_service.save_store(self.guide_store_path, self.guide_store)

    def _refresh_guide_view(self: MTGDeckSelectionFrame) -> None:
        self.sideboard_guide_panel.set_entries(
            self.sideboard_guide_entries, self.sideboard_exclusions
        )

    def _on_add_guide_entry(self: MTGDeckSelectionFrame) -> None:
        names = [item.get("name", "") for item in self.archetypes]
        dlg = GuideEntryDialog(self, names)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_data()
            if data.get("archetype"):
                self.sideboard_guide_entries.append(data)
                self._persist_guide_for_current()
                self._refresh_guide_view()
        dlg.Destroy()

    def _on_edit_guide_entry(self: MTGDeckSelectionFrame) -> None:
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

    def _on_remove_guide_entry(self: MTGDeckSelectionFrame) -> None:
        index = self.sideboard_guide_panel.get_selected_index()
        if index is None:
            wx.MessageBox(
                "Select an entry to remove.", "Sideboard Guide", wx.OK | wx.ICON_INFORMATION
            )
            return
        del self.sideboard_guide_entries[index]
        self._persist_guide_for_current()
        self._refresh_guide_view()

    def _on_edit_exclusions(self: MTGDeckSelectionFrame) -> None:
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
