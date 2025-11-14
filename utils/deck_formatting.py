from __future__ import annotations

from typing import Any

__all__ = ["format_deck_name"]


def format_deck_name(deck: dict[str, Any]) -> str:
    """Compose a compact deck line for list display."""
    date = deck.get("date", "")
    player = deck.get("player", "")
    event = deck.get("event", "")
    result = deck.get("result", "")
    return f"{date} | {player} — {event} [{result}]".strip()
