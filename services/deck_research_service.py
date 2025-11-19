from __future__ import annotations

from typing import Any

from loguru import logger

from navigators import mtggoldfish, mtgo_decklists
from utils.deck import read_curr_deck_file


class DeckResearchService:
    """
    Business logic for loading archetypes/decks and summarizing results.

    Uses MTGO.com as the primary source with MTGGoldfish as fallback for better
    data quality and sustainability.
    """

    def load_archetypes(self, format_name: str, force: bool = False) -> list[dict[str, Any]]:
        """
        Load archetypes for a given format.

        Checks MTGO.com cache first (passive, non-blocking), falls back to MTGGoldfish if not cached.
        Background preloader builds MTGO cache asynchronously.
        """
        fmt = (format_name or "").lower()

        # Check MTGO cache (passive, non-blocking)
        logger.debug(f"Checking MTGO cache for {fmt} archetypes (passive mode)")
        archetypes = mtgo_decklists.get_archetypes(fmt, cache_only=True)
        if archetypes:
            logger.info(f"Successfully loaded {len(archetypes)} archetypes from MTGO cache")
            return archetypes

        # MTGO data not cached - fall back to MTGGoldfish (always available)
        logger.info(f"MTGO cache miss for {fmt}, using MTGGoldfish")
        return mtggoldfish.get_archetypes(fmt, allow_stale=not force)

    def load_decks_for_archetype(self, identifier: str, mtg_format: str | None = None) -> list[dict[str, Any]]:
        """
        Load decks for a specific archetype.

        Checks MTGO.com cache first (passive, non-blocking), falls back to MTGGoldfish if not cached.
        Background preloader builds MTGO cache asynchronously.

        Args:
            identifier: Archetype identifier/href
            mtg_format: Optional format filter (e.g., "Modern", "Standard")
        """
        # Check MTGO cache (passive, non-blocking)
        logger.debug(f"Checking MTGO cache for archetype '{identifier}' format '{mtg_format or 'all'}' (passive mode)")
        decks = mtgo_decklists.get_archetype_decks(identifier, mtg_format=mtg_format, cache_only=True)
        if decks:
            logger.info(f"Successfully loaded {len(decks)} decks from MTGO cache")
            return decks

        # MTGO data not cached - fall back to MTGGoldfish (always available)
        logger.info(f"MTGO cache miss for archetype '{identifier}', using MTGGoldfish")
        return mtggoldfish.get_archetype_decks(identifier)

    def download_deck(self, deck_number: str, deck_payload: dict | None = None) -> None:
        """
        Download a deck and save it to the current deck file.

        Tries MTGO.com first, falls back to MTGGoldfish if needed.

        Args:
            deck_number: Deck identifier (MTGO ID or MTGGoldfish number)
            deck_payload: Optional deck payload dict with _mtgo_payload field for MTGO decks
        """
        # Check if this is an MTGO deck (ID starts with "mtgo_")
        is_mtgo = deck_number.startswith("mtgo_")

        if is_mtgo:
            # This is an MTGO deck - try to use the payload if available
            if deck_payload and "_mtgo_payload" in deck_payload:
                try:
                    logger.info(f"Converting MTGO deck from payload")
                    from navigators.mtgo_decklists import _deck_to_text
                    deck_text = _deck_to_text(deck_payload["_mtgo_payload"])
                    # Write to file
                    from utils.constants import CURR_DECK_FILE
                    CURR_DECK_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with CURR_DECK_FILE.open("w", encoding="utf-8") as f:
                        f.write(deck_text)
                    logger.info(f"Successfully converted MTGO deck from payload")
                    return
                except Exception as exc:
                    logger.error(f"Failed to convert MTGO deck from payload: {exc}")
                    raise ValueError(f"MTGO deck {deck_number} requires deck payload with _mtgo_payload field") from exc
            else:
                # Try to fetch from MTGO cache
                try:
                    logger.info(f"Trying to fetch MTGO deck {deck_number} from cache")
                    deck_text = mtgo_decklists.fetch_deck_text(deck_number)
                    from utils.constants import CURR_DECK_FILE
                    CURR_DECK_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with CURR_DECK_FILE.open("w", encoding="utf-8") as f:
                        f.write(deck_text)
                    logger.info(f"Successfully fetched MTGO deck from cache")
                    return
                except Exception as exc:
                    logger.error(f"MTGO deck {deck_number} not found in cache: {exc}")
                    raise ValueError(f"MTGO deck {deck_number} not available - deck payload required") from exc

        # Not an MTGO deck - use MTGGoldfish
        logger.info(f"Downloading deck {deck_number} from MTGGoldfish")
        mtggoldfish.download_deck(deck_number)

    def download_deck_text(self, deck_number: str, deck_payload: dict | None = None) -> str:
        """
        Download deck and return its text content.

        Args:
            deck_number: Deck identifier (MTGO ID or MTGGoldfish number)
            deck_payload: Optional deck payload dict with _mtgo_payload field for MTGO decks

        Returns:
            Deck text content
        """
        self.download_deck(deck_number, deck_payload)
        return read_curr_deck_file()

    @staticmethod
    def build_archetype_summary(archetype_name: str, decks: list[dict[str, Any]]) -> str:
        by_date: dict[str, int] = {}
        for deck in decks:
            date = str(deck.get("date", "")).lower()
            by_date[date] = by_date.get(date, 0) + 1
        latest_dates = sorted(by_date.items(), reverse=True)[:7]
        lines = [archetype_name, "", f"Total decks loaded: {len(decks)}", ""]
        if latest_dates:
            lines.append("Recent activity:")
            for day, count in latest_dates:
                lines.append(f"  {day}: {count} deck(s)")
        else:
            lines.append("No recent deck activity.")
        return "\n".join(lines)


__all__ = ["DeckResearchService"]
