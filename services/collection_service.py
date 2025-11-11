"""Service for collection operations - loading and managing inventory."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger


class CollectionService:
    """Handles collection inventory loading and caching."""

    def __init__(self, cache_dir: Path):
        """Initialize collection service.

        Args:
            cache_dir: Directory for caching collection data
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.collection_cache_file = cache_dir / "collection.json"
        self.inventory: dict[str, int] = {}

    def load_from_cache(self) -> bool:
        """Load collection from cache file.

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.collection_cache_file.exists():
            logger.debug("No collection cache found")
            return False

        try:
            with self.collection_cache_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            self.inventory = {}
            for item in data.get("cards", []):
                name = item.get("name", "")
                qty = item.get("quantity", 0)
                if name:
                    self.inventory[name] = self.inventory.get(name, 0) + qty

            logger.info(f"Loaded {len(self.inventory)} unique cards from cache")
            return True
        except (OSError, json.JSONDecodeError) as exc:
            logger.error(f"Failed to load collection cache: {exc}")
            return False

    def save_to_cache(self, cards: list[dict[str, Any]]) -> Path:
        """Save collection to cache file.

        Args:
            cards: List of card dictionaries with 'name' and 'quantity'

        Returns:
            Path to cache file

        Raises:
            OSError: If save fails
        """
        data = {"cards": cards}

        self.collection_cache_file.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        logger.info(f"Saved collection to {self.collection_cache_file}")
        return self.collection_cache_file

    def fetch_from_bridge(self, bridge_path: Path, timeout: int = 120) -> list[dict[str, Any]]:
        """Fetch collection from MTGO bridge.

        Args:
            bridge_path: Path to MTGOBridge.exe
            timeout: Timeout in seconds

        Returns:
            List of card dictionaries

        Raises:
            subprocess.TimeoutExpired: If bridge times out
            subprocess.CalledProcessError: If bridge fails
            json.JSONDecodeError: If response is invalid
        """
        logger.info("Fetching collection from MTGO bridge")

        result = subprocess.run(
            [str(bridge_path), "collection"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )

        data = json.loads(result.stdout)
        cards = data.get("collection", [])
        logger.info(f"Fetched {len(cards)} cards from bridge")
        return cards

    def build_inventory(self, cards: list[dict[str, Any]]) -> dict[str, int]:
        """Build inventory dictionary from card list.

        Args:
            cards: List of card dictionaries

        Returns:
            Dictionary mapping card names to quantities
        """
        inventory: dict[str, int] = {}

        for item in cards:
            name = item.get("name", "")
            qty = item.get("quantity", 0)
            if name:
                inventory[name] = inventory.get(name, 0) + qty

        self.inventory = inventory
        return inventory

    def get_owned_quantity(self, card_name: str) -> int:
        """Get owned quantity for a card.

        Args:
            card_name: Card name

        Returns:
            Owned quantity (0 if not owned)
        """
        return self.inventory.get(card_name, 0)

    def get_owned_status(self, card_name: str, required: int) -> tuple[str, str]:
        """Get ownership status text and color.

        Args:
            card_name: Card name
            required: Required quantity

        Returns:
            Tuple of (status text, color name)
        """
        owned = self.get_owned_quantity(card_name)

        if owned == 0:
            return "Not owned", "red"
        elif owned < required:
            return f"Own {owned}/{required}", "orange"
        else:
            return f"Own {owned}", "green"

    def clear(self) -> None:
        """Clear inventory."""
        self.inventory.clear()
        logger.debug("Cleared collection inventory")
