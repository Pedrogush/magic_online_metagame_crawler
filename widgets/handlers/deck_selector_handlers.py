"""Event handlers for MTGDeckSelectionFrame extracted to reduce main file size."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import wx
from loguru import logger

from utils.ui_helpers import widget_exists

if TYPE_CHECKING:
    from widgets.deck_selector import MTGDeckSelectionFrame


class DeckSelectorHandlers:
    """Mixin class containing all event handlers for MTGDeckSelectionFrame."""

    # UI Event Handlers
    def on_format_changed(self: MTGDeckSelectionFrame) -> None:
        """Handle format selection change."""
        self.current_format = self.research_panel.get_selected_format()
        self.fetch_archetypes(force=True)

    def on_archetype_filter(self: MTGDeckSelectionFrame) -> None:
        """Handle archetype search filter changes."""
        query = self.research_panel.get_search_query()
        if not query:
            self.filtered_archetypes = list(self.archetypes)
        else:
            self.filtered_archetypes = [
                entry for entry in self.archetypes if query in entry.get("name", "").lower()
            ]
        self._populate_archetype_list()

    def on_archetype_selected(self: MTGDeckSelectionFrame) -> None:
        """Handle archetype selection from the list."""
        with self._loading_lock:
            if self.loading_archetypes or self.loading_decks:
                return
        idx = self.research_panel.get_selected_archetype_index()
        if idx < 0:
            return
        archetype = self.filtered_archetypes[idx]
        self._load_decks_for_archetype(archetype)

    def on_deck_selected(self: MTGDeckSelectionFrame, _event: wx.CommandEvent) -> None:
        with self._loading_lock:
            if self.loading_decks:
                return
        idx = self.deck_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        deck = self.deck_repo.get_decks_list()[idx]
        self.deck_repo.set_current_deck(deck)
        self.load_button.Enable()
        self.copy_button.Enable(self._has_deck_loaded())
        self.save_button.Enable(self._has_deck_loaded())
        from widgets.deck_selector import format_deck_name

        self._set_status(f"Selected deck {format_deck_name(deck)}")
        self._show_left_panel("builder")
        self._schedule_settings_save()

    def on_load_deck_clicked(self: MTGDeckSelectionFrame, _event: wx.CommandEvent) -> None:
        current_deck = self.deck_repo.get_current_deck()
        with self._loading_lock:
            if self.loading_decks:
                return
        if not current_deck:
            return
        self._download_and_display_deck(current_deck)

    def on_daily_average_clicked(self: MTGDeckSelectionFrame, _event: wx.CommandEvent) -> None:
        with self._loading_lock:
            if self.loading_daily_average:
                return
        if not self.deck_repo.get_decks_list():
            return
        self._start_daily_average_build()

    def on_copy_clicked(self: MTGDeckSelectionFrame, _event: wx.CommandEvent) -> None:
        deck_content = self._build_deck_text().strip()
        if not deck_content:
            wx.MessageBox("No deck to copy.", "Copy Deck", wx.OK | wx.ICON_INFORMATION)
            return
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(deck_content))
            finally:
                wx.TheClipboard.Close()
            self._set_status("Deck copied to clipboard.")
        else:  # pragma: no cover
            wx.MessageBox("Could not access clipboard.", "Copy Deck", wx.OK | wx.ICON_WARNING)

    def on_save_clicked(self: MTGDeckSelectionFrame, _event: wx.CommandEvent) -> None:
        from utils.deck import sanitize_filename
        from utils.paths import DECK_SAVE_DIR
        from widgets.deck_selector import format_deck_name

        deck_content = self._build_deck_text().strip()
        if not deck_content:
            wx.MessageBox("Load a deck first.", "Save Deck", wx.OK | wx.ICON_INFORMATION)
            return
        default_name = "saved_deck"
        current_deck = self.deck_repo.get_current_deck()
        if current_deck:
            default_name = format_deck_name(current_deck).replace(" | ", "_")
        dlg = wx.TextEntryDialog(self, "Deck name:", "Save Deck", default_name=default_name)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        deck_name = dlg.GetValue().strip() or default_name
        dlg.Destroy()

        safe_name = sanitize_filename(deck_name)
        file_path = DECK_SAVE_DIR / f"{safe_name}.txt"
        try:
            with file_path.open("w", encoding="utf-8") as fh:
                fh.write(deck_content)
        except OSError as exc:  # pragma: no cover
            wx.MessageBox(f"Failed to write deck file:\n{exc}", "Save Deck", wx.OK | wx.ICON_ERROR)
            return

        try:
            deck_id = self.deck_repo.save_to_db(
                deck_name=deck_name,
                deck_content=deck_content,
                format_type=self.current_format,
                archetype=current_deck.get("name") if current_deck else None,
                player=current_deck.get("player") if current_deck else None,
                source="mtggoldfish" if current_deck else "manual",
                metadata=(current_deck or {}),
            )
            logger.info(f"Deck saved to database: {deck_name} (ID: {deck_id})")
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Deck saved to file but not database: {exc}")
            deck_id = None

        message = f"Deck saved to {file_path}"
        if deck_id:
            message += f"\nDatabase ID: {deck_id}"
        wx.MessageBox(message, "Deck Saved", wx.OK | wx.ICON_INFORMATION)
        self._set_status("Deck saved successfully.")

    def on_window_change(self: MTGDeckSelectionFrame, event: wx.Event) -> None:
        self._schedule_settings_save()
        event.Skip()

    def on_close(self: MTGDeckSelectionFrame, event: wx.CloseEvent) -> None:
        if self._save_timer and self._save_timer.IsRunning():
            self._save_timer.Stop()
        self._save_window_settings()
        for attr in ("tracker_window", "timer_window", "history_window"):
            window = getattr(self, attr)
            if widget_exists(window):
                window.Destroy()
                setattr(self, attr, None)
        if self.mana_keyboard_window and self.mana_keyboard_window.IsShown():
            self.mana_keyboard_window.Destroy()
            self.mana_keyboard_window = None
        event.Skip()

    # Async Callback Handlers
    def _on_archetypes_loaded(self: MTGDeckSelectionFrame, items: list[dict[str, Any]]) -> None:
        with self._loading_lock:
            self.loading_archetypes = False
        self.archetypes = sorted(items, key=lambda entry: entry.get("name", "").lower())
        self.filtered_archetypes = list(self.archetypes)
        self._populate_archetype_list()
        self.research_panel.enable_controls()
        count = len(self.archetypes)
        self._set_status(f"Loaded {count} archetypes for {self.current_format}.")
        self.summary_text.ChangeValue(
            f"Select an archetype to view decks.\nLoaded {count} archetypes."
        )

    def _on_archetypes_error(self: MTGDeckSelectionFrame, error: Exception) -> None:
        with self._loading_lock:
            self.loading_archetypes = False
        self.research_panel.set_error_state()
        self._set_status(f"Error: {error}")
        wx.MessageBox(
            f"Unable to load archetypes:\n{error}", "Archetype Error", wx.OK | wx.ICON_ERROR
        )

    def _on_decks_loaded(
        self: MTGDeckSelectionFrame, archetype_name: str, decks: list[dict[str, Any]]
    ) -> None:
        from widgets.deck_selector import format_deck_name

        with self._loading_lock:
            self.loading_decks = False
        self.deck_repo.set_decks_list(decks)
        self.deck_list.Clear()
        if not decks:
            self.deck_list.Append("No decks found.")
            self.deck_list.Disable()
            self._set_status(f"No decks for {archetype_name}.")
            self.summary_text.ChangeValue(f"{archetype_name}\n\nNo deck data available.")
            return
        for deck in decks:
            self.deck_list.Append(format_deck_name(deck))
        self.deck_list.Enable()
        self.daily_average_button.Enable()
        self._present_archetype_summary(archetype_name, decks)
        self._set_status(f"Loaded {len(decks)} decks for {archetype_name}. Select one to inspect.")

    def _on_decks_error(self: MTGDeckSelectionFrame, error: Exception) -> None:
        with self._loading_lock:
            self.loading_decks = False
        self.deck_list.Clear()
        self.deck_list.Append("Failed to load decks.")
        self._set_status(f"Error loading decks: {error}")
        wx.MessageBox(f"Failed to load deck lists:\n{error}", "Deck Error", wx.OK | wx.ICON_ERROR)

    def _on_deck_download_error(self: MTGDeckSelectionFrame, error: Exception) -> None:
        self.load_button.Enable()
        self._set_status(f"Deck download failed: {error}")
        wx.MessageBox(f"Failed to download deck:\n{error}", "Deck Download", wx.OK | wx.ICON_ERROR)

    def _on_deck_content_ready(
        self: MTGDeckSelectionFrame, deck_text: str, source: str = "manual"
    ) -> None:
        self.deck_repo.set_current_deck_text(deck_text)
        stats = self.deck_service.analyze_deck(deck_text)
        self.zone_cards["main"] = [
            {"name": name, "qty": qty} for name, qty in stats["mainboard_cards"]
        ]
        self.zone_cards["side"] = [
            {"name": name, "qty": qty} for name, qty in stats["sideboard_cards"]
        ]
        self.zone_cards["out"] = self._load_outboard_for_current()
        self.main_table.set_cards(self.zone_cards["main"])
        self.side_table.set_cards(self.zone_cards["side"])
        self.out_table.set_cards(self.zone_cards["out"])
        self._update_stats(deck_text)
        self.copy_button.Enable(True)
        self.save_button.Enable(True)
        self.deck_notes_panel.load_notes_for_current()
        self._load_guide_for_current()
        self._set_status(f"Deck ready ({source}).")
        self._show_left_panel("builder")
        self._schedule_settings_save()

    def _on_collection_fetched(self: MTGDeckSelectionFrame, filepath: Path, cards: list) -> None:
        """Handle successful collection fetch."""
        if cards:
            try:
                info = self.collection_service.load_from_card_list(cards, filepath)
                card_count = info["card_count"]
            except ValueError as exc:
                logger.error(f"Failed to load collection: {exc}")
                self.collection_status_label.SetLabel(f"Collection load failed: {exc}")
                return
        else:
            card_count = len(self.collection_service.get_inventory())

        self.collection_status_label.SetLabel(f"Collection: {filepath.name} ({card_count} entries)")
        self.main_table.set_cards(self.zone_cards["main"])
        self.side_table.set_cards(self.zone_cards["side"])

    def _on_collection_fetch_failed(self: MTGDeckSelectionFrame, error_msg: str) -> None:
        """Handle collection fetch failure."""
        self.collection_service.clear_inventory()
        self.collection_status_label.SetLabel(f"Collection fetch failed: {error_msg}")
        logger.warning(f"Collection fetch failed: {error_msg}")

    def _on_bulk_data_loaded(
        self: MTGDeckSelectionFrame, by_name: dict[str, list[dict[str, Any]]], stats: dict[str, Any]
    ) -> None:
        """Handle successful printings index load."""
        self.image_service.clear_printing_index_loading()
        self.image_service.set_bulk_data(by_name)
        self.card_inspector_panel.set_bulk_data(by_name)
        self._set_status("Ready")
        logger.info(
            "Printings index ready: {unique} names / {total} printings",
            unique=stats.get("unique_names"),
            total=stats.get("total_printings"),
        )

    def _on_bulk_data_load_failed(self: MTGDeckSelectionFrame, error_msg: str) -> None:
        """Handle printings index loading failure."""
        self.image_service.clear_printing_index_loading()
        self._set_status("Ready")
        logger.warning(f"Card printings index load failed: {error_msg}")

    def _on_bulk_data_downloaded(self: MTGDeckSelectionFrame, msg: str) -> None:
        """Handle successful bulk data download."""
        self._set_status("Card image database downloaded, indexing printings…")
        logger.info(f"Bulk data downloaded: {msg}")
        self._load_bulk_data_into_memory(force=True)

    def _on_bulk_data_failed(self: MTGDeckSelectionFrame, error_msg: str) -> None:
        """Handle bulk data download failure."""
        self._set_status("Ready")
        logger.warning(f"Bulk data download failed: {error_msg}")

    def _on_mana_keyboard_closed(self: MTGDeckSelectionFrame, event: wx.CloseEvent) -> None:
        self.mana_keyboard_window = None
        event.Skip()

    # Builder Panel Handlers
    def _on_builder_search(self: MTGDeckSelectionFrame) -> None:
        """Handle search button click from builder panel."""
        card_manager = self.card_repo.get_card_manager()
        if not card_manager:
            if not self.card_repo.is_card_data_loading():
                self.ensure_card_data_loaded()
            if not self.card_data_dialogs_disabled:
                wx.MessageBox(
                    "Card database is still loading. Please try again in a moment.",
                    "Card Search",
                    wx.OK | wx.ICON_INFORMATION,
                )
            return

        filters = self.builder_panel.get_filters()

        mv_value_text = filters.get("mv_value", "")
        if mv_value_text:
            try:
                float(mv_value_text)
            except ValueError:
                wx.MessageBox("Mana value must be numeric.", "Card Search", wx.OK | wx.ICON_WARNING)
                return

        results = self.search_service.search_with_builder_filters(filters, card_manager)
        self.builder_panel.update_results(results)

    def _on_builder_clear(self: MTGDeckSelectionFrame) -> None:
        """Handle clear button click from builder panel."""
        self.builder_panel.clear_filters()

    def _on_builder_result_selected(self: MTGDeckSelectionFrame, idx: int) -> None:
        """Handle result selection from builder panel."""
        meta = self.builder_panel.get_result_at_index(idx)
        if not meta:
            return
        faux_card = {"name": meta.get("name", "Unknown"), "qty": 1}
        self.card_inspector_panel.update_card(faux_card, zone=None, meta=meta)
