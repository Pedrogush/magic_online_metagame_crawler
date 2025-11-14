"""Tests for MetagameRepository data access layer."""

import json
import time

import pytest

from repositories.metagame_repository import MetagameRepository


@pytest.fixture
def metagame_repo():
    """MetagameRepository instance for testing."""
    return MetagameRepository(cache_ttl=3600)


@pytest.fixture
def archetype_cache_file(tmp_path, monkeypatch):
    """Create a temporary archetype cache file."""
    from utils import paths

    cache_file = tmp_path / "archetype_cache.json"
    monkeypatch.setattr(paths, "ARCHETYPE_LIST_CACHE_FILE", cache_file)
    return cache_file


@pytest.fixture
def deck_cache_file(tmp_path, monkeypatch):
    """Create a temporary deck cache file."""
    from utils import paths

    cache_file = tmp_path / "deck_cache.json"
    monkeypatch.setattr(paths, "DECK_CACHE_FILE", cache_file)
    return cache_file


# ============= Cache Loading Tests =============


def test_load_cached_archetypes_no_file(metagame_repo):
    """Test loading archetypes when cache file doesn't exist."""
    result = metagame_repo._load_cached_archetypes("Modern")
    assert result is None


def test_load_cached_archetypes_success(metagame_repo, archetype_cache_file):
    """Test loading archetypes from cache successfully."""
    cache_data = {
        "Modern": {
            "timestamp": time.time(),
            "items": [
                {"name": "Archetype 1", "url": "url1"},
                {"name": "Archetype 2", "url": "url2"},
            ],
        }
    }
    archetype_cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

    result = metagame_repo._load_cached_archetypes("Modern")

    assert result is not None
    assert len(result) == 2
    assert result[0]["name"] == "Archetype 1"


def test_load_cached_archetypes_expired(metagame_repo, archetype_cache_file):
    """Test loading expired archetypes returns None."""
    cache_data = {
        "Modern": {
            "timestamp": time.time() - 7200,  # 2 hours ago
            "items": [{"name": "Archetype 1"}],
        }
    }
    archetype_cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

    result = metagame_repo._load_cached_archetypes("Modern", max_age=3600)

    assert result is None


def test_load_cached_archetypes_ignore_age(metagame_repo, archetype_cache_file):
    """Test loading expired archetypes with max_age=None."""
    cache_data = {
        "Modern": {
            "timestamp": time.time() - 7200,  # 2 hours ago
            "items": [{"name": "Archetype 1"}],
        }
    }
    archetype_cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

    result = metagame_repo._load_cached_archetypes("Modern", max_age=None)

    assert result is not None
    assert len(result) == 1


def test_load_cached_archetypes_invalid_json(metagame_repo, archetype_cache_file):
    """Test loading archetypes with invalid JSON."""
    archetype_cache_file.write_text("invalid json", encoding="utf-8")

    result = metagame_repo._load_cached_archetypes("Modern")

    assert result is None


def test_load_cached_archetypes_missing_format(metagame_repo, archetype_cache_file):
    """Test loading archetypes for format not in cache."""
    cache_data = {
        "Modern": {
            "timestamp": time.time(),
            "items": [{"name": "Archetype 1"}],
        }
    }
    archetype_cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

    result = metagame_repo._load_cached_archetypes("Standard")

    assert result is None


# ============= Cache Saving Tests =============


def test_save_cached_archetypes_new_file(metagame_repo, archetype_cache_file):
    """Test saving archetypes to new cache file."""
    archetypes = [
        {"name": "Archetype 1", "url": "url1"},
        {"name": "Archetype 2", "url": "url2"},
    ]

    metagame_repo._save_cached_archetypes("Modern", archetypes)

    assert archetype_cache_file.exists()
    with archetype_cache_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert "Modern" in data
    assert len(data["Modern"]["items"]) == 2


def test_save_cached_archetypes_existing_file(metagame_repo, archetype_cache_file):
    """Test saving archetypes to existing cache file."""
    # Create existing cache
    existing_data = {
        "Standard": {
            "timestamp": time.time(),
            "items": [{"name": "Standard Archetype"}],
        }
    }
    archetype_cache_file.write_text(json.dumps(existing_data), encoding="utf-8")

    # Save new format
    archetypes = [{"name": "Modern Archetype"}]
    metagame_repo._save_cached_archetypes("Modern", archetypes)

    # Both formats should exist
    with archetype_cache_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert "Standard" in data
    assert "Modern" in data


def test_save_cached_archetypes_update_existing_format(metagame_repo, archetype_cache_file):
    """Test updating archetypes for existing format."""
    # Create existing cache
    existing_data = {
        "Modern": {
            "timestamp": time.time() - 3600,
            "items": [{"name": "Old Archetype"}],
        }
    }
    archetype_cache_file.write_text(json.dumps(existing_data), encoding="utf-8")

    # Update same format
    archetypes = [{"name": "New Archetype"}]
    metagame_repo._save_cached_archetypes("Modern", archetypes)

    # Should have new data
    with archetype_cache_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["Modern"]["items"]) == 1
    assert data["Modern"]["items"][0]["name"] == "New Archetype"


# ============= Deck Cache Tests =============


def test_load_cached_decks_success(metagame_repo, deck_cache_file):
    """Test loading decks from cache successfully."""
    cache_data = {
        "archetype_url": {
            "timestamp": time.time(),
            "items": [
                {"name": "Deck 1", "url": "deck1"},
                {"name": "Deck 2", "url": "deck2"},
            ],
        }
    }
    deck_cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

    result = metagame_repo._load_cached_decks("archetype_url")

    assert result is not None
    assert len(result) == 2


def test_load_cached_decks_expired(metagame_repo, deck_cache_file):
    """Test loading expired decks returns None."""
    cache_data = {
        "archetype_url": {
            "timestamp": time.time() - 7200,  # 2 hours ago
            "items": [{"name": "Deck 1"}],
        }
    }
    deck_cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

    result = metagame_repo._load_cached_decks("archetype_url", max_age=3600)

    assert result is None


def test_save_cached_decks_new_file(metagame_repo, deck_cache_file):
    """Test saving decks to new cache file."""
    decks = [
        {"name": "Deck 1", "url": "deck1"},
        {"name": "Deck 2", "url": "deck2"},
    ]

    metagame_repo._save_cached_decks("archetype_url", decks)

    assert deck_cache_file.exists()
    with deck_cache_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert "archetype_url" in data
    assert len(data["archetype_url"]["items"]) == 2


# ============= Clear Cache Tests =============


def test_clear_cache(metagame_repo, archetype_cache_file, deck_cache_file):
    """Test clearing all caches."""
    # Create cache files
    archetype_cache_file.write_text("{}", encoding="utf-8")
    deck_cache_file.write_text("{}", encoding="utf-8")

    metagame_repo.clear_cache()

    assert not archetype_cache_file.exists()
    assert not deck_cache_file.exists()


def test_clear_cache_nonexistent_files(metagame_repo):
    """Test clearing cache when files don't exist."""
    # Should not raise exception
    metagame_repo.clear_cache()


# ============= Repository Initialization Tests =============


def test_repository_initialization():
    """Test repository initializes with default TTL."""
    repo = MetagameRepository()
    assert repo.cache_ttl == 3600


def test_repository_custom_ttl():
    """Test repository with custom TTL."""
    repo = MetagameRepository(cache_ttl=7200)
    assert repo.cache_ttl == 7200
