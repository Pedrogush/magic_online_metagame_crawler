"""Tests for card image alias handling and printing index generation."""

from __future__ import annotations

import json
from utils import card_images


def test_ensure_printing_index_cache_includes_face_aliases(tmp_path, monkeypatch):
    """Double-faced cards should expose each face as a lookup key."""
    cache_dir = tmp_path / "card_images"
    cache_dir.mkdir(parents=True, exist_ok=True)
    bulk_path = cache_dir / "bulk_data.json"
    printings_path = cache_dir / "printings.json"
    payload = [
        {
            "name": "Delver of Secrets // Insectile Aberration",
            "id": "uuid-delver",
            "set": "isd",
            "set_name": "Innistrad",
            "collector_number": "51",
            "released_at": "2011-09-30",
            "card_faces": [
                {"name": "Delver of Secrets"},
                {"name": "Insectile Aberration"},
            ],
        }
    ]
    bulk_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(card_images, "IMAGE_CACHE_DIR", cache_dir, raising=False)
    monkeypatch.setattr(card_images, "BULK_DATA_CACHE", bulk_path, raising=False)
    monkeypatch.setattr(card_images, "PRINTING_INDEX_CACHE", printings_path, raising=False)

    data = card_images.ensure_printing_index_cache(force=True)["data"]

    canonical_key = "delver of secrets // insectile aberration"
    assert canonical_key in data
    assert "delver of secrets" in data
    assert "insectile aberration" in data
    # Face aliases should reuse the same printings entries
    assert data["delver of secrets"] == data[canonical_key]
    assert data["insectile aberration"] == data[canonical_key]


def test_card_image_cache_resolves_double_faced_alias(tmp_path):
    """Image cache should find stored MDFC images via either face name."""
    cache_dir = tmp_path / "cache"
    db_path = cache_dir / "images.db"
    cache = card_images.CardImageCache(cache_dir=cache_dir, db_path=db_path)
    image_path = cache.cache_dir / "normal" / "uuid-delver.jpg"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"fake")

    cache.add_image(
        uuid="uuid-delver",
        name="Delver of Secrets // Insectile Aberration",
        set_code="ISD",
        collector_number="51",
        image_size="normal",
        file_path=image_path,
    )

    assert cache.get_image_path("Delver of Secrets") == image_path
    assert cache.get_image_path("Insectile Aberration") == image_path
    # Regression guard: canonical name still resolves
    assert (
        cache.get_image_path("Delver of Secrets // Insectile Aberration") == image_path
    )
