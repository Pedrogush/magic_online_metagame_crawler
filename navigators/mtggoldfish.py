from pathlib import Path

from curl_cffi import requests
import bs4
import json
import time
import re
from urllib.parse import unquote
from datetime import datetime, timedelta
from loguru import logger
from utils.paths import (
    CONFIG_DIR,
    ARCHETYPE_CACHE_FILE,
    DECK_CACHE_FILE,
    CURR_DECK_FILE,
)

LEGACY_ARCHETYPE_CACHE_FILE = Path("archetype_cache.json")
LEGACY_DECK_CACHE_FILE = Path("deck_cache.json")
LEGACY_ARCHETYPE_CACHE_CONFIG_FILE = CONFIG_DIR / "archetype_cache.json"
LEGACY_DECK_CACHE_CONFIG_FILE = CONFIG_DIR / "deck_cache.json"
LEGACY_CURR_DECK_CACHE_FILE = Path("cache") / "curr_deck.txt"
LEGACY_CURR_DECK_ROOT_FILE = Path("curr_deck.txt")


def get_archetypes(mtg_format: str):
    logger.debug(f"Searching for archetypes in {mtg_format}")
    mtg_format = mtg_format.lower()
    page = requests.get(f"https://www.mtggoldfish.com/metagame/{mtg_format}/full", impersonate="chrome")
    soup = bs4.BeautifulSoup(page.text, "html.parser")
    metagame_decks = soup.select_one("#metagame-decks-container")
    archetypes: list[bs4.Tag] = metagame_decks.find_all("span", attrs={"class": "deck-price-paper"})
    archetypes = [tag for tag in archetypes if tag.find("a") and not tag.find("div")]
    return [
        {
            "name": tag.text.strip(),
            "href": tag.find("a")["href"].replace("/archetype/", "").replace("#paper", ""),
        }
        for tag in archetypes
    ]


def get_archetype_decks(archetype: str):
    page = requests.get(f"https://www.mtggoldfish.com/archetype/{archetype}/decks")
    soup = bs4.BeautifulSoup(page.text, "html.parser")
    table = soup.select_one("table.table-striped")
    trs: list[bs4.Tag] = table.find_all("tr")
    trs = trs[1:]
    decks = []
    for tr in trs:
        tds: list[bs4.Tag] = tr.find_all("td")
        decks.append(
            {
                "date": tds[0].text.strip(),
                "number": tds[1].select_one("a").attrs.get("href").replace("/deck/", ""),
                "player": tds[2].text.strip(),
                "event": tds[3].text.strip(),
                "result": tds[4].text.strip(),
                "name": archetype,
            }
        )
    return decks


def get_archetype_stats(mtg_format: str):
    cache_path = ARCHETYPE_CACHE_FILE
    legacy_source = False
    if not cache_path.exists() and LEGACY_ARCHETYPE_CACHE_CONFIG_FILE.exists():
        cache_path = LEGACY_ARCHETYPE_CACHE_CONFIG_FILE
        legacy_source = True
        logger.warning("Loaded legacy archetype_cache.json from config/; migrating to cache/")
    if not cache_path.exists() and LEGACY_ARCHETYPE_CACHE_FILE.exists():
        cache_path = LEGACY_ARCHETYPE_CACHE_FILE
        legacy_source = True
        logger.warning("Loaded legacy archetype_cache.json from project root; migrating to cache/")
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as f:
            stats = json.load(f)
            if mtg_format in stats and time.time() - stats[mtg_format]["timestamp"] < 60 * 60 * 24:
                if legacy_source:
                    try:
                        ARCHETYPE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                        with ARCHETYPE_CACHE_FILE.open("w", encoding="utf-8") as target:
                            json.dump(stats, target, indent=4)
                        if cache_path != ARCHETYPE_CACHE_FILE:
                            try:
                                cache_path.unlink()
                            except OSError as exc:
                                logger.debug(f"Unable to remove legacy archetype cache {cache_path}: {exc}")
                    except OSError as exc:
                        logger.warning(f"Failed to migrate archetype cache: {exc}")
                return stats
    archetypes = get_archetypes(mtg_format)
    stats = {mtg_format: {"timestamp": time.time()}}
    for archetype in archetypes:
        stats[mtg_format][archetype["name"]] = {"decks": get_archetype_decks(archetype["href"])}
        # for day in the past week display the number of decks
        stats[mtg_format][archetype["name"]]["results"] = {}
        for day in range(7):
            date = (datetime.now() - timedelta(days=day)).strftime("%Y-%m-%d")
            stats[mtg_format][archetype["name"]]["results"][date] = len(
                [deck for deck in stats[mtg_format][archetype["name"]]["decks"] if date.lower() in deck["date"].lower()]
            )
    ARCHETYPE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ARCHETYPE_CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)
    return stats


def get_daily_decks(mtg_format: str):
    page = requests.get(f"https://www.mtggoldfish.com/metagame/{mtg_format}")
    soup = bs4.BeautifulSoup(page.text, "html.parser")
    table_container = soup.select_one("div.similar-events-container")
    h4s: list[bs4.Tag] = table_container.find_all("h4")
    decks = {}
    for h4 in h4s:
        date = h4.find("nobr").text.strip().replace("on ", "")
        tournament_type = h4.find("a").text.strip()
        has_placement = "challenge" in tournament_type.lower()
        if date not in decks:
            decks[date] = []
        tbody: bs4.Tag = h4.find_next_sibling()
        cells = tbody.select("tr.striped")
        for cell in cells:
            deck_name = cell.select_one("td.column-deck").select_one("span.deck-price-paper").text.strip()
            deck_number = (
                cell.select_one("td.column-deck").select_one("a")["href"].replace("#online", "").replace("/deck/", "")
            )
            player_name = cell.select_one("td.column-player").text.strip()
            placement = None
            if has_placement:
                placement = cell.select_one("td.column-place").text.strip()
            decks[date].append(
                {
                    "deck_name": deck_name,
                    "player_name": player_name,
                    "tournament_type": tournament_type,
                    "deck_number": deck_number,
                    "placement": placement,
                }
            )
    return decks


def download_deck(deck_num: str):
    """
    Downloads deck list by scraping the deck page (robots.txt compliant).
    Previous implementation used /deck/download/ which is disallowed in robots.txt.
    """
    cache_path = DECK_CACHE_FILE
    legacy_source = None
    if not cache_path.exists() and LEGACY_DECK_CACHE_CONFIG_FILE.exists():
        cache_path = LEGACY_DECK_CACHE_CONFIG_FILE
        legacy_source = "config"
        logger.warning("Loaded legacy deck_cache.json from config/; migrating to cache/")
    if not cache_path.exists() and LEGACY_DECK_CACHE_FILE.exists():
        cache_path = LEGACY_DECK_CACHE_FILE
        legacy_source = "root"
        logger.warning("Loaded legacy deck_cache.json from project root; migrating to cache/")
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as fh:
            deck_cache = json.load(fh)
    else:
        deck_cache = {}
    if deck_num in deck_cache:
        CURR_DECK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CURR_DECK_FILE.open("w", encoding="utf-8") as f:
            f.write(deck_cache[deck_num])
        return

    # Fetch the deck page instead of using /deck/download/ (robots.txt compliant)
    page = requests.get(f"https://www.mtggoldfish.com/deck/{deck_num}", impersonate="chrome")

    # Extract the deck list from JavaScript initialization
    # The deck data is embedded in: initializeDeckComponents(..., ..., "encoded_deck", ...)
    match = re.search(r'initializeDeckComponents\([^,]+,\s*[^,]+,\s*"([^"]+)"', page.text)

    if not match:
        logger.error(f"Could not find deck data for deck {deck_num}")
        raise ValueError(f"Could not parse deck data for deck {deck_num}")

    # URL-decode the deck list
    encoded_deck = match.group(1)
    deck_text = unquote(encoded_deck)

    # Save to file and cache
    CURR_DECK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CURR_DECK_FILE.open("w", encoding="utf-8") as f:
        f.write(deck_text)

    deck_cache[deck_num] = deck_text
    DECK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DECK_CACHE_FILE.open("w", encoding="utf-8") as fh:
        json.dump(deck_cache, fh, indent=4)
    if legacy_source and cache_path != DECK_CACHE_FILE:
        try:
            cache_path.unlink()
        except OSError as exc:
            logger.debug(f"Unable to remove legacy deck cache {cache_path}: {exc}")
    for legacy_curr in (LEGACY_CURR_DECK_CACHE_FILE, LEGACY_CURR_DECK_ROOT_FILE):
        if legacy_curr.exists() and legacy_curr != CURR_DECK_FILE:
            try:
                legacy_curr.unlink()
            except OSError as exc:
                logger.debug(f"Unable to remove legacy deck file {legacy_curr}: {exc}")


if __name__ == "__main__":
    stats = get_archetype_stats("modern")
    print(json.dumps({s:stats['modern'][s]['results'] for s in stats['modern'] if 'timestamp' not in s}, indent=8))
    print("done")
