"""Service for deck analysis - statistics, curve, colors, etc."""

from __future__ import annotations

from collections import Counter
from typing import Any

from loguru import logger

from utils.deck import analyze_deck, deck_to_dictionary


class DeckAnalysisService:
    """Handles deck analysis and statistics."""

    def analyze(self, deck_text: str) -> dict[str, Any]:
        """Analyze deck and return comprehensive statistics.

        Args:
            deck_text: Deck content

        Returns:
            Dictionary with analysis results
        """
        return analyze_deck(deck_text)

    def calculate_mana_curve(self, cards: list[dict[str, Any]]) -> dict[int, int]:
        """Calculate mana curve from card list.

        Args:
            cards: List of card dictionaries with 'mana_value' and 'quantity'

        Returns:
            Dictionary mapping mana value to quantity
        """
        curve: dict[int, int] = {}

        for card in cards:
            mv = card.get("mana_value")
            qty = card.get("quantity", 1)

            if mv is not None:
                try:
                    mv_int = int(mv)
                    # Cap at 7+ for display
                    mv_int = min(mv_int, 7)
                    curve[mv_int] = curve.get(mv_int, 0) + qty
                except (ValueError, TypeError):
                    continue

        return curve

    def calculate_color_distribution(
        self, cards: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Calculate color distribution from card list.

        Args:
            cards: List of card dictionaries with 'colors' and 'quantity'

        Returns:
            Dictionary mapping colors to symbol counts
        """
        color_symbols: dict[str, int] = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}

        for card in cards:
            mana_cost = card.get("mana_cost", "")
            qty = card.get("quantity", 1)

            # Count each symbol in mana cost
            for char in mana_cost:
                if char in color_symbols:
                    color_symbols[char] += qty

        return color_symbols

    def identify_key_cards(
        self, cards: list[dict[str, Any]], threshold: int = 3
    ) -> list[dict[str, Any]]:
        """Identify key cards (3-4 copies typically).

        Args:
            cards: List of card dictionaries
            threshold: Minimum quantity to be considered key

        Returns:
            List of key cards
        """
        key_cards: list[dict[str, Any]] = []

        for card in cards:
            qty = card.get("quantity", 0)
            if qty >= threshold:
                key_cards.append(card)

        return key_cards

    def calculate_deck_totals(
        self, zones: dict[str, list[dict[str, Any]]]
    ) -> dict[str, int]:
        """Calculate total cards in each zone.

        Args:
            zones: Dictionary with 'main', 'side', 'out' zones

        Returns:
            Dictionary with zone totals
        """
        totals: dict[str, int] = {}

        for zone_name, cards in zones.items():
            total = sum(card.get("quantity", 0) for card in cards)
            totals[zone_name] = total

        return totals

    def find_duplicates(
        self, main_cards: list[dict[str, Any]], side_cards: list[dict[str, Any]]
    ) -> list[str]:
        """Find cards appearing in both mainboard and sideboard.

        Args:
            main_cards: Mainboard card list
            side_cards: Sideboard card list

        Returns:
            List of duplicate card names
        """
        main_names = {card["name"] for card in main_cards}
        side_names = {card["name"] for card in side_cards}

        duplicates = main_names & side_names
        return list(duplicates)

    def validate_deck(
        self, zones: dict[str, list[dict[str, Any]]], format_name: str | None = None
    ) -> dict[str, Any]:
        """Validate deck against format rules.

        Args:
            zones: Dictionary with deck zones
            format_name: Optional format name for specific validation

        Returns:
            Dictionary with validation results
        """
        totals = self.calculate_deck_totals(zones)
        main_total = totals.get("main", 0)
        side_total = totals.get("side", 0)

        issues: list[str] = []

        # Minimum deck size (60 for constructed)
        if format_name != "Commander" and main_total < 60:
            issues.append(f"Mainboard has {main_total} cards (minimum 60)")

        # Sideboard size (max 15 for most formats)
        if format_name != "Commander" and side_total > 15:
            issues.append(f"Sideboard has {side_total} cards (maximum 15)")

        # Check for duplicates
        duplicates = self.find_duplicates(zones.get("main", []), zones.get("side", []))
        if duplicates:
            issues.append(f"Cards in both main and side: {', '.join(duplicates[:3])}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "totals": totals,
        }

    def calculate_card_type_distribution(
        self, cards: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Calculate distribution by card type.

        Args:
            cards: List of card dictionaries

        Returns:
            Dictionary mapping types to quantities
        """
        type_counts: dict[str, int] = {}

        for card in cards:
            type_line = card.get("type_line", "")
            qty = card.get("quantity", 1)

            # Extract primary type
            if "—" in type_line:
                primary = type_line.split("—")[0].strip()
            else:
                primary = type_line

            # Count each type keyword
            for type_name in ["Creature", "Instant", "Sorcery", "Enchantment", "Artifact", "Planeswalker", "Land"]:
                if type_name in primary:
                    type_counts[type_name] = type_counts.get(type_name, 0) + qty
                    break

        return type_counts
