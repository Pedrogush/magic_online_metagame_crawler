"""Download and parse a single MTGO Modern Challenge page."""

import json
from datetime import datetime
from pathlib import Path

from navigators.mtgo_decklists import fetch_deck_event, fetch_decklist_index
from utils.archetype_classifier import ArchetypeClassifier
from utils.constants import ARCHETYPE_CACHE_FILE
from utils.deck_text_cache import get_deck_cache


def parse_mtgo_deck(raw_deck: dict) -> dict:
    """
    Parse raw MTGO deck into clean simplified format.

    Strips all unnecessary fields and flattens card_attributes.
    Returns dict with clean structure: deck_id, mainboard, sideboard, player
    """
    deck_id = raw_deck.get("loginplayeventcourseid") or raw_deck.get("decktournamentid")
    player = raw_deck.get("player") or raw_deck.get("pilot") or "Unknown"

    mainboard = []
    for card in raw_deck.get("main_deck", []):
        if card.get("sideboard") == "false":
            card_name = card.get("card_attributes", {}).get("card_name", "")
            if card_name:
                mainboard.append({
                    "card_name": card_name,
                    "qty": int(card.get("qty", "1")),
                    "sideboard": "false"
                })

    sideboard = []
    for card in raw_deck.get("sideboard_deck", []):
        card_name = card.get("card_attributes", {}).get("card_name", "")
        if card_name:
            sideboard.append({
                "card_name": card_name,
                "qty": int(card.get("qty", "1")),
                "sideboard": "true"
            })

    return {
        "deck_id": deck_id,
        "player": player,
        "mainboard": mainboard,
        "sideboard": sideboard
    }


def convert_deck_to_classifier_format(clean_deck: dict) -> dict:
    """Convert clean deck format to ArchetypeClassifier format."""
    mainboard = [
        {"name": card["card_name"], "count": card["qty"]}
        for card in clean_deck["mainboard"]
    ]
    sideboard = [
        {"name": card["card_name"], "count": card["qty"]}
        for card in clean_deck["sideboard"]
    ]

    return {
        "mainboard": mainboard,
        "sideboard": sideboard,
        "format": "modern"
    }


def deck_to_text(clean_deck: dict) -> str:
    """Convert clean deck format to text format matching MTGGoldfish."""
    lines = []

    for card in clean_deck["mainboard"]:
        lines.append(f"{card['qty']} {card['card_name']}")

    lines.append("sideboard")

    for card in clean_deck["sideboard"]:
        lines.append(f"{card['qty']} {card['card_name']}")

    return "\n".join(lines) + "\n"


def parse_mtgo_challenge_to_archetype_format(url: str) -> dict:
    """
    Parse an MTGO challenge page and return data in mtggoldfish archetype format.

    Returns a dictionary with archetypes as keys, each containing a list of decks.
    """
    payload = fetch_deck_event(url)

    classifier = ArchetypeClassifier()
    archetypes = {}
    event_date = payload.get("publish_date", datetime.now().isoformat()[:10])
    deck_cache = get_deck_cache()

    event_name = payload.get("name", "Modern Challenge")

    clean_decks = [parse_mtgo_deck(raw_deck) for raw_deck in payload.get("decklists", [])]
    classifier_decks = [convert_deck_to_classifier_format(deck) for deck in clean_decks]

    classifier.assign_archetypes(classifier_decks, "modern")

    for idx, (clean_deck, classifier_deck) in enumerate(zip(clean_decks, classifier_decks), 1):
        archetype_name = classifier_deck.get("archetype", "Unknown")
        player = clean_deck["player"]
        deck_id = clean_deck["deck_id"] or str(hash(player + event_date + str(idx)))

        deck_text = deck_to_text(clean_deck)
        deck_cache.set(deck_id, deck_text)

        if archetype_name not in archetypes:
            archetypes[archetype_name] = {"decks": [], "results": {event_date: 0}}

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
