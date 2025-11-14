from __future__ import annotations

from typing import Any

from navigators.mtggoldfish import download_deck, get_archetype_decks, get_archetypes
from utils.deck import read_curr_deck_file


class DeckResearchService:
    """Business logic for loading archetypes/decks and summarizing results."""

    def load_archetypes(self, format_name: str, force: bool = False) -> list[dict[str, Any]]:
        fmt = (format_name or "").lower()
        return get_archetypes(fmt, allow_stale=not force)

    def load_decks_for_archetype(self, identifier: str) -> list[dict[str, Any]]:
        return get_archetype_decks(identifier)

    def download_deck(self, deck_number: str) -> None:
        download_deck(deck_number)

    def download_deck_text(self, deck_number: str) -> str:
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
