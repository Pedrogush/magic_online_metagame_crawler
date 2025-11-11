"""Service for archetype operations - fetching, filtering, and managing archetypes."""

from __future__ import annotations

from typing import Any

from loguru import logger

from navigators.mtggoldfish import get_archetype_decks, get_archetypes


class ArchetypeService:
    """Handles all archetype-related business logic."""

    def __init__(self):
        """Initialize archetype service."""
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def fetch_archetypes(self, format_name: str, force: bool = False) -> list[dict[str, Any]]:
        """Fetch archetypes for a format.

        Args:
            format_name: MTG format (Modern, Pioneer, etc.)
            force: Force refresh from server

        Returns:
            List of archetype dictionaries

        Raises:
            Exception: If fetch fails
        """
        cache_key = format_name.lower()

        if not force and cache_key in self._cache:
            logger.debug(f"Using cached archetypes for {format_name}")
            return self._cache[cache_key]

        logger.info(f"Fetching archetypes for {format_name}")
        archetypes = get_archetypes(format_name.lower())
        self._cache[cache_key] = archetypes
        return archetypes

    def filter_archetypes(
        self, archetypes: list[dict[str, Any]], query: str
    ) -> list[dict[str, Any]]:
        """Filter archetypes by search query.

        Args:
            archetypes: List of archetypes to filter
            query: Search string

        Returns:
            Filtered list of archetypes
        """
        if not query or not query.strip():
            return archetypes

        query_lower = query.strip().lower()
        filtered: list[dict[str, Any]] = []

        for archetype in archetypes:
            name = archetype.get("name", "").lower()
            if query_lower in name:
                filtered.append(archetype)

        return filtered

    def fetch_decks_for_archetype(
        self, format_name: str, archetype_name: str
    ) -> list[dict[str, Any]]:
        """Fetch decklists for a specific archetype.

        Args:
            format_name: MTG format
            archetype_name: Archetype name

        Returns:
            List of deck dictionaries

        Raises:
            Exception: If fetch fails
        """
        logger.info(f"Fetching decks for {archetype_name} in {format_name}")
        decks = get_archetype_decks(format_name, archetype_name)
        return decks

    def clear_cache(self) -> None:
        """Clear archetype cache."""
        self._cache.clear()
        logger.debug("Cleared archetype cache")

    def get_archetype_summary(
        self, archetype_name: str, decks: list[dict[str, Any]]
    ) -> str:
        """Generate summary text for an archetype.

        Args:
            archetype_name: Name of the archetype
            decks: List of decks for this archetype

        Returns:
            Formatted summary text
        """
        if not decks:
            return f"No decks found for {archetype_name}"

        lines: list[str] = []
        lines.append(f"Archetype: {archetype_name}")
        lines.append(f"Decklists: {len(decks)}")
        lines.append("")

        # Extract player and event info
        players: set[str] = set()
        events: set[str] = set()

        for deck in decks[:10]:  # Limit to first 10 for summary
            player = deck.get("player", "")
            event = deck.get("event", "")
            if player:
                players.add(player)
            if event:
                events.add(event)

        if players:
            lines.append(f"Players: {', '.join(sorted(players)[:5])}")
        if events:
            lines.append(f"Events: {', '.join(sorted(events)[:3])}")

        return "\n".join(lines)
