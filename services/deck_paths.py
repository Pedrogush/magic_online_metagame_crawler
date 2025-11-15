from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from utils.constants import CACHE_DIR, CONFIG_FILE, DECKS_DIR

LEGACY_CONFIG_FILE = Path("config.json")
LEGACY_CURR_DECK_CACHE = Path("cache") / "curr_deck.txt"
LEGACY_CURR_DECK_ROOT = Path("curr_deck.txt")
NOTES_STORE = CACHE_DIR / "deck_notes.json"
OUTBOARD_STORE = CACHE_DIR / "deck_outboard.json"
GUIDE_STORE = CACHE_DIR / "deck_sbguides.json"
LEGACY_NOTES_STORE = CACHE_DIR / "deck_notes_wx.json"
LEGACY_OUTBOARD_STORE = CACHE_DIR / "deck_outboard_wx.json"
LEGACY_GUIDE_STORE = CACHE_DIR / "deck_sbguides_wx.json"
CARD_INSPECTOR_LOG = CACHE_DIR / "card_inspector_debug.log"

__all__ = [
    "CARD_INSPECTOR_LOG",
    "DeckPaths",
    "GUIDE_STORE",
    "LEGACY_CONFIG_FILE",
    "LEGACY_CURR_DECK_CACHE",
    "LEGACY_CURR_DECK_ROOT",
    "LEGACY_GUIDE_STORE",
    "LEGACY_NOTES_STORE",
    "LEGACY_OUTBOARD_STORE",
    "NOTES_STORE",
    "OUTBOARD_STORE",
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

    _migrate_legacy_stores()

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

    if LEGACY_CONFIG_FILE.exists():
        try:
            with LEGACY_CONFIG_FILE.open("r", encoding="utf-8") as cfg_file:
                config = json.load(cfg_file)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
            logger.warning(f"Invalid legacy config.json ({exc}); using default deck save path")
            return {}

        logger.warning(
            "Loaded legacy config.json from project root; migrating to config/ directory"
        )
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with CONFIG_FILE.open("w", encoding="utf-8") as fh:
                json.dump(config, fh, indent=4)
        except OSError as exc:
            logger.warning(f"Failed to write migrated config.json: {exc}")
        return config

    logger.debug(f"{CONFIG_FILE} not found; using default deck save path")
    return {}


def _migrate_legacy_stores() -> None:
    for new_path, legacy_path in (
        (NOTES_STORE, LEGACY_NOTES_STORE),
        (OUTBOARD_STORE, LEGACY_OUTBOARD_STORE),
        (GUIDE_STORE, LEGACY_GUIDE_STORE),
    ):
        if not new_path.exists() and legacy_path.exists():
            try:
                legacy_path.replace(new_path)
                logger.info(f"Migrated {legacy_path.name} to {new_path.name}")
            except OSError as exc:  # pragma: no cover - migration best-effort
                logger.warning(f"Failed to migrate {legacy_path} to {new_path}: {exc}")
