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

        Tries MTGO.com first, falls back to MTGGoldfish if needed.
        """
        fmt = (format_name or "").lower()

        # Try MTGO first
        try:
            logger.info(f"Loading archetypes for {fmt} from MTGO.com")
            archetypes = mtgo_decklists.get_archetypes(fmt)
            if archetypes:
                logger.info(f"Successfully loaded {len(archetypes)} archetypes from MTGO.com")
                return archetypes
            else:
                logger.warning(f"No archetypes found on MTGO.com for {fmt}, falling back to MTGGoldfish")
        except Exception as exc:
            logger.warning(f"Failed to load archetypes from MTGO.com: {exc}, falling back to MTGGoldfish")

        # Fallback to MTGGoldfish
        logger.info(f"Loading archetypes for {fmt} from MTGGoldfish")
        return mtggoldfish.get_archetypes(fmt, allow_stale=not force)

    def load_decks_for_archetype(self, identifier: str) -> list[dict[str, Any]]:
        """
        Load decks for a specific archetype.

        Tries MTGO.com first, falls back to MTGGoldfish if needed.
        """
        # Try MTGO first
        try:
            logger.info(f"Loading decks for archetype '{identifier}' from MTGO.com")
            decks = mtgo_decklists.get_archetype_decks(identifier)
            if decks:
                logger.info(f"Successfully loaded {len(decks)} decks from MTGO.com")
                return decks
            else:
                logger.warning(f"No decks found on MTGO.com for '{identifier}', falling back to MTGGoldfish")
        except Exception as exc:
            logger.warning(f"Failed to load decks from MTGO.com: {exc}, falling back to MTGGoldfish")

        # Fallback to MTGGoldfish
        logger.info(f"Loading decks for archetype '{identifier}' from MTGGoldfish")
        return mtggoldfish.get_archetype_decks(identifier)

    def download_deck(self, deck_number: str) -> None:
        """
        Download a deck and save it to the current deck file.

        Tries MTGO.com first, falls back to MTGGoldfish if needed.
        """
        # Try MTGO first
        try:
            logger.info(f"Downloading deck {deck_number} from MTGO.com")
            deck_text = mtgo_decklists.fetch_deck_text(deck_number)
            # Write to file (matching mtggoldfish.download_deck behavior)
            from utils.constants import CURR_DECK_FILE
            CURR_DECK_FILE.parent.mkdir(parents=True, exist_ok=True)
            with CURR_DECK_FILE.open("w", encoding="utf-8") as f:
                f.write(deck_text)
            logger.info(f"Successfully downloaded deck from MTGO.com")
            return
        except Exception as exc:
            logger.warning(f"Failed to download deck from MTGO.com: {exc}, falling back to MTGGoldfish")

        # Fallback to MTGGoldfish
        logger.info(f"Downloading deck {deck_number} from MTGGoldfish")
        mtggoldfish.download_deck(deck_number)

    def download_deck_text(self, deck_number: str) -> str:
        """Download deck and return its text content."""
        self.download_deck(deck_number)
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
