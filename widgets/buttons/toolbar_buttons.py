"""
Toolbar Buttons - Shared utility buttons for the deck selector toolbar.

Provides quick-access buttons for opponent tracking, timers, history, and data tasks.
"""

from collections.abc import Callable

import wx


class ToolbarButtons(wx.Panel):
    """Panel containing the deck selector toolbar buttons."""

    def __init__(
        self,
        parent: wx.Window,
        on_open_opponent_tracker: Callable[[], None] | None = None,
        on_open_timer_alert: Callable[[], None] | None = None,
        on_open_match_history: Callable[[], None] | None = None,
        on_open_metagame_analysis: Callable[[], None] | None = None,
        on_load_collection: Callable[[], None] | None = None,
        on_download_card_images: Callable[[], None] | None = None,
        on_update_card_database: Callable[[], None] | None = None,
    ):
        from utils.i18n import t

        super().__init__(parent)

        self._button_row = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self._button_row)

        self.opponent_tracker_button = self._add_button(
            t("toolbar.opponent_tracker"), on_open_opponent_tracker
        )
        self.timer_alert_button = self._add_button(t("toolbar.timer_alert"), on_open_timer_alert)
        self.match_history_button = self._add_button(
            t("toolbar.match_history"), on_open_match_history
        )
        self.metagame_analysis_button = self._add_button(
            t("toolbar.metagame_analysis"), on_open_metagame_analysis
        )
        self.load_collection_button = self._add_button(
            t("toolbar.load_collection"), on_load_collection
        )
        self.download_images_button = self._add_button(
            t("toolbar.download_images"), on_download_card_images
        )
        self.update_database_button = self._add_button(
            t("toolbar.update_database"), on_update_card_database
        )

        self._button_row.AddStretchSpacer(1)

    # ============= Public API =============

    def enable_mtgo_buttons(self, enable: bool = True) -> None:
        """Enable or disable MTGO-dependent buttons."""
        self.load_collection_button.Enable(enable)
        self.opponent_tracker_button.Enable(enable)
        self.timer_alert_button.Enable(enable)
        self.match_history_button.Enable(enable)

    # ============= Helpers =============

    def _add_button(
        self, label: str, handler: Callable[[], None] | None, *, margin: int = 6
    ) -> wx.Button:
        """Create a toolbar button and bind its handler if provided."""
        button = wx.Button(self, label=label)
        if handler:
            button.Bind(wx.EVT_BUTTON, lambda _evt, cb=handler: cb())
        else:  # pragma: no cover - defensive fallback
            button.Disable()
        self._button_row.Add(button, 0, wx.RIGHT, margin)
        return button


__all__ = ["ToolbarButtons"]
