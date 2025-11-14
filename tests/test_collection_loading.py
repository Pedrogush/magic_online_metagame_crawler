from __future__ import annotations

import json
from pathlib import Path

from repositories.card_repository import CardRepository
from services.collection_service import CollectionService


class TrackingCollectionService(CollectionService):
    """Collection service that records deck parse invocations for testing."""

    def __init__(self, card_repository: CardRepository | None = None):
        super().__init__(card_repository=card_repository)
        self.parse_calls = 0

    def _parse_deck_text(self, deck_text: str) -> dict[str, int]:
        self.parse_calls += 1
        return super()._parse_deck_text(deck_text)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_collection_export.json"


def test_card_repository_reads_collection_export():
    repo = CardRepository()

    cards = repo.load_collection_from_file(FIXTURE_PATH)

    assert len(cards) == 4

    names = [card["name"] for card in cards]
    assert names == ["Lightning Bolt", "Island", "Lightning Bolt", "Spell Pierce"]
    assert cards[-1]["quantity"] == 2


def test_card_repository_handles_flat_list_format(tmp_path):
    repo = CardRepository()
    list_path = tmp_path / "collection_list.json"
    payload = [
        {"name": "Opt", "quantity": 3},
        {"name": "Consider", "quantity": "2"},
    ]
    list_path.write_text(json.dumps(payload), encoding="utf-8")

    cards = repo.load_collection_from_file(list_path)

    assert len(cards) == 2
    assert [card["name"] for card in cards] == ["Opt", "Consider"]
    assert cards[1]["quantity"] == 2


def test_collection_service_loads_inventory_from_export(tmp_path):
    repo = CardRepository()
    service = CollectionService(card_repository=repo)

    # Copy to a temp location to emulate a freshly downloaded export
    temp_file = tmp_path / "collection_full_trade_20240101.json"
    temp_file.write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    assert service.load_collection(temp_file)

    inventory = service.get_inventory()
    assert inventory["Lightning Bolt"] == 5  # 4 + 1 duplicate entry
    assert inventory["Island"] == 12
    assert inventory["Spell Pierce"] == 2


def test_analyze_deck_ownership_uses_cached_requirements():
    repo = CardRepository()
    service = TrackingCollectionService(card_repository=repo)
    service.set_inventory({"Lightning Bolt": 4, "Island": 12})

    deck_text = "4 Lightning Bolt\n\nSideboard\n1 Island"

    first = service.analyze_deck_ownership(deck_text)
    second = service.analyze_deck_ownership(deck_text)

    assert first == second
    assert service.parse_calls == 1

    updated_deck = deck_text + "\n1 Spell Pierce"
    service.analyze_deck_ownership(updated_deck)

    assert service.parse_calls == 2
