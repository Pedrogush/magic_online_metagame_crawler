from __future__ import annotations

import json
from pathlib import Path

from repositories.card_repository import CardRepository
from services.collection_service import CollectionService

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_collection_export.json"


def test_card_repository_reads_collection_export():
    repo = CardRepository()

    cards = repo.load_collection_from_file(FIXTURE_PATH)

    assert len(cards) == 4
    assert cards[0]["name"] == "Lightning Bolt"
    assert cards[-1]["name"] == "Spell Pierce"
    assert cards[-1]["quantity"] == 2


def test_card_repository_handles_snapshot_wrapper(tmp_path):
    repo = CardRepository()
    snapshot_path = tmp_path / "collection_snapshot.json"
    payload = {
        "collection": {
            "id": 42,
            "name": "Sample Export",
            "itemCount": 4,
            "maxItems": 7500,
            "items": json.loads(FIXTURE_PATH.read_text(encoding="utf-8")),
        }
    }
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    cards = repo.load_collection_from_file(snapshot_path)

    assert len(cards) == 4
    assert cards[1]["name"] == "Island"


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
