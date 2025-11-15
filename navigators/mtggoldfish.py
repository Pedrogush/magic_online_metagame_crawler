import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

import bs4
from curl_cffi import requests
from loguru import logger

from utils.constants import (
    ARCHETYPE_CACHE_FILE,
    ARCHETYPE_LIST_CACHE_FILE,
    CURR_DECK_FILE,
    DECK_CACHE_FILE,
)
from utils.constants import METAGAME_CACHE_TTL_SECONDS, ONE_DAY_SECONDS


def _load_cached_archetypes(mtg_format: str, max_age: int = METAGAME_CACHE_TTL_SECONDS):
    if not ARCHETYPE_LIST_CACHE_FILE.exists():
        return None
    try:
        with ARCHETYPE_LIST_CACHE_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        logger.warning(f"Cached archetype list invalid: {exc}")
        return None
    entry = data.get(mtg_format)
    if not entry:
        return None
    if time.time() - entry.get("timestamp", 0) > max_age:
        return None
    return entry.get("items")


def _save_cached_archetypes(mtg_format: str, items: list[dict]):
    try:
        if ARCHETYPE_LIST_CACHE_FILE.exists():
            with ARCHETYPE_LIST_CACHE_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            data = {}
    except json.JSONDecodeError:
        data = {}
    data[mtg_format] = {"timestamp": time.time(), "items": items}
    ARCHETYPE_LIST_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ARCHETYPE_LIST_CACHE_FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def get_archetypes(
    mtg_format: str, cache_ttl: int = METAGAME_CACHE_TTL_SECONDS, allow_stale: bool = True
):
    mtg_format = mtg_format.lower()
    cached = _load_cached_archetypes(mtg_format, cache_ttl)
    if cached is not None:
        logger.debug(f"Using cached archetypes for {mtg_format}")
        return cached

    logger.debug(f"Fetching archetypes for {mtg_format} from MTGGoldfish")
    try:
        page = requests.get(
            f"https://www.mtggoldfish.com/metagame/{mtg_format}/full",
            impersonate="chrome",
            timeout=30,
        )
        page.raise_for_status()
    except Exception as exc:
        logger.error(f"Failed to fetch archetype page: {exc}")
        if allow_stale:
            stale = _load_cached_archetypes(mtg_format, max_age=ONE_DAY_SECONDS * 7)
            if stale is not None:
                logger.warning(f"Using stale archetype cache for {mtg_format}")
                return stale
        raise

    soup = bs4.BeautifulSoup(page.text, "lxml")
    metagame_decks = soup.select_one("#metagame-decks-container")
    if not metagame_decks:
        raise RuntimeError("Failed to locate metagame deck container")
    archetypes: list[bs4.Tag] = metagame_decks.find_all("span", attrs={"class": "deck-price-paper"})
    archetypes = [tag for tag in archetypes if tag.find("a") and not tag.find("div")]
    items = [
        {
            "name": tag.text.strip(),
            "href": tag.find("a")["href"].replace("/archetype/", "").replace("#paper", ""),
        }
        for tag in archetypes
    ]
    _save_cached_archetypes(mtg_format, items)
    return items


def get_archetype_decks(archetype: str):
    try:
        page = requests.get(
            f"https://www.mtggoldfish.com/archetype/{archetype}/decks",
            impersonate="chrome",
            timeout=30,
        )
        page.raise_for_status()
    except Exception as exc:
        logger.error(f"Failed to fetch decks for archetype {archetype}: {exc}")
        return []

    soup = bs4.BeautifulSoup(page.text, "lxml")
    table = soup.select_one("table.table-striped")
    if not table:
        logger.warning(f"Deck table missing for archetype {archetype}")
        return []
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
    stats = {}
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                stats = json.load(f)
        except json.JSONDecodeError as exc:
            logger.warning(f"Invalid archetype cache at {cache_path}: {exc}")
            stats = {}
        if (
            mtg_format in stats
            and time.time() - stats[mtg_format].get("timestamp", 0) < ONE_DAY_SECONDS
        ):
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
                [
                    deck
                    for deck in stats[mtg_format][archetype["name"]]["decks"]
                    if date.lower() in deck["date"].lower()
                ]
            )
    ARCHETYPE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ARCHETYPE_CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)
    return stats


def get_daily_decks(mtg_format: str):
    try:
        page = requests.get(
            f"https://www.mtggoldfish.com/metagame/{mtg_format}",
            impersonate="chrome",
            timeout=30,
        )
        page.raise_for_status()
    except Exception as exc:
        logger.error(f"Failed to fetch daily decks for {mtg_format}: {exc}")
        return {}

    soup = bs4.BeautifulSoup(page.text, "lxml")
    table_container = soup.select_one("div.similar-events-container")
    if not table_container:
        logger.warning(f"Daily decks container missing for format {mtg_format}")
        return {}
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
            deck_name = (
                cell.select_one("td.column-deck").select_one("span.deck-price-paper").text.strip()
            )
            deck_number = (
                cell.select_one("td.column-deck")
                .select_one("a")["href"]
                .replace("#online", "")
                .replace("/deck/", "")
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


def _load_deck_cache() -> tuple[dict[str, str], Path, str | None]:
    cache_path = DECK_CACHE_FILE
    deck_cache: dict[str, str] = {}
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as fh:
                deck_cache = json.load(fh)
        except json.JSONDecodeError as exc:
            logger.warning(f"Unable to parse deck cache {cache_path}: {exc}")
            deck_cache = {}
    return deck_cache, cache_path


def _persist_deck_cache(
    deck_cache: dict[str, str], cache_path: Path
) -> None:
    DECK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DECK_CACHE_FILE.open("w", encoding="utf-8") as fh:
        json.dump(deck_cache, fh, indent=4)


def fetch_deck_text(deck_num: str) -> str:
    """
    Return a deck list as text, using the local cache when available.
    """
    deck_cache, cache_path = _load_deck_cache()
    if deck_num in deck_cache:
        return deck_cache[deck_num]

    page = requests.get(f"https://www.mtggoldfish.com/deck/{deck_num}", impersonate="chrome")
    match = re.search(r'initializeDeckComponents\([^,]+,\s*[^,]+,\s*"([^"]+)"', page.text)
    if not match:
        logger.error(f"Could not find deck data for deck {deck_num}")
        raise ValueError(f"Could not parse deck data for deck {deck_num}")
    encoded_deck = match.group(1)
    deck_text = unquote(encoded_deck)

    deck_cache[deck_num] = deck_text
    _persist_deck_cache(deck_cache, cache_path)
    return deck_text


def download_deck(deck_num: str):
    """
    Downloads a deck list and writes it to CURR_DECK_FILE while maintaining cache compatibility.
    """
    deck_text = fetch_deck_text(deck_num)

    CURR_DECK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CURR_DECK_FILE.open("w", encoding="utf-8") as f:
        f.write(deck_text)


if __name__ == "__main__":
    stats = get_archetype_stats("modern")
    print(
        json.dumps(
            {s: stats["modern"][s]["results"] for s in stats["modern"] if "timestamp" not in s},
            indent=8,
        )
    )
    print("done")
