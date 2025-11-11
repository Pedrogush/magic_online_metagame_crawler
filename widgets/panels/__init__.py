"""Reusable UI panels for the MTG deck selector application."""

from widgets.panels.card_box_panel import CardBoxPanel
from widgets.panels.card_inspector_panel import CardInspectorPanel
from widgets.panels.card_table_panel import CardTablePanel
from widgets.panels.deck_builder_panel import DeckBuilderPanel
from widgets.panels.deck_notes_panel import DeckNotesPanel
from widgets.panels.deck_research_panel import DeckResearchPanel
from widgets.panels.deck_stats_panel import DeckStatsPanel
from widgets.panels.sideboard_guide_panel import SideboardGuidePanel

__all__ = [
    "CardBoxPanel",
    "CardInspectorPanel",
    "CardTablePanel",
    "DeckBuilderPanel",
    "DeckNotesPanel",
    "DeckResearchPanel",
    "DeckStatsPanel",
    "SideboardGuidePanel",
]
