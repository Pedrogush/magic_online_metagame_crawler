from pathlib import Path

CONFIG_DIR = Path("config")
CACHE_DIR = Path("cache")
DECKS_DIR = Path("decks")
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DECKS_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "config.json"
DECK_MONITOR_CONFIG_FILE = CONFIG_DIR / "deck_monitor_config.json"
DECK_SELECTOR_SETTINGS_FILE = CONFIG_DIR / "deck_selector_settings.json"
LEADERBOARD_POSITIONS_FILE = CONFIG_DIR / "leaderboard_positions.json"

DECK_MONITOR_CACHE_FILE = CACHE_DIR / "deck_monitor_cache.json"
ARCHETYPE_CACHE_FILE = CACHE_DIR / "archetype_cache.json"
ARCHETYPE_LIST_CACHE_FILE = CACHE_DIR / "archetype_list.json"
MTGO_ARTICLES_CACHE_FILE = CACHE_DIR / "mtgo_articles.json"
MTGO_DECK_CACHE_FILE = CACHE_DIR / "mtgo_decks.json"
DECK_CACHE_FILE = CACHE_DIR / "deck_cache.json"
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
    "DECK_CACHE_FILE",
    "CURR_DECK_FILE",
]
