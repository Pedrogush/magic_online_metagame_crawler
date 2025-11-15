"""
Metagame Repository - Data access layer for metagame information.

This module handles all metagame-related data fetching including:
- MTGGoldfish archetype scraping
- Deck list downloading
- Caching of metagame data
"""

import json
import time
from typing import Any, Final

from loguru import logger

from navigators.mtggoldfish import (
    download_deck,
    get_archetype_decks,
    get_archetypes,
)
from utils.constants import (
    ARCHETYPE_LIST_CACHE_FILE,
    DECK_CACHE_FILE,
)
from utils.constants import METAGAME_CACHE_TTL_SECONDS

_USE_DEFAULT_MAX_AGE: Final = object()


class MetagameRepository:
    """Repository for metagame data access operations."""

    def __init__(self, cache_ttl: int = METAGAME_CACHE_TTL_SECONDS):
        """
        Initialize the metagame repository.

        Args:
            cache_ttl: Time-to-live for cached data in seconds (default: 1 hour)
        """
        self.cache_ttl = cache_ttl

    # ============= Archetype Operations =============

    def get_archetypes_for_format(
        self, mtg_format: str, force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """
        Get list of archetypes for a specific format.

        Args:
            mtg_format: MTG format (e.g., "Modern", "Standard")
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of archetype dictionaries with keys: name, url, share, etc.
        """
        # Try cache first unless forced refresh
        if not force_refresh:
            cached = self._load_cached_archetypes(mtg_format)
            if cached is not None:
                logger.debug(f"Using cached archetypes for {mtg_format}")
                return cached

        # Fetch fresh data
        logger.info(f"Fetching fresh archetypes for {mtg_format}")
        try:
            archetypes = get_archetypes(mtg_format)
            # Cache the results
            self._save_cached_archetypes(mtg_format, archetypes)
            return archetypes
        except Exception as exc:
            logger.error(f"Failed to fetch archetypes: {exc}")
            # Try to return stale cache if available
            cached = self._load_cached_archetypes(mtg_format, max_age=None)
            if cached:
                logger.warning(f"Returning stale cached data for {mtg_format}")
                return cached
            raise

    def get_decks_for_archetype(
        self, archetype: dict[str, Any], force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """
        Get deck lists for a specific archetype.

        Args:
            archetype: Archetype dictionary with 'url' key
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of deck dictionaries
        """
        archetype_url = archetype.get("url", "")
        archetype_name = archetype.get("name", "Unknown")

        # Try cache first unless forced refresh
        if not force_refresh:
            cached = self._load_cached_decks(archetype_url)
            if cached is not None:
                logger.debug(f"Using cached decks for {archetype_name}")
                return cached

        # Fetch fresh data
        logger.info(f"Fetching fresh decks for {archetype_name}")
        try:
            decks = get_archetype_decks(archetype)
            # Cache the results
            self._save_cached_decks(archetype_url, decks)
            return decks
        except Exception as exc:
            logger.error(f"Failed to fetch decks for {archetype_name}: {exc}")
            # Try to return stale cache if available
            cached = self._load_cached_decks(archetype_url, max_age=None)
            if cached:
                logger.warning(f"Returning stale cached decks for {archetype_name}")
                return cached
            raise

    def download_deck_content(self, deck: dict[str, Any]) -> str:
        """
        Download the actual deck list content.

        Args:
            deck: Deck dictionary with 'url' key

        Returns:
            Deck list as text string

        Raises:
            Exception: If download fails
        """
        deck_name = deck.get("name", "Unknown")

        logger.info(f"Downloading deck: {deck_name}")
        try:
            deck_content = download_deck(deck)
            return deck_content
        except Exception as exc:
            logger.error(f"Failed to download deck {deck_name}: {exc}")
            raise

    # ============= Cache Management =============

    def _load_cached_archetypes(
        self, mtg_format: str, max_age: int | None | object = _USE_DEFAULT_MAX_AGE
    ) -> list[dict[str, Any]] | None:
        """
        Load cached archetype list.

        Args:
            mtg_format: MTG format to load
            max_age: Maximum age in seconds (None = ignore age, -1 = use default TTL)

        Returns:
            List of archetypes or None if cache miss
        """
        if max_age == -1:
            max_age = _USE_DEFAULT_MAX_AGE
        effective_max_age = self.cache_ttl if max_age is _USE_DEFAULT_MAX_AGE else max_age

        if not ARCHETYPE_LIST_CACHE_FILE.exists():
            return None

        try:
            with ARCHETYPE_LIST_CACHE_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            logger.warning(f"Cached archetype list invalid: {exc}")
            return None

        entry = data.get(mtg_format)
        if not entry:
            return None

        # Check age if max_age is specified
        if effective_max_age is not None:
            timestamp = entry.get("timestamp", 0)
            if time.time() - timestamp > effective_max_age:
                logger.debug(f"Archetype cache for {mtg_format} expired")
                return None

        return entry.get("items")

    def _save_cached_archetypes(self, mtg_format: str, items: list[dict[str, Any]]) -> None:
        """
        Save archetypes to cache.

        Args:
            mtg_format: MTG format
            items: List of archetype dictionaries
        """
        try:
            # Load existing cache
            if ARCHETYPE_LIST_CACHE_FILE.exists():
                with ARCHETYPE_LIST_CACHE_FILE.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            else:
                data = {}

            # Update entry for this format
            data[mtg_format] = {"timestamp": time.time(), "items": items}

            # Save back
            ARCHETYPE_LIST_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with ARCHETYPE_LIST_CACHE_FILE.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)

            logger.debug(f"Cached {len(items)} archetypes for {mtg_format}")
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to cache archetypes: {exc}")

    def _load_cached_decks(
        self, archetype_url: str, max_age: int | None | object = _USE_DEFAULT_MAX_AGE
    ) -> list[dict[str, Any]] | None:
        """
        Load cached deck list for an archetype.

        Args:
            archetype_url: URL identifying the archetype
            max_age: Maximum age in seconds (None = ignore age, -1 = use default TTL)

        Returns:
            List of decks or None if cache miss
        """
        if max_age == -1:
            max_age = _USE_DEFAULT_MAX_AGE
        effective_max_age = self.cache_ttl if max_age is _USE_DEFAULT_MAX_AGE else max_age

        if not DECK_CACHE_FILE.exists():
            return None

        try:
            with DECK_CACHE_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            logger.warning(f"Cached deck list invalid: {exc}")
            return None

        entry = data.get(archetype_url)
        if not entry:
            return None

        # Check age if max_age is specified
        if effective_max_age is not None:
            timestamp = entry.get("timestamp", 0)
            if time.time() - timestamp > effective_max_age:
                logger.debug("Deck cache for archetype expired")
                return None

        return entry.get("items")

    def _save_cached_decks(self, archetype_url: str, items: list[dict[str, Any]]) -> None:
        """
        Save decks to cache.

        Args:
            archetype_url: URL identifying the archetype
            items: List of deck dictionaries
        """
        try:
            # Load existing cache
            if DECK_CACHE_FILE.exists():
                with DECK_CACHE_FILE.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            else:
                data = {}

            # Update entry for this archetype
            data[archetype_url] = {"timestamp": time.time(), "items": items}

            # Save back
            DECK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with DECK_CACHE_FILE.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)

            logger.debug(f"Cached {len(items)} decks for archetype")
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to cache decks: {exc}")

    def clear_cache(self) -> None:
        """Clear all metagame caches."""
        for cache_file in [ARCHETYPE_LIST_CACHE_FILE, DECK_CACHE_FILE]:
            if cache_file.exists():
                try:
                    cache_file.unlink()
                    logger.info(f"Cleared cache: {cache_file}")
                except OSError as exc:
                    logger.warning(f"Failed to clear cache {cache_file}: {exc}")


# Global instance for backward compatibility
_default_repository = None


def get_metagame_repository() -> MetagameRepository:
    """Get the default metagame repository instance."""
    global _default_repository
    if _default_repository is None:
        _default_repository = MetagameRepository()
    return _default_repository


def reset_metagame_repository() -> None:
    """
    Reset the global metagame repository instance.

    This is primarily useful for testing to ensure test isolation
    and prevent state leakage between tests.
    """
    global _default_repository
    _default_repository = None
