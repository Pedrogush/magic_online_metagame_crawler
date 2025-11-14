from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from repositories.deck_repository import DeckRepository
from services.deck_service import DeckService


@dataclass(frozen=True)
class ZoneUpdateResult:
    deck_text: str
    has_loaded_deck: bool


class DeckZoneManager:
    """Business logic around editing zone cards."""

    def __init__(self, deck_service: DeckService, deck_repo: DeckRepository) -> None:
        self.deck_service = deck_service
        self.deck_repo = deck_repo

    def handle_zone_change(self, zone_cards: dict[str, list[dict[str, Any]]]) -> ZoneUpdateResult:
        deck_text = self.deck_service.build_deck_text_from_zones(zone_cards)
        self.deck_repo.set_current_deck_text(deck_text)
        has_loaded_deck = bool(zone_cards.get("main") or zone_cards.get("side"))
        return ZoneUpdateResult(deck_text=deck_text, has_loaded_deck=has_loaded_deck)


__all__ = ["DeckZoneManager", "ZoneUpdateResult"]
