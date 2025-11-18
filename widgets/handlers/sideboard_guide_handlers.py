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
        # Use decklist hash to ensure each unique 75 gets its own guide
        key = self.deck_repo.get_current_decklist_hash()
        payload = self.guide_store.get(key) or {}
        entries = payload.get("entries", [])

        # Migrate old format entries to new format
        migrated_entries = []
        for entry in entries:
            # Check if entry is in old format (has cards_in/cards_out as strings)
            if "cards_in" in entry or "cards_out" in entry:
                # Convert text format to dict format
                play_out = self._parse_card_text(entry.get("cards_out", ""))
                play_in = self._parse_card_text(entry.get("cards_in", ""))
                migrated_entry = {
                    "archetype": entry.get("archetype", ""),
                    "play_out": play_out,
                    "play_in": play_in,
                    "draw_out": play_out.copy(),  # Duplicate for draw
                    "draw_in": play_in.copy(),  # Duplicate for draw
                    "notes": entry.get("notes", ""),
                }
                migrated_entries.append(migrated_entry)
            else:
                # Check if new format has string values (needs parsing)
                migrated_entry = entry.copy()
                for field in ["play_out", "play_in", "draw_out", "draw_in"]:
                    if field in migrated_entry and isinstance(migrated_entry[field], str):
                        migrated_entry[field] = self._parse_card_text(migrated_entry[field])
                migrated_entries.append(migrated_entry)

        self.sideboard_guide_entries = migrated_entries
        self.sideboard_exclusions = payload.get("exclusions", [])
        self.sideboard_guide_panel.set_entries(
            self.sideboard_guide_entries, self.sideboard_exclusions
        )

    def _parse_card_text(self: MTGDeckSelectionFrame, text: str) -> dict[str, int]:
        """
        Parse card text like "2x Lightning Bolt, 1x Mountain" into a dict.

        Args:
            text: Card list in text format

        Returns:
            Dict mapping card name to quantity
        """
        if not text or not isinstance(text, str):
            return {}

        result = {}
        lines = text.replace(",", "\n").split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Try to parse "2x Card Name" or "2 Card Name" format
            parts = line.split(None, 1)
            if len(parts) == 2:
                qty_str, name = parts
                # Remove 'x' suffix if present
                qty_str = qty_str.rstrip("x")
                try:
                    qty = int(qty_str)
                    result[name.strip()] = qty
                    continue
                except ValueError:
                    pass

            # Fallback: treat whole line as card name with qty 1
            if line:
                result[line] = 1

        return result

    def _persist_guide_for_current(self: MTGDeckSelectionFrame) -> None:
        # Use decklist hash to ensure each unique 75 gets its own guide
        key = self.deck_repo.get_current_decklist_hash()
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
        mainboard = self.zone_cards.get("main", [])
        sideboard = self.zone_cards.get("side", [])

        dlg = GuideEntryDialog(self, names, mainboard, sideboard)

        # Keep dialog open for "Save & Continue" workflow
        while True:
            result = dlg.ShowModal()

            if result == wx.ID_CANCEL:
                break

            # Get data (for both OK and Save & Continue)
            data = dlg.get_data()
            if data.get("archetype"):
                self.sideboard_guide_entries.append(data)
                self._persist_guide_for_current()
                self._refresh_guide_view()

            if result == wx.ID_OK:
                # User clicked OK - close dialog
                break

            # result == wx.ID_APPLY (Save & Continue) - loop continues with dialog open

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
        mainboard = self.zone_cards.get("main", [])
        sideboard = self.zone_cards.get("side", [])

        dlg = GuideEntryDialog(self, names, mainboard, sideboard, data=data)
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

    def _on_export_guide_csv(self: MTGDeckSelectionFrame) -> None:
        """Export sideboard guide to CSV format."""
        if not self.sideboard_guide_entries:
            wx.MessageBox(
                "No sideboard guide entries to export.", "Export CSV", wx.OK | wx.ICON_INFORMATION
            )
            return

        # Ask user for save location
        dlg = wx.FileDialog(
            self,
            "Export Sideboard Guide",
            wildcard="CSV files (*.csv)|*.csv",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )

        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return

        file_path = dlg.GetPath()
        dlg.Destroy()

        try:
            self._export_guide_to_csv(file_path)
            wx.MessageBox(
                f"Sideboard guide exported successfully to:\n{file_path}",
                "Export CSV",
                wx.OK | wx.ICON_INFORMATION,
            )
        except Exception as e:
            wx.MessageBox(f"Error exporting CSV:\n{e}", "Export CSV", wx.OK | wx.ICON_ERROR)

    def _export_guide_to_csv(self: MTGDeckSelectionFrame, file_path: str) -> None:
        """
        Export sideboard guide to CSV with smart filtering.

        Creates a table where:
        - Rows are cards
        - Columns are matchups (archetypes)
        - Cells show "Out" for cards taken out, "In" for cards brought in
        - Cards that never appear are filtered out
        """
        import csv

        # Collect all cards and their actions per archetype
        card_actions: dict[str, dict[str, set[str]]] = {}  # card_name -> archetype -> {actions}

        for entry in self.sideboard_guide_entries:
            if entry.get("archetype") in self.sideboard_exclusions:
                continue

            archetype = entry.get("archetype", "Unknown")

            # Process play/draw scenarios
            for scenario, out_key, in_key in [
                ("Play", "play_out", "play_in"),
                ("Draw", "draw_out", "draw_in"),
            ]:
                out_cards = entry.get(out_key, {})
                in_cards = entry.get(in_key, {})

                if isinstance(out_cards, dict):
                    for card_name, qty in out_cards.items():
                        if qty > 0:
                            card_actions.setdefault(card_name, {}).setdefault(
                                f"{archetype} ({scenario})", set()
                            ).add(f"Out {qty}")

                if isinstance(in_cards, dict):
                    for card_name, qty in in_cards.items():
                        if qty > 0:
                            card_actions.setdefault(card_name, {}).setdefault(
                                f"{archetype} ({scenario})", set()
                            ).add(f"In {qty}")

        # Filter out cards that never appear
        filtered_cards = {card: actions for card, actions in card_actions.items() if actions}

        if not filtered_cards:
            raise ValueError("No cards to export after filtering")

        # Get all unique matchups (columns)
        all_matchups = sorted(
            {matchup for actions in filtered_cards.values() for matchup in actions.keys()}
        )

        # Write CSV
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header row
            writer.writerow(["Card"] + all_matchups)

            # Data rows
            for card_name in sorted(filtered_cards.keys()):
                row = [card_name]
                for matchup in all_matchups:
                    actions = filtered_cards[card_name].get(matchup, set())
                    # Join multiple actions with " & " if both in and out
                    cell_value = " & ".join(sorted(actions)) if actions else ""
                    row.append(cell_value)
                writer.writerow(row)
