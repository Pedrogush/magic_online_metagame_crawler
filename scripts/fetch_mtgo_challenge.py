"""Download and parse a single MTGO Modern Challenge page."""

import json
from datetime import datetime
from pathlib import Path

from navigators.mtgo_decklists import fetch_deck_event, fetch_decklist_index
from utils.constants import ARCHETYPE_CACHE_FILE
from utils.deck_text_cache import get_deck_cache


def infer_archetype_from_deck(deck: dict) -> str:
    """
    Infer archetype name from deck contents by identifying key cards.
    """
    main_deck = deck.get("main_deck", [])

    card_names = [card.get("card_attributes", {}).get("card_name", "") for card in main_deck]
    card_name_set = set(card_names)

    # Check for key archetype-defining cards
    if "Ugin's Labyrinth" in card_name_set and "Eldrazi Temple" in card_name_set:
        return "Eldrazi Tron"
    elif "Goryo's Vengeance" in card_name_set:
        return "Goryo's Vengeance"
    elif "Living End" in card_name_set:
        return "Living End"
    elif "Urza's Saga" in card_name_set and "Ornithopter" in card_name_set:
        return "Hammer Time"
    elif "Primeval Titan" in card_name_set:
        return "Amulet Titan"
    elif "Yawgmoth, Thran Physician" in card_name_set:
        return "Yawgmoth"
    elif "Murktide Regent" in card_name_set:
        return "Izzet Murktide"
    elif "Omnath, Locus of Creation" in card_name_set:
        return "4C Omnath"
    elif "Creativity" in card_name_set:
        return "Creativity"
    elif "Scam" in card_name_set or "Grief" in card_name_set:
        return "Rakdos Scam"
    elif "The One Ring" in card_name_set and "Phlage" in card_name_set:
        return "Jeskai Control"
    elif "Tarmogoyf" in card_name_set and "Wrenn and Six" in card_name_set:
        return "Jund"

    # Fallback: use most common non-basic card name
    if card_names:
        from collections import Counter

        non_basic_cards = [
            name
            for name in card_names
            if "Plains" not in name
            and "Island" not in name
            and "Swamp" not in name
            and "Mountain" not in name
            and "Forest" not in name
        ]
        if non_basic_cards:
            most_common = Counter(non_basic_cards).most_common(1)[0][0]
            return most_common

    return "Unknown"


def deck_to_text(deck: dict) -> str:
    """Convert MTGO deck data to text format matching MTGGoldfish."""
    lines = []

    # Main deck
    main_deck = deck.get("main_deck", [])
    for card in main_deck:
        if card.get("sideboard") == "false":
            qty = card.get("qty", "1")
            name = card.get("card_attributes", {}).get("card_name", "Unknown")
            lines.append(f"{qty} {name}")

    # Sideboard
    lines.append("sideboard")
    sideboard = deck.get("sideboard_deck", [])
    for card in sideboard:
        qty = card.get("qty", "1")
        name = card.get("card_attributes", {}).get("card_name", "Unknown")
        lines.append(f"{qty} {name}")

    return "\n".join(lines) + "\n"


def parse_mtgo_challenge_to_archetype_format(url: str) -> dict:
    """
    Parse an MTGO challenge page and return data in mtggoldfish archetype format.

    Returns a dictionary with archetypes as keys, each containing a list of decks.
    """
    payload = fetch_deck_event(url)

    archetypes = {}
    event_date = payload.get("publish_date", datetime.now().isoformat()[:10])
    deck_cache = get_deck_cache()

    # Get event name for result field
    event_name = payload.get("name", "Modern Challenge")

    for idx, deck in enumerate(payload.get("decklists", []), 1):
        archetype_name = infer_archetype_from_deck(deck)
        player = deck.get("player") or deck.get("pilot") or "Unknown"
        deck_id = deck.get("loginplayeventcourseid") or str(hash(player + event_date + str(idx)))

        # Store deck text in cache
        deck_text = deck_to_text(deck)
        deck_cache.set(deck_id, deck_text)

        if archetype_name not in archetypes:
            archetypes[archetype_name] = {"decks": [], "results": {event_date: 0}}

        # Use placement (1st, 2nd, 3rd, etc.) for challenges
        deck_entry = {
            "date": event_date,
            "number": str(deck_id),
            "player": player,
            "event": event_name,
            "result": f"{idx}{'st' if idx == 1 else 'nd' if idx == 2 else 'rd' if idx == 3 else 'th'}",
            "name": archetype_name,
        }

        archetypes[archetype_name]["decks"].append(deck_entry)
        archetypes[archetype_name]["results"][event_date] += 1

    return archetypes


def fetch_latest_modern_challenge():
    """Fetch the latest Modern Challenge from MTGO."""
    now = datetime.now()
    entries = fetch_decklist_index(now.year, now.month)

    modern_challenges = [
        e
        for e in entries
        if e.get("format")
        and "modern" in e["format"].lower()
        and e.get("event_type") == "challenge"
    ]

    if not modern_challenges:
        print("No Modern Challenge found in current month")
        return None

    entry = modern_challenges[0]
    print(f"Found Modern Challenge: {entry['title']}")
    print(f"URL: {entry['url']}")
    print(f"Date: {entry['publish_date']}")

    archetypes = parse_mtgo_challenge_to_archetype_format(entry["url"])

    # Load existing archetype cache or create new
    if ARCHETYPE_CACHE_FILE.exists():
        with ARCHETYPE_CACHE_FILE.open("r", encoding="utf-8") as f:
            cache_data = json.load(f)
    else:
        cache_data = {}

    # Update/create modern section
    if "modern" not in cache_data:
        cache_data["modern"] = {"timestamp": datetime.now().timestamp()}
    else:
        cache_data["modern"]["timestamp"] = datetime.now().timestamp()

    # Merge archetypes
    for archetype_name, archetype_data in archetypes.items():
        if archetype_name not in cache_data["modern"]:
            cache_data["modern"][archetype_name] = archetype_data
        else:
            # Merge decks
            existing_deck_nums = {
                d["number"] for d in cache_data["modern"][archetype_name]["decks"]
            }
            new_decks = [
                d for d in archetype_data["decks"] if d["number"] not in existing_deck_nums
            ]
            cache_data["modern"][archetype_name]["decks"].extend(new_decks)

            # Merge results
            for date, count in archetype_data["results"].items():
                if date not in cache_data["modern"][archetype_name]["results"]:
                    cache_data["modern"][archetype_name]["results"][date] = count

    # Save to archetype cache
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
        print(f"Fetching Modern Challenge from URL: {url}")
        archetypes = parse_mtgo_challenge_to_archetype_format(url)

        output = {"modern": {"timestamp": datetime.now().timestamp(), **archetypes}}

        output_file = Path("cache") / "mtgo_modern_challenge.json"
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
        result = fetch_latest_modern_challenge()
        if result:
            print("\nArchetypes found:")
            for archetype_name in result["modern"]:
                if archetype_name != "timestamp":
                    deck_count = len(result["modern"][archetype_name]["decks"])
                    print(f"  {archetype_name}: {deck_count} decks")
        else:
            print("\nUsage: python fetch_mtgo_challenge.py [URL]")
            print(
                "Example: python fetch_mtgo_challenge.py https://www.mtgo.com/decklist/modern-challenge-32-2025-11-2312824804"
            )
