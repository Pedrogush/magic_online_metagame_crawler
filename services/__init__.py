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


from services.search_service import SearchService, get_search_service

from services.deck_service import DeckService, get_deck_service
from services.image_service import ImageService, get_image_service
from services.store_service import StoreService, get_store_service

__all__ = [
    "CollectionService",
    "DeckService",
    "ImageService",
    "SearchService",
    "StoreService",
    "get_collection_service",
    "get_deck_service",
    "get_image_service",
    "get_search_service",
    "get_store_service",
]
