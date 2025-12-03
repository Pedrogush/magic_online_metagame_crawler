"""Constants file."""

import os
import sys
from pathlib import Path

BRIDGE_PATH = "dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/win-x64/MTGOBridge.exe"
APP_NAME = "MTGO Metagame Deck Builder"


def _default_base_dir() -> Path:
    """Return the writable base directory for config/cache/logging."""
    if getattr(sys, "frozen", False):
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / APP_NAME
        return Path.home() / ".mtgo_metagame_deck_builder"
    return Path(__file__).resolve().parent.parent


SUBDUED_TEXT = (185, 191, 202)
DARK_BG = (20, 22, 27)
DARK_PANEL = (34, 39, 46)
DARK_ALT = (40, 46, 54)
DARK_ACCENT = (59, 130, 246)
LIGHT_TEXT = (236, 236, 236)

ZONE_TITLES = {
    "main": "Mainboard",
    "side": "Sideboard",
    "out": "Outboard",
}

__all__ = [
    "SUBDUED_TEXT",
    "DARK_BG",
    "DARK_PANEL",
    "DARK_ALT",
    "DARK_ACCENT",
    "LIGHT_TEXT",
    "ZONE_TITLES",
]

BASE_DATA_DIR = _default_base_dir()
CONFIG_DIR = BASE_DATA_DIR / "config"
CACHE_DIR = BASE_DATA_DIR / "cache"
DECKS_DIR = BASE_DATA_DIR / "decks"
DECK_SAVE_DIR = DECKS_DIR
LOGS_DIR = BASE_DATA_DIR / "logs"


def ensure_base_dirs() -> None:
    """Ensure base config/cache/deck/log directories exist without importing side effects."""
    BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in (CONFIG_DIR, CACHE_DIR, DECKS_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)


CONFIG_FILE = CONFIG_DIR / "config.json"
DECK_MONITOR_CONFIG_FILE = CONFIG_DIR / "deck_monitor_config.json"
DECK_SELECTOR_SETTINGS_FILE = CONFIG_DIR / "deck_selector_settings.json"
LEADERBOARD_POSITIONS_FILE = CONFIG_DIR / "leaderboard_positions.json"

DECK_MONITOR_CACHE_FILE = CACHE_DIR / "deck_monitor_cache.json"
ARCHETYPE_CACHE_FILE = CACHE_DIR / "archetype_cache.json"
ARCHETYPE_LIST_CACHE_FILE = CACHE_DIR / "archetype_list.json"
MTGO_ARTICLES_CACHE_FILE = CACHE_DIR / "mtgo_articles.json"
MTGO_DECK_CACHE_FILE = CACHE_DIR / "mtgo_decks.json"
# Separate cache files to avoid collision between different data structures
DECK_TEXT_CACHE_FILE = CACHE_DIR / "deck_text_cache.json"  # Individual deck content
ARCHETYPE_DECKS_CACHE_FILE = CACHE_DIR / "archetype_decks_cache.json"  # Deck lists per archetype
# Legacy name for backward compatibility (points to deck text cache)
DECK_CACHE_FILE = DECK_TEXT_CACHE_FILE
CURR_DECK_FILE = DECKS_DIR / "curr_deck.txt"

__all__ = [
    "CONFIG_DIR",
    "CACHE_DIR",
    "DECKS_DIR",
    "CONFIG_FILE",
    "DECK_MONITOR_CONFIG_FILE",
    "DECK_MONITOR_CACHE_FILE",
    "DECK_SELECTOR_SETTINGS_FILE",
    "LEADERBOARD_POSITIONS_FILE",
    "ARCHETYPE_CACHE_FILE",
    "ARCHETYPE_LIST_CACHE_FILE",
    "MTGO_ARTICLES_CACHE_FILE",
    "MTGO_DECK_CACHE_FILE",
    "DECK_TEXT_CACHE_FILE",
    "ARCHETYPE_DECKS_CACHE_FILE",
    "DECK_CACHE_FILE",
    "CURR_DECK_FILE",
    "ensure_base_dirs",
]

"""Gameplay-related constants shared across services."""

FULL_MANA_SYMBOLS: list[str] = (
    ["W", "U", "B", "R", "G", "C", "S", "X", "Y", "Z", "∞", "½"]
    + [str(i) for i in range(0, 21)]
    + [
        "W/U",
        "W/B",
        "U/B",
        "U/R",
        "B/R",
        "B/G",
        "R/G",
        "R/W",
        "G/W",
        "G/U",
        "C/W",
        "C/U",
        "C/B",
        "C/R",
        "C/G",
        "2/W",
        "2/U",
        "2/B",
        "2/R",
        "2/G",
        "W/P",
        "U/P",
        "B/P",
        "R/P",
        "G/P",
    ]
)

FORMAT_OPTIONS = [
    "Modern",
    "Standard",
    "Pioneer",
    "Legacy",
    "Vintage",
    "Pauper",
    "Commander",
    "Brawl",
    "Historic",
]

__all__ = ["FULL_MANA_SYMBOLS", "FORMAT_OPTIONS"]

CHALLENGE_LOOKUP_OPTIONS = (
    "Modern",
    "Pioneer",
    "Legacy",
    "Duel Commander",
    "Vintage",
    "Limited",
)
GOLDFISH = "https://www.mtggoldfish.com/player/"

"""Service-level configuration defaults shared across modules."""

ONE_HOUR_SECONDS = 60 * 60
ONE_DAY_SECONDS = 24 * 60 * 60

# Collection inventory refresh settings
COLLECTION_CACHE_MAX_AGE_SECONDS = ONE_HOUR_SECONDS

# Metagame scraping cache TTL
METAGAME_CACHE_TTL_SECONDS = ONE_HOUR_SECONDS

# Card image bulk data refresh thresholds
DEFAULT_BULK_DATA_MAX_AGE_DAYS = 30
BULK_DATA_CACHE_FRESHNESS_SECONDS = DEFAULT_BULK_DATA_MAX_AGE_DAYS * ONE_DAY_SECONDS

NOTES_STORE = CACHE_DIR / "deck_notes.json"
OUTBOARD_STORE = CACHE_DIR / "deck_outboard.json"
GUIDE_STORE = CACHE_DIR / "deck_sbguides.json"
CARD_INSPECTOR_LOG = CACHE_DIR / "card_inspector_debug.log"

ATOMIC_DATA_URL = "https://mtgjson.com/api/v5/AtomicCards.json.zip"

DECK_SELECTOR_MANA_ICON_SIZE = int(26 * 0.7)
BULK_CACHE_MIN_AGE_DAYS = 1
BULK_CACHE_MAX_AGE_DAYS = 365
