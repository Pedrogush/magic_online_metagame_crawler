from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from utils.constants import (
    CONFIG_FILE,
    DECKS_DIR,
    NOTES_STORE,
    OUTBOARD_STORE,
    GUIDE_STORE,
    CARD_INSPECTOR_LOG,
)


__all__ = [
    "DeckPaths",
    "load_deck_paths",
]


@dataclass(frozen=True)
class DeckPaths:
    """Configuration paths for deck management."""

    config: dict[str, Any]
    deck_save_dir: Path
    notes_store: Path
    outboard_store: Path
    guide_store: Path
    card_inspector_log: Path


def load_deck_paths() -> DeckPaths:
    """Load deck configuration and ensure directories exist."""
    config = _load_config()
    deck_save_dir = Path(config.get("deck_selector_save_path") or DECKS_DIR).expanduser()
    try:
        deck_save_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - defensive logging
        logger.warning(f"Unable to create deck save directory '{deck_save_dir}': {exc}")
    config.setdefault("deck_selector_save_path", str(deck_save_dir))

    return DeckPaths(
        config=config,
        deck_save_dir=deck_save_dir,
        notes_store=NOTES_STORE,
        outboard_store=OUTBOARD_STORE,
        guide_store=GUIDE_STORE,
        card_inspector_log=CARD_INSPECTOR_LOG,
    )


def _load_config() -> dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as cfg_file:
                return json.load(cfg_file)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
            logger.warning(f"Invalid {CONFIG_FILE} ({exc}); using default deck save path")
            return {}

    logger.debug(f"{CONFIG_FILE} not found; using default deck save path")
    return {}

