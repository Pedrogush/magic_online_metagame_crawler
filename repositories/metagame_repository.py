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
    fetch_deck_text,
    get_archetype_decks,
    get_archetypes,
)
from utils.constants import (
    ARCHETYPE_DECKS_CACHE_FILE,
    ARCHETYPE_LIST_CACHE_FILE,
    METAGAME_CACHE_TTL_SECONDS,
)

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
        self, archetype: dict[str, Any], force_refresh: bool = False, source_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get deck lists for a specific archetype.

        Args:
            archetype: Archetype dictionary with 'href' or 'url' key
            force_refresh: If True, bypass cache and fetch fresh data
            source_filter: Optional source filter ('mtggoldfish', 'mtgo', or 'both')

        Returns:
            List of deck dictionaries
        """
        # Support both 'href' (from get_archetypes) and 'url' for compatibility
        archetype_href = archetype.get("href") or archetype.get("url", "")
        archetype_name = archetype.get("name", "Unknown")

        # Try cache first unless forced refresh
        if not force_refresh:
            cached = self._load_cached_decks(archetype_href)
            if cached is not None:
                logger.debug(f"Using cached decks for {archetype_name}")
                mtggoldfish_decks = self._filter_decks_by_source(cached, source_filter)
                mtgo_decks = self._get_mtgo_decks_from_db(archetype_name, source_filter)
                return self._merge_and_sort_decks(mtggoldfish_decks, mtgo_decks)

        # Fetch fresh data
        logger.info(f"Fetching fresh decks for {archetype_name}")
        try:
            # get_archetype_decks expects just the href string, not the dict
            decks = get_archetype_decks(archetype_href)
            # Cache the results
            self._save_cached_decks(archetype_href, decks)
            mtggoldfish_decks = self._filter_decks_by_source(decks, source_filter)
            mtgo_decks = self._get_mtgo_decks_from_db(archetype_name, source_filter)
            return self._merge_and_sort_decks(mtggoldfish_decks, mtgo_decks)
        except Exception as exc:
            logger.error(f"Failed to fetch decks for {archetype_name}: {exc}")
            # Try to return stale cache if available
            cached = self._load_cached_decks(archetype_href, max_age=None)
            if cached:
                logger.warning(f"Returning stale cached decks for {archetype_name}")
                mtggoldfish_decks = self._filter_decks_by_source(cached, source_filter)
                mtgo_decks = self._get_mtgo_decks_from_db(archetype_name, source_filter)
                return self._merge_and_sort_decks(mtggoldfish_decks, mtgo_decks)
            raise

    def download_deck_content(self, deck: dict[str, Any], source_filter: str | None = None) -> str:
        """
        Download the actual deck list content.

        Args:
            deck: Deck dictionary with 'number' key (deck ID)
            source_filter: Optional source filter ('mtggoldfish', 'mtgo', or 'both')

        Returns:
            Deck list as text string

        Raises:
            Exception: If download fails
        """
        deck_name = deck.get("name", "Unknown")
        deck_number = deck.get("number", "")

        if not deck_number:
            raise ValueError(f"Deck {deck_name} has no 'number' field")

        logger.info(f"Downloading deck: {deck_name}")
        try:
            # fetch_deck_text handles caching and returns the text directly
            # This avoids unnecessary write-to-file and read-from-file operations
            deck_content = fetch_deck_text(deck_number, source_filter=source_filter)
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

        if not ARCHETYPE_DECKS_CACHE_FILE.exists():
            return None

        try:
            with ARCHETYPE_DECKS_CACHE_FILE.open("r", encoding="utf-8") as fh:
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
            if ARCHETYPE_DECKS_CACHE_FILE.exists():
                with ARCHETYPE_DECKS_CACHE_FILE.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            else:
                data = {}

            # Update entry for this archetype
            data[archetype_url] = {"timestamp": time.time(), "items": items}

            # Save back
            ARCHETYPE_DECKS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with ARCHETYPE_DECKS_CACHE_FILE.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)

            logger.debug(f"Cached {len(items)} decks for archetype")
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to cache decks: {exc}")

    def _filter_decks_by_source(
        self, decks: list[dict[str, Any]], source_filter: str | None
    ) -> list[dict[str, Any]]:
        """
        Filter decks by source.

        Args:
            decks: List of deck dictionaries
            source_filter: Optional source filter ('mtggoldfish', 'mtgo', or 'both')

        Returns:
            Filtered list of decks
        """
        if not source_filter or source_filter == "both":
            return decks

        return [deck for deck in decks if deck.get("source") == source_filter]

    def _get_mtgo_decks_from_db(
        self, archetype_name: str, source_filter: str | None
    ) -> list[dict[str, Any]]:
        """
        Retrieve MTGO decks from JSON cache for a specific archetype.

        Args:
            archetype_name: Name of the archetype
            source_filter: Optional source filter ('mtggoldfish', 'mtgo', or 'both')

        Returns:
            List of MTGO deck dictionaries formatted for UI display
        """
        if source_filter == "mtggoldfish":
            return []

        try:
            from services.mtgo_background_service import load_mtgo_deck_metadata

            mtgo_decks = []
            for fmt in ("modern", "standard", "pioneer", "legacy"):
                decks = load_mtgo_deck_metadata(archetype_name, fmt)
                mtgo_decks.extend(decks)

            logger.debug(f"Retrieved {len(mtgo_decks)} MTGO decks from cache for {archetype_name}")
            return mtgo_decks

        except Exception as exc:
            logger.warning(f"Failed to retrieve MTGO decks from cache: {exc}")
            return []

    def _merge_and_sort_decks(
        self, mtggoldfish_decks: list[dict[str, Any]], mtgo_decks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Merge MTGGoldfish and MTGO decks and sort by date (newest first).

        Args:
            mtggoldfish_decks: Decks from MTGGoldfish
            mtgo_decks: Decks from MTGO (MongoDB)

        Returns:
            Merged and sorted list of decks
        """
        all_decks = mtggoldfish_decks + mtgo_decks

        def parse_date(date_str: str) -> tuple:
            if not date_str:
                return (0, 0, 0)
            try:
                parts = date_str.split("-")
                if len(parts) == 3:
                    return (int(parts[0]), int(parts[1]), int(parts[2]))
                elif "/" in date_str:
                    parts = date_str.split("/")
                    if len(parts) == 3:
                        return (int(parts[2]), int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
            return (0, 0, 0)

        all_decks.sort(key=lambda d: parse_date(d.get("date", "")), reverse=True)
        return all_decks

    def clear_cache(self) -> None:
        """Clear all metagame caches."""
        for cache_file in [ARCHETYPE_LIST_CACHE_FILE, ARCHETYPE_DECKS_CACHE_FILE]:
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
