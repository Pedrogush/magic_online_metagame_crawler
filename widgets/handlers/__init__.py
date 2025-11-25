"""Handler mixins for widgets."""

from widgets.handlers.app_event_handlers import AppEventHandlers
from widgets.handlers.card_table_panel_handler import CardTablePanelHandler
from widgets.handlers.sideboard_guide_handlers import SideboardGuideHandlers

__all__ = [
    "AppEventHandlers",
    "CardTablePanelHandler",
    "SideboardGuideHandlers",
]
