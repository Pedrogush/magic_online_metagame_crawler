from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import wx
import wx.dataview as dv

from services.radar_service import CardFrequency

if TYPE_CHECKING:
    from widgets.app_frame import AppFrame
    from widgets.buttons.deck_action_buttons import DeckActionButtons
    from widgets.buttons.toolbar_buttons import ToolbarButtons
    from widgets.panels.deck_builder_panel import DeckBuilderPanel
    from widgets.panels.sideboard_guide_panel import SideboardGuidePanel


class TooltipManager:
    """Central helper for registering tooltips across the UI."""

    @staticmethod
    def set(widget: wx.Window | None, text: str | None) -> None:
        """Assign a tooltip if both widget and text are present."""
        if widget and text:
            widget.SetToolTip(text)

    # ---------- App-wide helpers ----------
    def apply_app_frame_tooltips(self, frame: AppFrame) -> None:
        """Attach tooltips to primary UI elements on the main frame."""
        self._apply_toolbar_tooltips(frame.toolbar)
        self._apply_deck_actions(frame.deck_action_buttons)

        if frame.builder_panel:
            self._apply_builder_tooltips(frame.builder_panel)
        if frame.research_panel and getattr(frame.research_panel, "refresh_button", None):
            self.set(
                frame.research_panel.refresh_button,
                "Reload archetypes for the selected format.",
            )
        if frame.sideboard_guide_panel:
            self._apply_sideboard_tooltips(frame.sideboard_guide_panel)
        if frame.deck_notes_panel:
            self.set(frame.deck_notes_panel.save_btn, "Save deck notes to disk.")
        if frame.card_inspector_panel:
            self.set(frame.card_inspector_panel.prev_btn, "Show previous matching card image.")
            self.set(frame.card_inspector_panel.next_btn, "Show next matching card image.")

    def _apply_toolbar_tooltips(self, toolbar: ToolbarButtons) -> None:
        self.set(
            toolbar.opponent_tracker_button,
            "MTGO overlay that reads match window titles to identify opponents.",
        )
        self.set(
            toolbar.timer_alert_button,
            "Monitor MTGO challenge timers and play alerts as rounds end.",
        )
        self.set(
            toolbar.match_history_button,
            "Open your MTGO match history pulled from local logs.",
        )
        self.set(
            toolbar.load_collection_button,
            "Load your MTGO collection via the bridge for ownership checks.",
        )
        self.set(
            toolbar.metagame_analysis_button,
            "Launch detailed metagame analysis for the current format.",
        )
        self.set(
            toolbar.download_images_button,
            "Download any missing card images for offline viewing.",
        )
        if getattr(toolbar, "help_button", None):
            self.set(toolbar.help_button, "Open the in-app guide, contact info, and license.")

    def _apply_deck_actions(self, buttons: DeckActionButtons) -> None:
        self.set(
            buttons.daily_average_button,
            "Build a deck from the current archetype's average card counts.",
        )
        self.set(buttons.copy_button, "Copy the current decklist to your clipboard.")
        self.set(buttons.save_button, "Save the current decklist to a file.")

    def _apply_builder_tooltips(self, builder: DeckBuilderPanel) -> None:
        self.set(builder.back_btn, "Return to deck research view.")
        self.set(builder.clear_filters_btn, "Reset all filters and search fields.")
        self.set(builder.all_mana_btn, "Open the full mana symbol keyboard.")
        self.set(builder.open_radar_btn, "Generate or view archetype radar data.")

    def _apply_sideboard_tooltips(self, panel: SideboardGuidePanel) -> None:
        self.set(panel.add_btn, "Add a new matchup guide entry.")
        self.set(panel.edit_btn, "Edit the selected matchup guide entry.")
        self.set(panel.remove_btn, "Remove the selected matchup guide entry.")
        self.set(panel.exclusions_btn, "Choose archetypes to exclude from guide suggestions.")
        self.set(panel.export_btn, "Export sideboard guide entries to CSV.")
        self.set(panel.import_btn, "Import sideboard guide entries from CSV.")

    # ---------- Radar helpers ----------
    def bind_radar_distribution_tooltips(
        self,
        list_ctrl: dv.DataViewListCtrl,
        cards_supplier: Callable[[], list[CardFrequency]],
        total_supplier: Callable[[], int],
    ) -> None:
        """Bind tooltip handlers showing card copy distribution for a radar list."""

        def on_mouse_move(event: wx.MouseEvent) -> None:
            cards = cards_supplier() or []
            total_decks = total_supplier() or 0
            tooltip_text = self._build_radar_tooltip(list_ctrl, cards, total_decks, event)
            current_tip = list_ctrl.GetToolTipText() if list_ctrl.GetToolTip() else ""

            if tooltip_text and tooltip_text != current_tip:
                list_ctrl.SetToolTip(tooltip_text)
            elif not tooltip_text and current_tip:
                list_ctrl.SetToolTip("")
            event.Skip()

        def on_leave(event: wx.Event) -> None:
            if list_ctrl.GetToolTip():
                list_ctrl.SetToolTip("")
            event.Skip()

        list_ctrl.Bind(wx.EVT_MOTION, on_mouse_move)
        list_ctrl.Bind(wx.EVT_LEAVE_WINDOW, on_leave)

    def _build_radar_tooltip(
        self,
        list_ctrl: dv.DataViewListCtrl,
        cards: list[CardFrequency],
        total_decks: int,
        event: wx.MouseEvent,
    ) -> str:
        if total_decks <= 0:
            return ""

        hit = list_ctrl.HitTest(event.GetPosition())
        if not hit or len(hit) < 2:
            return ""

        item = hit[0]
        if not item or not item.IsOk():
            return ""

        row = list_ctrl.ItemToRow(item)
        if row == wx.NOT_FOUND or row >= len(cards):
            return ""

        card = cards[row]
        lines = [f"{total_decks} decks analyzed"]
        for copies, deck_count in card.copy_distribution.items():
            copy_label = "copy" if copies == 1 else "copies"
            lines.append(f"{deck_count} decks use {copies} {copy_label}")
        return "\n".join(lines)


__all__ = ["TooltipManager"]
