import json
import time

from repositories.metagame_repository import MetagameRepository


def _write_cache(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_get_archetypes_returns_stale_cache_when_fetch_fails(monkeypatch, tmp_path):
    cache_file = tmp_path / "archetype_list.json"
    monkeypatch.setattr(
        "repositories.metagame_repository.ARCHETYPE_LIST_CACHE_FILE",
        cache_file,
        raising=False,
    )
    repo = MetagameRepository(cache_ttl=1)
    stale_items = [{"name": "UR Murktide"}]
    _write_cache(
        cache_file,
        {"Modern": {"timestamp": time.time() - 3600, "items": stale_items}},
    )

    def fake_get_archetypes(_format):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "repositories.metagame_repository.get_archetypes",
        fake_get_archetypes,
    )

    assert repo.get_archetypes_for_format("Modern") == stale_items


def test_get_decks_returns_stale_cache_when_fetch_fails(monkeypatch, tmp_path):
    cache_file = tmp_path / "deck_cache.json"
    monkeypatch.setattr(
        "repositories.metagame_repository.DECK_CACHE_FILE",
        cache_file,
        raising=False,
    )
    repo = MetagameRepository(cache_ttl=1)
    archetype = {"url": "format/archetype", "name": "Test"}
    stale_items = [{"name": "Deck A", "player": "Alice"}]
    _write_cache(
        cache_file,
        {archetype["url"]: {"timestamp": time.time() - 3600, "items": stale_items}},
    )

    def fake_get_archetype_decks(_archetype):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "repositories.metagame_repository.get_archetype_decks",
        fake_get_archetype_decks,
    )

    assert repo.get_decks_for_archetype(archetype) == stale_items
