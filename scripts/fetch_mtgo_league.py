"""Download and parse a single MTGO Modern League page."""

import json
from datetime import datetime
from pathlib import Path

from navigators.mtgo_decklists import fetch_deck_event, fetch_decklist_index
from utils.constants import ARCHETYPE_CACHE_FILE
from utils.deck_text_cache import get_deck_cache
from utils.simple_archetype_detector import detect_modern_archetype


def convert_mtgo_deck_to_classifier_format(deck: dict) -> dict:
    """Convert MTGO deck format to the format expected by ArchetypeClassifier."""
    mainboard = []
    sideboard = []

    for card in deck.get("main_deck", []):
        if card.get("sideboard") == "false":
            card_name = card.get("card_attributes", {}).get("card_name", "")
            qty = int(card.get("qty", "1"))
            if card_name:
                mainboard.append({"name": card_name, "count": qty})

    for card in deck.get("sideboard_deck", []):
        card_name = card.get("card_attributes", {}).get("card_name", "")
        qty = int(card.get("qty", "1"))
        if card_name:
            sideboard.append({"name": card_name, "count": qty})

    return {
        "mainboard": mainboard,
        "sideboard": sideboard,
        "format": "modern"
    }


def deck_to_text(deck: dict) -> str:
    """Convert MTGO deck data to text format matching MTGGoldfish."""
    lines = []

    main_deck = deck.get("main_deck", [])
    for card in main_deck:
        if card.get("sideboard") == "false":
            qty = card.get("qty", "1")
            name = card.get("card_attributes", {}).get("card_name", "Unknown")
            lines.append(f"{qty} {name}")

    lines.append("sideboard")
    sideboard = deck.get("sideboard_deck", [])
    for card in sideboard:
        qty = card.get("qty", "1")
        name = card.get("card_attributes", {}).get("card_name", "Unknown")
        lines.append(f"{qty} {name}")

    return "\n".join(lines) + "\n"


def parse_mtgo_league_to_archetype_format(url: str) -> dict:
    """
    Parse an MTGO league page and return data in mtggoldfish archetype format.

    Returns a dictionary with archetypes as keys, each containing a list of decks.
    """
    payload = fetch_deck_event(url)

    archetypes = {}
    event_date = payload.get("publish_date", datetime.now().isoformat()[:10])
    deck_cache = get_deck_cache()

    for deck in payload.get("decklists", []):
        classifier_deck = convert_mtgo_deck_to_classifier_format(deck)
        archetype_name = detect_modern_archetype(classifier_deck["mainboard"])
        player = deck.get("player") or deck.get("pilot") or "Unknown"

        wins_data = deck.get("wins", {})
        if isinstance(wins_data, dict):
            wins = wins_data.get("wins", "5")
            losses = wins_data.get("losses", "0")
        else:
            wins = "5"
            losses = "0"

        deck_id = deck.get("loginplayeventcourseid") or str(hash(player + event_date))

        deck_text = deck_to_text(deck)
        deck_cache.set(deck_id, deck_text)

        if archetype_name not in archetypes:
            archetypes[archetype_name] = {"decks": [], "results": {event_date: 0}}

        deck_entry = {
            "date": event_date,
            "number": str(deck_id),
            "player": player,
            "event": "Modern League",
            "result": f"{wins}-{losses}",
            "name": archetype_name,
        }

        archetypes[archetype_name]["decks"].append(deck_entry)
        archetypes[archetype_name]["results"][event_date] += 1

    return archetypes


def fetch_latest_modern_league():
    """Fetch the latest Modern League from MTGO."""
    now = datetime.now()
    entries = fetch_decklist_index(now.year, now.month)

    modern_leagues = [
        e
        for e in entries
        if e.get("format") and "modern" in e["format"].lower() and e.get("event_type") == "league"
    ]

    if not modern_leagues:
        print("No Modern League found in current month")
        return None

    entry = modern_leagues[0]
    print(f"Found Modern League: {entry['title']}")
    print(f"URL: {entry['url']}")
    print(f"Date: {entry['publish_date']}")

    archetypes = parse_mtgo_league_to_archetype_format(entry["url"])

    if ARCHETYPE_CACHE_FILE.exists():
        with ARCHETYPE_CACHE_FILE.open("r", encoding="utf-8") as f:
            cache_data = json.load(f)
    else:
        cache_data = {}

    if "modern" not in cache_data:
        cache_data["modern"] = {"timestamp": datetime.now().timestamp()}
    else:
        cache_data["modern"]["timestamp"] = datetime.now().timestamp()

    for archetype_name, archetype_data in archetypes.items():
        if archetype_name not in cache_data["modern"]:
            cache_data["modern"][archetype_name] = archetype_data
        else:
            existing_deck_nums = {
                d["number"] for d in cache_data["modern"][archetype_name]["decks"]
            }
            new_decks = [
                d for d in archetype_data["decks"] if d["number"] not in existing_deck_nums
            ]
            cache_data["modern"][archetype_name]["decks"].extend(new_decks)

            for date, count in archetype_data["results"].items():
                if date not in cache_data["modern"][archetype_name]["results"]:
                    cache_data["modern"][archetype_name]["results"][date] = count

    ARCHETYPE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ARCHETYPE_CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=4)

    print(f"\nSaved {len(archetypes)} archetypes to {ARCHETYPE_CACHE_FILE}")
    print(f"Total decks: {sum(len(a['decks']) for a in archetypes.values())}")
    return cache_data


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"Fetching Modern League from URL: {url}")
        archetypes = parse_mtgo_league_to_archetype_format(url)

        output = {"modern": {"timestamp": datetime.now().timestamp(), **archetypes}}

        output_file = Path("cache") / "mtgo_modern_league.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        print(f"\nSaved {len(archetypes)} archetypes to {output_file}")
        print(f"Total decks: {sum(len(a['decks']) for a in archetypes.values())}")

        print("\nArchetypes found:")
        for archetype_name in archetypes:
            deck_count = len(archetypes[archetype_name]["decks"])
            print(f"  {archetype_name}: {deck_count} decks")
    else:
        result = fetch_latest_modern_league()
        if result:
            print("\nArchetypes found:")
            for archetype_name in result["modern"]:
                if archetype_name != "timestamp":
                    deck_count = len(result["modern"][archetype_name]["decks"])
                    print(f"  {archetype_name}: {deck_count} decks")
        else:
            print("\nUsage: python fetch_mtgo_league.py [URL]")
            print(
                "Example: python fetch_mtgo_league.py https://www.mtgo.com/decklist/modern-league-2025-11-259979"
            )
