"""
Search Service - Business logic for card search and filtering.

This module contains all the business logic for searching and filtering cards:
- Text search
- Color filtering
- Mana cost filtering
- Type filtering
- Advanced search combinations
"""

from typing import Any

from loguru import logger

from repositories.card_repository import CardRepository, get_card_repository
from utils.search_filters import matches_color_filter, matches_mana_cost, matches_mana_value


class SearchService:
    """Service for card search and filtering logic."""

    def __init__(self, card_repository: CardRepository | None = None):
        """
        Initialize the search service.

        Args:
            card_repository: CardRepository instance
        """
        self.card_repo = card_repository or get_card_repository()

    # ============= Basic Search =============

    def search_cards_by_name(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Search for cards by name.

        Args:
            query: Text to search for in card names
            limit: Maximum number of results to return

        Returns:
            List of matching card dictionaries
        """
        if not query:
            return []

        try:
            # Ensure card data is loaded
            if not self.card_repo.is_card_data_loaded():
                logger.warning("Card data not loaded")
                return []

            # Use the card repository to search
            results = self.card_repo.search_cards(query=query)

            # Apply limit
            return results[:limit]

        except Exception as exc:
            logger.error(f"Failed to search cards by name: {exc}")
            return []

    # ============= Advanced Filtering =============

    def filter_cards(
        self,
        cards: list[dict[str, Any]],
        colors: list[str] | None = None,
        color_mode: str = "Any",
        types: list[str] | None = None,
        mana_cost_query: str | None = None,
        mana_cost_mode: str = "at_least",
        mana_value: float | None = None,
        mana_value_comparator: str = "=",
        text_contains: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Filter a list of cards by various criteria.

        Args:
            cards: List of card dictionaries to filter
            colors: List of color codes to filter by (e.g., ['W', 'U'])
            color_mode: How to apply color filter ("Any", "At least", "Exactly", "Not these")
            types: List of type keywords to match (e.g., ['Creature', 'Instant'])
            mana_cost_query: Mana cost pattern to match (e.g., "2GG")
            mana_cost_mode: How to match mana cost ("exact" or "at_least")
            mana_value: Mana value to compare against
            mana_value_comparator: Comparison operator ("<", "≤", "=", "≥", ">")
            text_contains: Text that must appear in card text

        Returns:
            Filtered list of cards
        """
        filtered = cards

        # Apply color filter
        if colors and color_mode != "Any":
            filtered = [
                card
                for card in filtered
                if self._matches_color_filter(card, colors, color_mode)
            ]

        # Apply type filter
        if types:
            filtered = [
                card for card in filtered if self._matches_type_filter(card, types)
            ]

        # Apply mana cost filter
        if mana_cost_query:
            filtered = [
                card
                for card in filtered
                if self._matches_mana_cost_filter(card, mana_cost_query, mana_cost_mode)
            ]

        # Apply mana value filter
        if mana_value is not None:
            filtered = [
                card
                for card in filtered
                if self._matches_mana_value_filter(card, mana_value, mana_value_comparator)
            ]

        # Apply text search filter
        if text_contains:
            filtered = [
                card
                for card in filtered
                if self._matches_text_filter(card, text_contains)
            ]

        return filtered

    # ============= Private Filter Methods =============

    def _matches_color_filter(
        self, card: dict[str, Any], colors: list[str], mode: str
    ) -> bool:
        """Check if card matches color filter."""
        card_colors = card.get("colors", []) or card.get("color_identity", [])
        if isinstance(card_colors, str):
            card_colors = list(card_colors)
        return matches_color_filter(card_colors, colors, mode)

    def _matches_type_filter(self, card: dict[str, Any], types: list[str]) -> bool:
        """Check if card matches type filter."""
        card_type = card.get("type_line", "") or card.get("type", "")
        if not card_type:
            return False

        card_type_lower = card_type.lower()
        return any(type_keyword.lower() in card_type_lower for type_keyword in types)

    def _matches_mana_cost_filter(
        self, card: dict[str, Any], query: str, mode: str
    ) -> bool:
        """Check if card matches mana cost filter."""
        card_cost = card.get("mana_cost", "")
        if not card_cost:
            return False
        return matches_mana_cost(card_cost, query, mode)

    def _matches_mana_value_filter(
        self, card: dict[str, Any], target: float, comparator: str
    ) -> bool:
        """Check if card matches mana value filter."""
        card_value = card.get("cmc") or card.get("mana_value")
        if card_value is None:
            return False
        return matches_mana_value(card_value, target, comparator)

    def _matches_text_filter(self, card: dict[str, Any], query: str) -> bool:
        """Check if card text contains query string."""
        text = card.get("oracle_text", "") or card.get("text", "")
        if not text:
            return False
        return query.lower() in text.lower()

    # ============= Search Suggestions =============

    def get_card_suggestions(
        self, partial_name: str, limit: int = 10
    ) -> list[str]:
        """
        Get card name suggestions based on partial input.

        Args:
            partial_name: Partial card name
            limit: Maximum number of suggestions

        Returns:
            List of suggested card names
        """
        if len(partial_name) < 2:
            return []

        try:
            results = self.search_cards_by_name(partial_name, limit=limit)
            return [card.get("name", "") for card in results if card.get("name")]
        except Exception as exc:
            logger.warning(f"Failed to get card suggestions: {exc}")
            return []

    # ============= Deck-Specific Search =============

    def find_cards_in_deck(
        self, deck_text: str, search_term: str
    ) -> list[tuple[str, int]]:
        """
        Find cards in a deck that match a search term.

        Args:
            deck_text: Deck list as text
            search_term: Term to search for in card names

        Returns:
            List of (card_name, count) tuples
        """
        results = []
        search_lower = search_term.lower()

        for line in deck_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                parts = line.split(" ", 1)
                if len(parts) < 2:
                    continue

                count = int(float(parts[0]))
                card_name = parts[1].strip()

                # Check if search term matches
                if search_lower in card_name.lower():
                    results.append((card_name, count))

            except (ValueError, IndexError):
                continue

        return results

    def group_cards_by_type(
        self, cards: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Group cards by their primary type.

        Args:
            cards: List of card dictionaries

        Returns:
            Dictionary mapping types to card lists
        """
        groups: dict[str, list[dict[str, Any]]] = {
            "Creature": [],
            "Instant": [],
            "Sorcery": [],
            "Enchantment": [],
            "Artifact": [],
            "Planeswalker": [],
            "Land": [],
            "Other": [],
        }

        for card in cards:
            type_line = card.get("type_line", "") or card.get("type", "")
            type_line_lower = type_line.lower()

            # Assign to first matching category
            assigned = False
            for card_type in groups.keys():
                if card_type.lower() in type_line_lower:
                    groups[card_type].append(card)
                    assigned = True
                    break

            if not assigned:
                groups["Other"].append(card)

        # Remove empty groups
        return {k: v for k, v in groups.items() if v}


# Global instance for backward compatibility
_default_service = None


def get_search_service() -> SearchService:
    """Get the default search service instance."""
    global _default_service
    if _default_service is None:
        _default_service = SearchService()
    return _default_service
