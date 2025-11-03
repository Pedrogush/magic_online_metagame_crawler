from typing import Iterable

from utils import mtgo_bridge


def dump_decks(decks_payload: Iterable[dict]) -> None:
    for block in decks_payload:
        format_name = block.get("format", "Unknown")
        decks = block.get("decks", [])
        print(f"{format_name} ({len(decks)} decks)")
        for deck in decks:
            print(
                f"  '{deck.get('name')}' (ID: {deck.get('id')}) "
                f"– {deck.get('main')} main / {deck.get('side')} side "
                f"(last updated {deck.get('timestamp')})"
            )
        print()


def dump_collection(collection_payload: Iterable[dict], limit_cards: int = 10) -> None:
    for binder in collection_payload:
        cards = binder.get("cards", [])
        print(f"Binder: {binder.get('name')}  ({len(cards)} entries)")
        for card in cards[:limit_cards]:
            print(f"  {card.get('quantity')}x {card.get('name')} ({card.get('set')})")
        remaining = len(cards) - limit_cards
        if remaining > 0:
            print(f"  ...and {remaining} more")
        print()
        break


def main() -> None:
    print("Decks grouped by format:")
    decks = mtgo_bridge.list_decks()
    dump_decks(decks)

    print()
    print("Collection snapshot:")
    collection = mtgo_bridge.get_collection_snapshot()
    dump_collection(collection)


if __name__ == "__main__":
    main()
