"""Handlers for card table interactions."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import wx

from utils.constants import ZONE_TITLES

if TYPE_CHECKING:
    from widgets.app_frame import AppFrame


class CardTablePanelHandler:
    """Mixin containing zone editing and card focus handlers."""

    def _after_zone_change(self, zone: str) -> None:
        if zone == "main":
            self.main_table.set_cards(self.zone_cards["main"])
        elif zone == "side":
            self.side_table.set_cards(self.zone_cards["side"])
        else:
            if self.out_table:
                self.out_table.set_cards(self.zone_cards["out"])
            self._persist_outboard_for_current()
        deck_text = self.controller.deck_service.build_deck_text_from_zones(self.zone_cards)
        self.controller.deck_repo.set_current_deck_text(deck_text)
        self._update_stats(deck_text)
        self.copy_button.Enable(self._has_deck_loaded())
        self.save_button.Enable(self._has_deck_loaded())
        self._schedule_settings_save()

    def _handle_zone_delta(self: AppFrame, zone: str, name: str, delta: int) -> None:
        cards = self.zone_cards.get(zone, [])
        for entry in cards:
            if entry["name"].lower() == name.lower():
                current_qty = entry["qty"]
                if isinstance(current_qty, float) and not current_qty.is_integer():
                    current_qty = math.ceil(current_qty) if delta > 0 else math.floor(current_qty)
                entry["qty"] = max(0, current_qty + delta)
                if entry["qty"] == 0:
                    cards.remove(entry)
                break
        else:
            if delta > 0:
                cards.append({"name": name, "qty": delta})
        cards.sort(key=lambda item: item["name"].lower())
        self.zone_cards[zone] = cards
        self._after_zone_change(zone)

    def _handle_zone_remove(self: AppFrame, zone: str, name: str) -> None:
        cards = self.zone_cards.get(zone, [])
        self.zone_cards[zone] = [entry for entry in cards if entry["name"].lower() != name.lower()]
        self._after_zone_change(zone)

    def _handle_zone_add(self: AppFrame, zone: str) -> None:
        if zone == "out":
            main_cards = [entry["name"] for entry in self.zone_cards.get("main", [])]
            existing = {entry["name"].lower() for entry in self.zone_cards.get("out", [])}
            candidates = [name for name in main_cards if name.lower() not in existing]
            if not candidates:
                wx.MessageBox(
                    "All mainboard cards are already in the outboard list.",
                    "Outboard",
                    wx.OK | wx.ICON_INFORMATION,
                )
                return
            dlg = wx.SingleChoiceDialog(
                self, "Select a mainboard card eligible for sideboarding.", "Outboard", candidates
            )
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            selection = dlg.GetStringSelection()
            dlg.Destroy()
            qty = next(
                (entry["qty"] for entry in self.zone_cards["main"] if entry["name"] == selection), 1
            )
            self.zone_cards.setdefault("out", []).append({"name": selection, "qty": qty})
            self.zone_cards["out"].sort(key=lambda item: item["name"].lower())
            self._after_zone_change("out")
            return

        dlg = wx.TextEntryDialog(
            self, f"Add card to {ZONE_TITLES.get(zone, zone)} (format: 'Qty Card Name')", "Add Card"
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        value = dlg.GetValue().strip()
        dlg.Destroy()
        if not value:
            return
        parts = value.split(" ", 1)
        try:
            qty = int(parts[0]) if len(parts) > 1 else 1
        except ValueError:
            qty = 1
        name = parts[1].strip() if len(parts) > 1 else value
        if not name:
            return
        self.zone_cards.setdefault(zone, []).append({"name": name, "qty": max(1, qty)})
        self.zone_cards[zone].sort(key=lambda item: item["name"].lower())
        self._after_zone_change(zone)

    def _collapse_other_zone_tables(self, active_zone: str) -> None:
        tables = {
            "main": self.main_table,
            "side": self.side_table,
            "out": self.out_table,
        }
        for zone, table in tables.items():
            if zone == active_zone:
                continue
            if table:
                table.collapse_active()

    def _handle_card_focus(self: AppFrame, zone: str, card: dict[str, Any] | None) -> None:
        if card is None:
            if self.card_inspector_panel.active_zone == zone:
                self.card_inspector_panel.reset()
            return
        self._collapse_other_zone_tables(zone)
        meta = self.controller.card_repo.get_card_metadata(card["name"])
        self.card_inspector_panel.update_card(card, zone=zone, meta=meta)

    def _handle_card_hover(self: AppFrame, zone: str, card: dict[str, Any]) -> None:
        self._pending_hover = (zone, card)
        if self._inspector_hover_timer is None:
            self._inspector_hover_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._flush_hover_preview, self._inspector_hover_timer)
        elif self._inspector_hover_timer.IsRunning():
            self._inspector_hover_timer.Stop()
        # Debounce inspector updates to avoid thrashing while the mouse moves quickly.
        self._inspector_hover_timer.StartOnce(120)

    def _flush_hover_preview(self: AppFrame, _event: wx.TimerEvent) -> None:
        if not self._pending_hover:
            return
        zone, card = self._pending_hover
        self._pending_hover = None
        meta = self.controller.card_repo.get_card_metadata(card["name"])
        self.card_inspector_panel.update_card(card, zone=zone, meta=meta)
