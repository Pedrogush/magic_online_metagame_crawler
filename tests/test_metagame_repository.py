import json

import pytest

from repositories.metagame_repository import MetagameRepository


@pytest.fixture
def deck_cache_file(tmp_path, monkeypatch):
    cache_file = tmp_path / "deck_cache.json"
    monkeypatch.setattr("repositories.metagame_repository.DECK_CACHE_FILE", cache_file)
    return cache_file


def test_get_decks_for_archetype_uses_slug_when_caching(monkeypatch, deck_cache_file):
    repo = MetagameRepository()
    captured = {}

    def fake_get_archetype_decks(slug: str):
        captured["slug"] = slug
        return [{"number": "123"}]

    monkeypatch.setattr(
        "repositories.metagame_repository.get_archetype_decks", fake_get_archetype_decks
    )

    decks = repo.get_decks_for_archetype(
        {"name": "Temur Rhinos", "href": "temur-rhinos"}, force_refresh=True
    )

    assert decks == [{"number": "123"}]
    assert captured["slug"] == "temur-rhinos"
    assert deck_cache_file.exists()

    cache_data = json.loads(deck_cache_file.read_text())
    assert "temur-rhinos" in cache_data


def test_get_decks_for_archetype_accepts_slug_strings(monkeypatch, deck_cache_file):
    repo = MetagameRepository()
    received = []

    def fake_get_archetype_decks(slug: str):
        received.append(slug)
        return []

    monkeypatch.setattr(
        "repositories.metagame_repository.get_archetype_decks", fake_get_archetype_decks
    )

    repo.get_decks_for_archetype("rakdos-midrange", force_refresh=True)

    assert received == ["rakdos-midrange"]
    assert deck_cache_file.exists()
