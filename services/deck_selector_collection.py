from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.collection_service import CollectionService


@dataclass(frozen=True)
class CollectionStatus:
    label: str
    filepath: Path
    card_count: int
    age_hours: int


class DeckSelectorCollectionManager:
    """Format collection status information for the deck selector UI."""

    def __init__(self, collection_service: CollectionService) -> None:
        self.collection_service = collection_service

    def load_cached_status(self, directory: Path) -> CollectionStatus:
        """Load cached collection info and return display-friendly metadata."""
        info = self.collection_service.load_from_cached_file(directory)
        age_hours = info["age_hours"]
        age_str = f"{age_hours}h ago" if age_hours > 0 else "recent"
        label = f"Collection: {info['filepath'].name} ({info['card_count']} entries, {age_str})"
        return CollectionStatus(
            label=label,
            filepath=info["filepath"],
            card_count=info["card_count"],
            age_hours=age_hours,
        )


__all__ = ["CollectionStatus", "DeckSelectorCollectionManager"]
