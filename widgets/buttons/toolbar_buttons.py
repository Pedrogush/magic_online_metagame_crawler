"""
Toolbar Buttons - Shared utility buttons for the deck selector toolbar.

Provides quick-access buttons for MTGO utilities, analysis, and support tasks.
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
        on_open_help: Callable[[], None] | None = None,
        on_download_card_images: Callable[[], None] | None = None,
    ):
        """
        Initialize the toolbar button panel.

        Args:
            parent: Parent window
            on_open_opponent_tracker: Callback for "Opponent Tracker"
            on_open_timer_alert: Callback for "Timer Alert"
            on_open_match_history: Callback for "Match History"
            on_open_metagame_analysis: Callback for "Metagame Analysis"
            on_load_collection: Callback for "Load Collection"
            on_open_help: Callback for "Help & About"
            on_download_card_images: Callback for "Download Card Images"
        """
        super().__init__(parent)

        root = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(root)

        mtgo_box = wx.StaticBox(self, label="MTGO Tools")
        mtgo_box.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
        mtgo_box_sizer = wx.StaticBoxSizer(mtgo_box, wx.HORIZONTAL)
        root.Add(mtgo_box_sizer, 0, wx.RIGHT, 10)

        self.opponent_tracker_button = self._add_button(
            "Opponent Tracker", on_open_opponent_tracker, mtgo_box_sizer
        )
        self.timer_alert_button = self._add_button(
            "Timer Alert", on_open_timer_alert, mtgo_box_sizer
        )
        self.match_history_button = self._add_button(
            "Match History", on_open_match_history, mtgo_box_sizer
        )
        self.load_collection_button = self._add_button(
            "Load Collection", on_load_collection, mtgo_box_sizer, margin=0
        )

        utility_box = wx.StaticBox(self, label="Research & Utilities")
        utility_box.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
        utility_sizer = wx.StaticBoxSizer(utility_box, wx.HORIZONTAL)
        root.Add(utility_sizer, 1, wx.EXPAND)

        self.metagame_analysis_button = self._add_button(
            "Metagame Analysis", on_open_metagame_analysis, utility_sizer
        )
        self.download_images_button = self._add_button(
            "Download Card Images", on_download_card_images, utility_sizer
        )
        self.help_button = self._add_button("Help & About", on_open_help, utility_sizer, margin=0)

    # ============= Public API =============

    def enable_mtgo_buttons(self, enable: bool = True) -> None:
        """Enable or disable MTGO-dependent buttons."""
        self.load_collection_button.Enable(enable)
        self.opponent_tracker_button.Enable(enable)
        self.timer_alert_button.Enable(enable)
        self.match_history_button.Enable(enable)

    # ============= Helpers =============

    def _add_button(
        self,
        label: str,
        handler: Callable[[], None] | None,
        container: wx.BoxSizer,
        *,
        margin: int = 6,
    ) -> wx.Button:
        """Create a toolbar button and bind its handler if provided."""
        button = wx.Button(self, label=label)
        if handler:
            button.Bind(wx.EVT_BUTTON, lambda _evt, cb=handler: cb())
        else:  # pragma: no cover - defensive fallback
            button.Disable()
        container.Add(button, 0, wx.RIGHT, margin)
        return button


__all__ = ["ToolbarButtons"]
