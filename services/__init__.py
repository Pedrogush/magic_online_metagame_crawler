"""
Services package - Business logic layer.

This package exposes business services while avoiding heavy imports at module load time.
"""

from importlib import import_module
from typing import Any

__all__ = [
    "CollectionService",
    "CollectionStatus",
    "DeckResearchService",
    "DeckService",
    "ImageService",
    "SearchService",
    "StateService",
    "StoreService",
    "ZoneUpdateResult",
    "get_collection_service",
    "get_deck_research_service",
    "get_deck_service",
    "get_image_service",
    "get_search_service",
    "get_state_service",
    "get_store_service",
]

_LAZY_MODULES = {
    "DeckResearchService": "services.deck_research_service",
    "DeckService": "services.deck_service",
    "ZoneUpdateResult": "services.deck_service",
    "get_deck_service": "services.deck_service",
    "ImageService": "services.image_service",
    "get_image_service": "services.image_service",
    "SearchService": "services.search_service",
    "get_search_service": "services.search_service",
    "StateService": "services.state_service",
    "StoreService": "services.store_service",
    "get_store_service": "services.store_service",
}

_COLLECTION_EXPORTS = {"CollectionService", "CollectionStatus", "get_collection_service"}


def __getattr__(name: str) -> Any:
    if name in _COLLECTION_EXPORTS:
        try:
            module = import_module("services.collection_service")
        except Exception as error:  # pragma: no cover - wx not installed in headless envs
            if name == "get_collection_service":

                def _raise_collection_error(exc=error):
                    raise RuntimeError(
                        "CollectionService is unavailable (wxPython not installed)"
                    ) from exc

                globals()[name] = _raise_collection_error
                return _raise_collection_error
            globals()[name] = None
            return None
        value = getattr(module, name)
        globals()[name] = value
        return value

    if name in _LAZY_MODULES:
        module = import_module(_LAZY_MODULES[name])
        value = getattr(module, name)
        globals()[name] = value
        return value

    raise AttributeError(f"module 'services' has no attribute '{name}'")


def get_deck_research_service():
    from services.deck_research_service import DeckResearchService

    return DeckResearchService()


def get_state_service():
    from services.state_service import StateService

    return StateService()
