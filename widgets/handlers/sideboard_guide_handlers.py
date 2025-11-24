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
                archetype_name = data.get("archetype")
                enable_double = data.get("enable_double_entries", False)

                if not enable_double:
                    # Check if archetype already exists and overwrite it
                    existing_index = None
                    for i, entry in enumerate(self.sideboard_guide_entries):
                        if entry.get("archetype") == archetype_name:
                            existing_index = i
                            break

                    if existing_index is not None:
                        # Overwrite existing entry
                        # Don't include enable_double_entries in the persisted data
                        entry_data = {k: v for k, v in data.items() if k != "enable_double_entries"}
                        self.sideboard_guide_entries[existing_index] = entry_data
                    else:
                        # Add new entry
                        entry_data = {k: v for k, v in data.items() if k != "enable_double_entries"}
                        self.sideboard_guide_entries.append(entry_data)
                else:
                    # Add new entry even if archetype exists
                    entry_data = {k: v for k, v in data.items() if k != "enable_double_entries"}
                    self.sideboard_guide_entries.append(entry_data)

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
            self._set_status("Select an entry to edit.")
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
            self._set_status("Select an entry to remove.")
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
            self._set_status("No guide entries to export.")
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
            self._set_status("Sideboard guide exported successfully.")
        except Exception as e:
            self._set_status("Error exporting sideboard guide to CSV.")
            from loguru import logger
            logger.exception(f"Error exporting sideboard guide to CSV: {e}")

    def _on_import_guide_csv(self: MTGDeckSelectionFrame) -> None:
        """Import sideboard guide from CSV format."""
        # Clear any existing warnings
        self.sideboard_guide_panel.set_warning("")

        # Ask user for file to import
        file_dlg = wx.FileDialog(
            self,
            "Import Sideboard Guide",
            wildcard="CSV files (*.csv)|*.csv",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )

        if file_dlg.ShowModal() != wx.ID_OK:
            file_dlg.Destroy()
            return

        file_path = file_dlg.GetPath()
        file_dlg.Destroy()

        # Show import options dialog
        options_dlg = wx.Dialog(self, title="Import Options", size=(400, 150))
        panel = wx.Panel(options_dlg)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Checkbox for enabling double entries
        enable_double_checkbox = wx.CheckBox(panel, label="Enable double entries")
        enable_double_checkbox.SetToolTip(
            "If unchecked, will overwrite existing entries for matching archetypes. "
            "If checked, will add entries even if archetypes already exist."
        )
        sizer.Add(enable_double_checkbox, 0, wx.ALL, 12)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        ok_btn = wx.Button(panel, label="Import", id=wx.ID_OK)
        ok_btn.SetDefault()
        btn_sizer.Add(ok_btn, 0, wx.RIGHT, 8)
        cancel_btn = wx.Button(panel, label="Cancel", id=wx.ID_CANCEL)
        btn_sizer.Add(cancel_btn, 0)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)

        panel.SetSizer(sizer)
        options_dlg.Centre()

        if options_dlg.ShowModal() != wx.ID_OK:
            options_dlg.Destroy()
            return

        enable_double_entries = enable_double_checkbox.GetValue()
        options_dlg.Destroy()

        try:
            imported_entries, warnings = self._import_guide_from_csv(file_path)

            if not imported_entries:
                self._set_status("No valid guide entries found in CSV.")
                return

            # Handle duplicate archetypes based on enable_double_entries setting
            if not enable_double_entries:
                # Overwrite existing entries for matching archetypes
                for imported_entry in imported_entries:
                    archetype_name = imported_entry.get("archetype")
                    existing_index = None
                    for i, entry in enumerate(self.sideboard_guide_entries):
                        if entry.get("archetype") == archetype_name:
                            existing_index = i
                            break

                    if existing_index is not None:
                        # Overwrite existing entry
                        self.sideboard_guide_entries[existing_index] = imported_entry
                    else:
                        # Add new entry
                        self.sideboard_guide_entries.append(imported_entry)
            else:
                # Add all imported entries even if archetypes exist
                self.sideboard_guide_entries.extend(imported_entries)

            self._persist_guide_for_current()
            self._refresh_guide_view()

            # Display warnings if any
            if warnings:
                warning_msg = (
                    f"Imported {len(imported_entries)} entries with warnings: {'; '.join(warnings)}"
                )
                self.sideboard_guide_panel.set_warning(warning_msg)
            else:
                # Show success message briefly then clear
                self._set_status(f"Successfully imported {len(imported_entries)} guide entries.")

        except Exception as e:
            self._set_status("Error importing sideboard guide from CSV.")
            from loguru import logger
            logger.exception(f"Error importing sideboard guide from CSV: {e}")

    def _export_guide_to_csv(self: MTGDeckSelectionFrame, file_path: str) -> None:
        """
        Export sideboard guide to CSV with smart filtering.

        Creates a table where:
        - Rows are cards
        - Columns are matchups (archetypes)
        - Cells show "Out" for cards taken out, "In" for cards brought in
        - Cards that never appear are filtered out
        - Decklist is included beneath the guide table
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

            # Add blank rows as separator
            writer.writerow([])
            writer.writerow([])

            # Add decklist section
            writer.writerow(["DECKLIST"])
            writer.writerow([])

            # Write mainboard
            writer.writerow(["Mainboard"])
            mainboard_cards = self.zone_cards.get("main", [])
            for card in sorted(mainboard_cards, key=lambda c: c.get("name", "")):
                qty = card.get("qty", 0)
                name = card.get("name", "")
                writer.writerow([f"{qty} {name}"])

            # Write sideboard
            writer.writerow([])
            writer.writerow(["Sideboard"])
            sideboard_cards = self.zone_cards.get("side", [])
            for card in sorted(sideboard_cards, key=lambda c: c.get("name", "")):
                qty = card.get("qty", 0)
                name = card.get("name", "")
                writer.writerow([f"{qty} {name}"])

    def _import_guide_from_csv(
        self: MTGDeckSelectionFrame, file_path: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Import sideboard guide from CSV format with sanitization.

        Args:
            file_path: Path to CSV file to import

        Returns:
            Tuple of (imported entries, list of warning messages)
        """
        import csv
        import re

        # Build sets of available card names for validation
        mainboard_names = {card["name"] for card in self.zone_cards.get("main", [])}
        sideboard_names = {card["name"] for card in self.zone_cards.get("side", [])}

        entries_by_archetype: dict[str, dict[str, dict[str, int]]] = {}
        warnings: list[str] = []
        missing_cards: set[str] = set()

        with open(file_path, encoding="utf-8") as f:
            reader = csv.reader(f)

            # Read header
            header = next(reader, None)
            if not header or header[0] != "Card":
                raise ValueError("Invalid CSV format: expected 'Card' as first column header")

            # Extract matchup columns (skip first "Card" column)
            matchup_columns = header[1:]

            # Parse matchup columns to extract archetype and scenario
            # Format: "Archetype Name (Play)" or "Archetype Name (Draw)"
            archetype_scenario_map: list[tuple[str, str]] = []
            for col in matchup_columns:
                match = re.match(r"^(.+?)\s*\((Play|Draw)\)$", col)
                if match:
                    archetype_name = match.group(1).strip()
                    scenario = match.group(2).lower()  # "play" or "draw"
                    archetype_scenario_map.append((archetype_name, scenario))
                else:
                    # Skip columns that don't match expected format
                    archetype_scenario_map.append((None, None))

            # Read data rows until we hit the DECKLIST section
            for row in reader:
                if not row:
                    continue

                # Stop when we hit the decklist section
                if row[0] in ["DECKLIST", "Mainboard", "Sideboard"]:
                    break

                card_name = row[0].strip()
                if not card_name:
                    continue

                # Process each matchup column
                for idx, cell_value in enumerate(row[1:], start=0):
                    if idx >= len(archetype_scenario_map):
                        continue

                    archetype_name, scenario = archetype_scenario_map[idx]
                    if not archetype_name or not scenario:
                        continue

                    if not cell_value or not cell_value.strip():
                        continue

                    # Initialize archetype entry if needed
                    if archetype_name not in entries_by_archetype:
                        entries_by_archetype[archetype_name] = {
                            "play_out": {},
                            "play_in": {},
                            "draw_out": {},
                            "draw_in": {},
                        }

                    # Parse cell value like "Out 2" or "In 3" or "Out 2 & In 1"
                    actions = cell_value.split("&")
                    for action in actions:
                        action = action.strip()
                        # Match "Out X" or "In X"
                        match = re.match(r"^(Out|In)\s+(\d+)$", action)
                        if match:
                            direction = match.group(1).lower()  # "out" or "in"
                            qty = int(match.group(2))

                            # Determine the key for this action
                            key = f"{scenario}_{direction}"  # e.g., "play_out", "draw_in"

                            # Validate card exists in appropriate zone
                            if direction == "out" and card_name not in mainboard_names:
                                missing_cards.add(f"{card_name} (not in mainboard)")
                                continue
                            elif direction == "in" and card_name not in sideboard_names:
                                missing_cards.add(f"{card_name} (not in sideboard)")
                                continue

                            # Add to entry
                            entries_by_archetype[archetype_name][key][card_name] = qty

        # Convert to list of entries
        imported_entries = []
        for archetype_name, data in entries_by_archetype.items():
            entry = {
                "archetype": archetype_name,
                "play_out": data["play_out"],
                "play_in": data["play_in"],
                "draw_out": data["draw_out"],
                "draw_in": data["draw_in"],
                "notes": "",
            }
            imported_entries.append(entry)

        # Build warning messages
        if missing_cards:
            warnings.append(f"Cards not in deck: {', '.join(sorted(missing_cards))}")

        return imported_entries, warnings
