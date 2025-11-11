"""Tests for CollectionService."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from services.collection_service import CollectionService


@pytest.fixture
def collection_service(tmp_path):
    """Create a CollectionService instance with temporary directory."""
    return CollectionService(tmp_path)


@pytest.fixture
def sample_cards():
    """Sample card collection for testing."""
    return [
        {"name": "Lightning Bolt", "quantity": 10},
        {"name": "Mountain", "quantity": 50},
        {"name": "Lava Spike", "quantity": 4},
    ]


class TestCollectionServiceInitialization:
    """Test CollectionService initialization."""

    def test_initialization_creates_directory(self, tmp_path):
        """Test that service creates cache directory on init."""
        cache_dir = tmp_path / "cache"
        assert not cache_dir.exists()

        service = CollectionService(cache_dir)

        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_initialization_sets_cache_file_path(self, tmp_path):
        """Test that cache file path is set correctly."""
        service = CollectionService(tmp_path)

        expected_path = tmp_path / "collection.json"
        assert service.collection_cache_file == expected_path

    def test_initialization_empty_inventory(self, tmp_path):
        """Test that inventory starts empty."""
        service = CollectionService(tmp_path)

        assert service.inventory == {}


class TestLoadFromCache:
    """Test loading collection from cache."""

    def test_load_from_cache_success(self, collection_service, sample_cards):
        """Test successful loading from cache."""
        # Create cache file
        cache_data = {"cards": sample_cards}
        collection_service.collection_cache_file.write_text(
            json.dumps(cache_data), encoding="utf-8"
        )

        result = collection_service.load_from_cache()

        assert result is True
        assert collection_service.inventory["Lightning Bolt"] == 10
        assert collection_service.inventory["Mountain"] == 50
        assert collection_service.inventory["Lava Spike"] == 4

    def test_load_from_cache_no_file(self, collection_service):
        """Test loading when cache file doesn't exist."""
        result = collection_service.load_from_cache()

        assert result is False
        assert collection_service.inventory == {}

    def test_load_from_cache_invalid_json(self, collection_service):
        """Test loading with invalid JSON file."""
        collection_service.collection_cache_file.write_text(
            "invalid json", encoding="utf-8"
        )

        result = collection_service.load_from_cache()

        assert result is False

    def test_load_from_cache_aggregates_duplicates(self, collection_service):
        """Test that duplicate card names are aggregated."""
        cache_data = {
            "cards": [
                {"name": "Lightning Bolt", "quantity": 5},
                {"name": "Lightning Bolt", "quantity": 3},
                {"name": "Mountain", "quantity": 20},
            ]
        }
        collection_service.collection_cache_file.write_text(
            json.dumps(cache_data), encoding="utf-8"
        )

        collection_service.load_from_cache()

        assert collection_service.inventory["Lightning Bolt"] == 8

    def test_load_from_cache_missing_cards_key(self, collection_service):
        """Test loading with missing 'cards' key."""
        cache_data = {"not_cards": []}
        collection_service.collection_cache_file.write_text(
            json.dumps(cache_data), encoding="utf-8"
        )

        result = collection_service.load_from_cache()

        # Should still succeed with empty inventory
        assert result is True
        assert collection_service.inventory == {}


class TestSaveToCache:
    """Test saving collection to cache."""

    def test_save_to_cache_success(self, collection_service, sample_cards):
        """Test successful save to cache."""
        filepath = collection_service.save_to_cache(sample_cards)

        assert filepath.exists()
        assert filepath == collection_service.collection_cache_file

        # Verify content
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["cards"] == sample_cards

    def test_save_to_cache_creates_parent_dirs(self, tmp_path):
        """Test that save creates parent directories if needed."""
        cache_dir = tmp_path / "nested" / "cache"
        service = CollectionService(cache_dir)

        cards = [{"name": "Test", "quantity": 1}]
        filepath = service.save_to_cache(cards)

        assert filepath.exists()
        assert filepath.parent.exists()

    def test_save_to_cache_overwrites_existing(
        self, collection_service, sample_cards
    ):
        """Test that save overwrites existing cache."""
        # Save first version
        collection_service.save_to_cache(sample_cards)

        # Save different version
        new_cards = [{"name": "Different Card", "quantity": 1}]
        collection_service.save_to_cache(new_cards)

        # Verify new data
        with collection_service.collection_cache_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["cards"]) == 1
        assert data["cards"][0]["name"] == "Different Card"


class TestFetchFromBridge:
    """Test fetching collection from MTGO bridge."""

    @patch("services.collection_service.subprocess.run")
    def test_fetch_from_bridge_success(self, mock_run, collection_service, sample_cards, tmp_path):
        """Test successful fetch from bridge."""
        bridge_path = tmp_path / "bridge.exe"
        bridge_path.touch()

        # Mock subprocess result
        mock_result = Mock()
        mock_result.stdout = json.dumps({"collection": sample_cards})
        mock_run.return_value = mock_result

        result = collection_service.fetch_from_bridge(bridge_path)

        assert result == sample_cards
        mock_run.assert_called_once()
        # Verify command arguments
        args = mock_run.call_args[0][0]
        assert str(bridge_path) in args
        assert "collection" in args

    @patch("services.collection_service.subprocess.run")
    def test_fetch_from_bridge_timeout(self, mock_run, collection_service, tmp_path):
        """Test fetch with custom timeout."""
        bridge_path = tmp_path / "bridge.exe"
        bridge_path.touch()

        mock_result = Mock()
        mock_result.stdout = json.dumps({"collection": []})
        mock_run.return_value = mock_result

        collection_service.fetch_from_bridge(bridge_path, timeout=60)

        # Verify timeout parameter
        assert mock_run.call_args[1]["timeout"] == 60

    @patch("services.collection_service.subprocess.run")
    def test_fetch_from_bridge_timeout_error(self, mock_run, collection_service, tmp_path):
        """Test fetch raises on timeout."""
        bridge_path = tmp_path / "bridge.exe"
        bridge_path.touch()

        mock_run.side_effect = subprocess.TimeoutExpired("bridge.exe", 120)

        with pytest.raises(subprocess.TimeoutExpired):
            collection_service.fetch_from_bridge(bridge_path)

    @patch("services.collection_service.subprocess.run")
    def test_fetch_from_bridge_invalid_json(self, mock_run, collection_service, tmp_path):
        """Test fetch with invalid JSON response."""
        bridge_path = tmp_path / "bridge.exe"
        bridge_path.touch()

        mock_result = Mock()
        mock_result.stdout = "invalid json"
        mock_run.return_value = mock_result

        with pytest.raises(json.JSONDecodeError):
            collection_service.fetch_from_bridge(bridge_path)

    @patch("services.collection_service.subprocess.run")
    def test_fetch_from_bridge_missing_collection_key(
        self, mock_run, collection_service, tmp_path
    ):
        """Test fetch with missing 'collection' key in response."""
        bridge_path = tmp_path / "bridge.exe"
        bridge_path.touch()

        mock_result = Mock()
        mock_result.stdout = json.dumps({"not_collection": []})
        mock_run.return_value = mock_result

        result = collection_service.fetch_from_bridge(bridge_path)

        # Should return empty list if key missing
        assert result == []


class TestBuildInventory:
    """Test inventory building functionality."""

    def test_build_inventory_basic(self, collection_service, sample_cards):
        """Test building inventory from card list."""
        inventory = collection_service.build_inventory(sample_cards)

        assert inventory["Lightning Bolt"] == 10
        assert inventory["Mountain"] == 50
        assert inventory["Lava Spike"] == 4
        assert collection_service.inventory == inventory

    def test_build_inventory_empty(self, collection_service):
        """Test building inventory from empty list."""
        inventory = collection_service.build_inventory([])

        assert inventory == {}

    def test_build_inventory_aggregates_duplicates(self, collection_service):
        """Test that duplicates are aggregated."""
        cards = [
            {"name": "Lightning Bolt", "quantity": 5},
            {"name": "Lightning Bolt", "quantity": 3},
        ]

        inventory = collection_service.build_inventory(cards)

        assert inventory["Lightning Bolt"] == 8

    def test_build_inventory_ignores_missing_name(self, collection_service):
        """Test that cards without names are ignored."""
        cards = [
            {"name": "Lightning Bolt", "quantity": 5},
            {"quantity": 10},  # Missing name
            {"name": "Mountain", "quantity": 20},
        ]

        inventory = collection_service.build_inventory(cards)

        assert len(inventory) == 2
        assert "Lightning Bolt" in inventory
        assert "Mountain" in inventory

    def test_build_inventory_handles_zero_quantity(self, collection_service):
        """Test handling of zero quantity cards."""
        cards = [
            {"name": "Lightning Bolt", "quantity": 0},
            {"name": "Mountain", "quantity": 20},
        ]

        inventory = collection_service.build_inventory(cards)

        # Zero quantity cards should still be included
        assert inventory["Lightning Bolt"] == 0
        assert inventory["Mountain"] == 20


class TestGetOwnedQuantity:
    """Test getting owned quantity for cards."""

    def test_get_owned_quantity_exists(self, collection_service, sample_cards):
        """Test getting quantity for owned card."""
        collection_service.build_inventory(sample_cards)

        qty = collection_service.get_owned_quantity("Lightning Bolt")

        assert qty == 10

    def test_get_owned_quantity_not_owned(self, collection_service, sample_cards):
        """Test getting quantity for unowned card."""
        collection_service.build_inventory(sample_cards)

        qty = collection_service.get_owned_quantity("Black Lotus")

        assert qty == 0

    def test_get_owned_quantity_empty_inventory(self, collection_service):
        """Test getting quantity with empty inventory."""
        qty = collection_service.get_owned_quantity("Lightning Bolt")

        assert qty == 0


class TestGetOwnedStatus:
    """Test getting ownership status."""

    def test_get_owned_status_not_owned(self, collection_service):
        """Test status for unowned card."""
        status, color = collection_service.get_owned_status("Lightning Bolt", 4)

        assert status == "Not owned"
        assert color == "red"

    def test_get_owned_status_partial(self, collection_service, sample_cards):
        """Test status for partially owned card."""
        collection_service.build_inventory(sample_cards)

        status, color = collection_service.get_owned_status("Lava Spike", 10)

        assert "Own 4/10" in status
        assert color == "orange"

    def test_get_owned_status_complete(self, collection_service, sample_cards):
        """Test status for fully owned card."""
        collection_service.build_inventory(sample_cards)

        status, color = collection_service.get_owned_status("Lightning Bolt", 4)

        assert "Own 10" in status
        assert color == "green"

    def test_get_owned_status_exact_match(self, collection_service, sample_cards):
        """Test status when owned equals required."""
        collection_service.build_inventory(sample_cards)

        status, color = collection_service.get_owned_status("Lava Spike", 4)

        assert "Own 4" in status
        assert color == "green"


class TestClear:
    """Test inventory clearing."""

    def test_clear_inventory(self, collection_service, sample_cards):
        """Test that clear empties inventory."""
        collection_service.build_inventory(sample_cards)
        assert len(collection_service.inventory) > 0

        collection_service.clear()

        assert collection_service.inventory == {}
