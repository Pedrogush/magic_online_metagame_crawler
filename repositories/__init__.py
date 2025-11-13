"""
Repositories package - Data access layer.

This package contains repository classes that handle all data persistence
and retrieval operations, isolating the UI and business logic from data access details.
"""

from repositories.card_repository import CardRepository, get_card_repository
from repositories.deck_repository import DeckRepository, get_deck_repository
from repositories.metagame_repository import MetagameRepository, get_metagame_repository

__all__ = [
    "CardRepository",
    "DeckRepository",
    "MetagameRepository",
    "get_card_repository",
    "get_deck_repository",
    "get_metagame_repository",
]
