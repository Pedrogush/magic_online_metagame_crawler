"""Service for deck operations - loading, saving, downloading, and parsing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from navigators.mtggoldfish import download_deck, get_archetype_decks
from utils.dbq import save_deck_to_db
from utils.deck import add_dicts, analyze_deck, deck_to_dictionary


class DeckService:
    """Handles all deck-related business logic."""

    def __init__(self, deck_save_dir: Path):
        """Initialize deck service with save directory.

        Args:
            deck_save_dir: Directory where decks will be saved
        """
        self.deck_save_dir = deck_save_dir
        self.deck_save_dir.mkdir(parents=True, exist_ok=True)

    def download_deck(self, deck: dict[str, Any]) -> str:
        """Download deck content from MTGGoldfish.

        Args:
            deck: Deck metadata dictionary with 'number' key

        Returns:
            Deck text content

        Raises:
            ValueError: If deck download fails
        """
        deck_num = deck.get("number", "")
        if not deck_num:
            raise ValueError("Deck number not found")

        logger.info(f"Downloading deck {deck_num}")
        deck_text = download_deck(deck_num)
        return deck_text

    def parse_deck(self, deck_text: str) -> dict[str, list[dict[str, Any]]]:
        """Parse deck text into structured zones.

        Args:
            deck_text: Raw deck text

        Returns:
            Dictionary with 'main', 'side', and 'out' zones
        """
        lines = deck_text.strip().split("\n")
        zones: dict[str, list[dict[str, Any]]] = {"main": [], "side": [], "out": []}
        current_zone = "main"

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("sideboard"):
                current_zone = "side"
                continue

            # Parse quantity and name
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue

            try:
                qty = int(parts[0])
                name = parts[1]
                zones[current_zone].append({"name": name, "quantity": qty})
            except ValueError:
                continue

        return zones

    def build_deck_text(self, zones: dict[str, list[dict[str, Any]]]) -> str:
        """Build deck text from zone data.

        Args:
            zones: Dictionary with 'main' and 'side' zones

        Returns:
            Formatted deck text
        """
        lines: list[str] = []

        # Mainboard
        for card in zones.get("main", []):
            lines.append(f"{card['quantity']} {card['name']}")

        # Sideboard
        side_cards = zones.get("side", [])
        if side_cards:
            lines.append("")
            lines.append("Sideboard")
            for card in side_cards:
                lines.append(f"{card['quantity']} {card['name']}")

        return "\n".join(lines)

    def save_deck(self, deck_text: str, name: str) -> Path:
        """Save deck to file.

        Args:
            deck_text: Deck content
            name: Base filename

        Returns:
            Path to saved file

        Raises:
            OSError: If save fails
        """
        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-"))
        if not safe_name:
            safe_name = "deck"

        filepath = self.deck_save_dir / f"{safe_name}.txt"

        # Add number if file exists
        counter = 1
        while filepath.exists():
            filepath = self.deck_save_dir / f"{safe_name}_{counter}.txt"
            counter += 1

        logger.info(f"Saving deck to {filepath}")
        filepath.write_text(deck_text, encoding="utf-8")
        return filepath

    def save_to_db(self, deck_text: str, metadata: dict[str, Any] | None = None) -> None:
        """Save deck to database.

        Args:
            deck_text: Deck content
            metadata: Optional deck metadata (format, archetype, etc.)
        """
        try:
            save_deck_to_db(deck_text, metadata or {})
            logger.debug("Saved deck to database")
        except Exception as exc:
            logger.error(f"Failed to save deck to database: {exc}")

    def analyze_deck(self, deck_text: str) -> dict[str, Any]:
        """Analyze deck and return statistics.

        Args:
            deck_text: Deck content

        Returns:
            Dictionary with deck statistics (curve, colors, etc.)
        """
        return analyze_deck(deck_text)

    def deck_to_dictionary(self, deck_text: str) -> dict[str, int]:
        """Convert deck text to card name -> quantity dictionary.

        Args:
            deck_text: Deck content

        Returns:
            Dictionary mapping card names to quantities
        """
        return deck_to_dictionary(deck_text)

    def build_daily_average(
        self, decks: list[dict[str, Any]], format_name: str
    ) -> tuple[dict[str, float], int]:
        """Build average deck from multiple decklists.

        Args:
            decks: List of deck dictionaries with 'number' key
            format_name: Format name for fetching deck data

        Returns:
            Tuple of (card frequency buffer, number of decks processed)
        """
        deck_buffer: dict[str, float] = {}
        decks_added = 0

        for deck in decks:
            try:
                deck_num = deck.get("number", "")
                if not deck_num:
                    continue

                deck_text = download_deck(deck_num)
                deck_dict = self.deck_to_dictionary(deck_text)

                deck_buffer = add_dicts(deck_buffer, deck_dict)
                decks_added += 1
                logger.debug(f"Added deck {deck_num} to average ({decks_added} total)")
            except Exception as exc:
                logger.warning(f"Failed to process deck {deck.get('number')}: {exc}")
                continue

        return deck_buffer, decks_added

    def render_average_deck(self, buffer: dict[str, float], decks_added: int) -> str:
        """Render average deck from frequency buffer.

        Args:
            buffer: Card frequencies
            decks_added: Number of decks in average

        Returns:
            Formatted deck text
        """
        if decks_added == 0:
            return ""

        # Calculate average quantities
        averaged: dict[str, float] = {
            name: count / decks_added for name, count in buffer.items()
        }

        # Sort by frequency and group
        main_cards: list[tuple[str, float]] = []
        side_cards: list[tuple[str, float]] = []

        for name, freq in sorted(averaged.items(), key=lambda x: -x[1]):
            # Assume mainboard cards appear in >50% of decks
            if freq >= 0.5:
                main_cards.append((name, freq))
            else:
                side_cards.append((name, freq))

        lines: list[str] = []
        lines.append(f"# Average of {decks_added} decks")
        lines.append("")

        # Mainboard
        for name, freq in main_cards:
            qty = round(freq)
            if qty > 0:
                lines.append(f"{qty} {name}")

        # Sideboard
        if side_cards:
            lines.append("")
            lines.append("Sideboard")
            for name, freq in side_cards:
                qty = round(freq)
                if qty > 0:
                    lines.append(f"{qty} {name}")

        return "\n".join(lines)
