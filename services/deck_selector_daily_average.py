from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from repositories.deck_repository import DeckRepository
from services.deck_research_service import DeckResearchService
from services.deck_service import DeckService
from utils.deck import read_curr_deck_file


class DeckSelectorDailyAverageBuilder:
    """Encapsulate daily average deck aggregation logic."""

    def __init__(
        self,
        deck_repo: DeckRepository,
        deck_service: DeckService,
        deck_research_service: DeckResearchService,
    ) -> None:
        self.deck_repo = deck_repo
        self.deck_service = deck_service
        self.deck_research_service = deck_research_service

    def filter_today_decks(
        self, decks: list[dict[str, Any]], today: str | None = None
    ) -> list[dict[str, Any]]:
        today = today or time.strftime("%Y-%m-%d").lower()
        return [deck for deck in decks if today in str(deck.get("date", "")).lower()]

    def build_average_text(
        self,
        todays_decks: list[dict[str, Any]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        buffer = self.deck_repo.build_daily_average_deck(
            todays_decks,
            self.deck_research_service.download_deck,
            read_curr_deck_file,
            self.deck_service.add_deck_to_buffer,
            progress_callback=progress_callback,
        )
        return self.deck_service.render_average_deck(buffer, len(todays_decks))


__all__ = ["DeckSelectorDailyAverageBuilder"]
