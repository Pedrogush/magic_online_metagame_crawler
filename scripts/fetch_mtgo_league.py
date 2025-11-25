"""Download and parse a single MTGO Modern League page."""

import json
from datetime import datetime
from pathlib import Path

from navigators.mtgo_decklists import fetch_deck_event, fetch_decklist_index


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
    elif "Urza's Saga" in card_name_set and "�ormite" in card_name_set:
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


def parse_mtgo_league_to_archetype_format(url: str) -> dict:
    """
    Parse an MTGO league page and return data in mtggoldfish archetype format.

    Returns a dictionary with archetypes as keys, each containing a list of decks.
    """
    payload = fetch_deck_event(url)

    archetypes = {}
    event_date = payload.get("eventDate", datetime.utcnow().isoformat()[:10])

    for deck in payload.get("decklists", []):
        archetype_name = infer_archetype_from_deck(deck)
        player = deck.get("player") or deck.get("pilot") or "Unknown"
        standing = deck.get("standing") or deck.get("finish") or ""
        record = deck.get("record") or deck.get("winLoss") or ""
        deck_id = deck.get("mtgoId") or deck.get("identifier") or ""

        if archetype_name not in archetypes:
            archetypes[archetype_name] = {"decks": [], "results": {event_date: 0}}

        deck_entry = {
            "date": event_date,
            "number": str(deck_id),
            "player": player,
            "event": "Modern League",
            "result": f"{standing} {record}".strip(),
            "name": archetype_name,
        }

        archetypes[archetype_name]["decks"].append(deck_entry)
        archetypes[archetype_name]["results"][event_date] += 1

    return archetypes


def fetch_latest_modern_league():
    """Fetch the latest Modern League from MTGO."""
    now = datetime.now()
    entries = fetch_decklist_index(now.year, now.month, force_refresh=True)

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

    output = {"modern": {"timestamp": datetime.now().timestamp(), **archetypes}}

    output_file = Path("cache") / "mtgo_modern_league.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {len(archetypes)} archetypes to {output_file}")
    print(f"Total decks: {sum(len(a['decks']) for a in archetypes.values())}")
    return output


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
