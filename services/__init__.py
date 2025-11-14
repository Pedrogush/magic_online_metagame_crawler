"""
Services package - Business logic layer.

This package contains service classes that handle all business logic,
orchestrating between repositories and the UI layer.
"""

try:  # wxPython may be missing in headless environments
    from services.collection_service import CollectionService, get_collection_service
except Exception:  # pragma: no cover - collection service not available without wx
    CollectionService = None

    def get_collection_service():
        raise RuntimeError("CollectionService is unavailable (wxPython not installed)")


from services.deck_research_service import DeckResearchService
from services.deck_selector_card_data import DeckSelectorCardDataLoader
from services.deck_selector_collection import DeckSelectorCollectionManager
from services.deck_selector_daily_average import DeckSelectorDailyAverageBuilder
from services.deck_selector_image import DeckSelectorImageManager
from services.deck_selector_state import DeckSelectorStateStore
from services.deck_selector_zones import DeckZoneManager
from services.deck_service import DeckService, get_deck_service
from services.image_service import ImageService, get_image_service
from services.search_service import SearchService, get_search_service
from services.store_service import StoreService, get_store_service

__all__ = [
    "CollectionService",
    "DeckSelectorCollectionManager",
    "DeckSelectorDailyAverageBuilder",
    "DeckResearchService",
    "DeckSelectorImageManager",
    "DeckSelectorCardDataLoader",
    "DeckZoneManager",
    "DeckSelectorStateStore",
    "DeckService",
    "ImageService",
    "SearchService",
    "StoreService",
    "get_collection_service",
    "get_deck_research_service",
    "get_deck_service",
    "get_image_service",
    "get_search_service",
    "get_store_service",
]


def get_deck_research_service() -> DeckResearchService:
    return DeckResearchService()


def get_deck_selector_state_store() -> DeckSelectorStateStore:
    return DeckSelectorStateStore()
