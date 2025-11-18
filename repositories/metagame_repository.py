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

from navigators import mtggoldfish, mtgo_decklists
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

        Uses MTGO.com as the primary source with MTGGoldfish as fallback.

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

        # Fetch fresh data - try MTGO first
        logger.info(f"Fetching fresh archetypes for {mtg_format} from MTGO.com")
        try:
            archetypes = mtgo_decklists.get_archetypes(mtg_format)
            if archetypes:
                # Cache the results
                self._save_cached_archetypes(mtg_format, archetypes)
                logger.info(f"Successfully fetched {len(archetypes)} archetypes from MTGO.com")
                return archetypes
            else:
                logger.warning(f"No archetypes found on MTGO.com for {mtg_format}, falling back to MTGGoldfish")
        except Exception as exc:
            logger.warning(f"Failed to fetch archetypes from MTGO.com: {exc}, falling back to MTGGoldfish")

        # Fallback to MTGGoldfish
        logger.info(f"Fetching archetypes for {mtg_format} from MTGGoldfish")
        try:
            archetypes = mtggoldfish.get_archetypes(mtg_format)
            # Cache the results
            self._save_cached_archetypes(mtg_format, archetypes)
            logger.info(f"Successfully fetched {len(archetypes)} archetypes from MTGGoldfish")
            return archetypes
        except Exception as exc:
            logger.error(f"Failed to fetch archetypes from MTGGoldfish: {exc}")
            # Try to return stale cache if available
            cached = self._load_cached_archetypes(mtg_format, max_age=None)
            if cached:
                logger.warning(f"Returning stale cached data for {mtg_format}")
                return cached
            raise

    def get_decks_for_archetype(
        self,
        archetype: dict[str, Any],
        mtg_format: str | None = None,
        force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """
        Get deck lists for a specific archetype.

        Uses MTGO.com as the primary source with MTGGoldfish as fallback.

        Args:
            archetype: Archetype dictionary with 'href' or 'url' key
            mtg_format: Optional MTG format to filter by (e.g., "Modern", "Standard")
            force_refresh: If True, bypass cache and fetch fresh data

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
                return cached

        # Fetch fresh data - try MTGO first with format filtering
        logger.info(f"Fetching fresh decks for {archetype_name} in format '{mtg_format or 'all'}' from MTGO.com")
        try:
            # Try to get decks from MTGO using archetype name or href
            decks = mtgo_decklists.get_archetype_decks(archetype_href, mtg_format=mtg_format)
            if decks:
                # Cache the results
                self._save_cached_decks(archetype_href, decks)
                logger.info(f"Successfully fetched {len(decks)} decks from MTGO.com")
                return decks
            else:
                logger.warning(f"No decks found on MTGO.com for {archetype_name}, falling back to MTGGoldfish")
        except Exception as exc:
            logger.warning(f"Failed to fetch decks from MTGO.com: {exc}, falling back to MTGGoldfish")

        # Fallback to MTGGoldfish
        logger.info(f"Fetching decks for {archetype_name} from MTGGoldfish")
        try:
            # get_archetype_decks expects just the href string, not the dict
            decks = mtggoldfish.get_archetype_decks(archetype_href)
            # Cache the results
            self._save_cached_decks(archetype_href, decks)
            logger.info(f"Successfully fetched {len(decks)} decks from MTGGoldfish")
            return decks
        except Exception as exc:
            logger.error(f"Failed to fetch decks from MTGGoldfish: {exc}")
            # Try to return stale cache if available
            cached = self._load_cached_decks(archetype_href, max_age=None)
            if cached:
                logger.warning(f"Returning stale cached decks for {archetype_name}")
                return cached
            raise

    def download_deck_content(self, deck: dict[str, Any]) -> str:
        """
        Download the actual deck list content.

        Uses MTGO.com as the primary source with MTGGoldfish as fallback.

        Args:
            deck: Deck dictionary with 'number' key (deck ID) and optional _mtgo_payload

        Returns:
            Deck list as text string

        Raises:
            Exception: If download fails
        """
        deck_name = deck.get("name", "Unknown")
        deck_number = deck.get("number", "")
        is_mtgo = deck.get("_is_mtgo", False)

        if not deck_number:
            raise ValueError(f"Deck {deck_name} has no 'number' field")

        # Check if this is an MTGO deck (has _mtgo_payload field or _is_mtgo flag)
        mtgo_payload = deck.get("_mtgo_payload")
        if mtgo_payload or is_mtgo:
            if mtgo_payload:
                logger.info(f"Converting MTGO deck from payload: {deck_name}")
                try:
                    # Use the stored payload directly
                    from navigators.mtgo_decklists import _deck_to_text
                    deck_content = _deck_to_text(mtgo_payload)
                    logger.info(f"Successfully converted MTGO deck from payload")
                    return deck_content
                except Exception as exc:
                    logger.warning(f"Failed to use MTGO deck payload: {exc}")

            # Try MTGO cache by deck ID
            logger.info(f"Trying to fetch MTGO deck from cache: {deck_name}")
            try:
                deck_content = mtgo_decklists.fetch_deck_text(deck_number)
                logger.info(f"Successfully fetched MTGO deck from cache")
                return deck_content
            except Exception as exc:
                logger.error(f"MTGO deck {deck_name} not available: {exc}")
                raise ValueError(f"MTGO deck {deck_name} not available in cache") from exc

        # Not an MTGO deck - use MTGGoldfish
        logger.info(f"Downloading deck from MTGGoldfish: {deck_name}")
        try:
            # fetch_deck_text handles caching and returns the text directly
            # This avoids unnecessary write-to-file and read-from-file operations
            deck_content = mtggoldfish.fetch_deck_text(deck_number)
            logger.info(f"Successfully downloaded deck from MTGGoldfish")
            return deck_content
        except Exception as exc:
            logger.error(f"Failed to download deck from MTGGoldfish {deck_name}: {exc}")
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
