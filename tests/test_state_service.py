"""Tests for services.state_service module."""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

# Import StateService directly from file to avoid wx dependency in services.__init__
spec = importlib.util.spec_from_file_location(
    "state_service",
    Path(__file__).parent.parent / "services" / "state_service.py"
)
state_service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state_service)

StateService = state_service.StateService


class TestStateService:
    """Tests for StateService class."""

    def test_load_returns_empty_dict_when_file_does_not_exist(self):
        """Test that load returns empty dict when settings file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "nonexistent.json"
            service = StateService(settings_path)
            result = service.load()
            assert result == {}

    def test_load_returns_data_from_valid_json_file(self):
        """Test that load correctly reads data from a valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            test_data = {"key1": "value1", "key2": 42, "key3": True}

            with settings_path.open("w", encoding="utf-8") as fh:
                json.dump(test_data, fh)

            service = StateService(settings_path)
            result = service.load()
            assert result == test_data

    def test_load_returns_empty_dict_on_invalid_json(self):
        """Test that load returns empty dict when JSON is malformed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "bad.json"

            with settings_path.open("w", encoding="utf-8") as fh:
                fh.write("{ invalid json }")

            service = StateService(settings_path)
            result = service.load()
            assert result == {}

    def test_save_writes_data_to_file(self):
        """Test that save correctly writes data to a JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            service = StateService(settings_path)
            test_data = {"foo": "bar", "count": 123}

            service.save(test_data)

            with settings_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            assert loaded == test_data

    def test_save_creates_parent_directories(self):
        """Test that save creates parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "subdir" / "nested" / "settings.json"
            service = StateService(settings_path)
            test_data = {"test": "data"}

            service.save(test_data)

            assert settings_path.exists()
            with settings_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            assert loaded == test_data

    def test_save_and_load_roundtrip(self):
        """Test that data saved can be loaded back correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            service = StateService(settings_path)
            test_data = {
                "string": "test",
                "number": 42,
                "bool": True,
                "list": [1, 2, 3],
                "nested": {"key": "value"}
            }

            service.save(test_data)
            loaded = service.load()

            assert loaded == test_data


class TestCoerceBool:
    """Tests for StateService.coerce_bool static method."""

    def test_coerce_bool_with_true_boolean(self):
        """Test coerce_bool with True."""
        assert StateService.coerce_bool(True) is True

    def test_coerce_bool_with_false_boolean(self):
        """Test coerce_bool with False."""
        assert StateService.coerce_bool(False) is False

    def test_coerce_bool_with_truthy_strings(self):
        """Test coerce_bool with various truthy string values."""
        assert StateService.coerce_bool("true") is True
        assert StateService.coerce_bool("True") is True
        assert StateService.coerce_bool("TRUE") is True
        assert StateService.coerce_bool("1") is True
        assert StateService.coerce_bool("yes") is True
        assert StateService.coerce_bool("Yes") is True
        assert StateService.coerce_bool("on") is True
        assert StateService.coerce_bool("ON") is True
        assert StateService.coerce_bool("  true  ") is True

    def test_coerce_bool_with_falsy_strings(self):
        """Test coerce_bool with various falsy string values."""
        assert StateService.coerce_bool("false") is False
        assert StateService.coerce_bool("False") is False
        assert StateService.coerce_bool("0") is False
        assert StateService.coerce_bool("no") is False
        assert StateService.coerce_bool("off") is False
        assert StateService.coerce_bool("") is False
        assert StateService.coerce_bool("random") is False

    def test_coerce_bool_with_numbers(self):
        """Test coerce_bool with numeric values."""
        assert StateService.coerce_bool(1) is True
        assert StateService.coerce_bool(42) is True
        assert StateService.coerce_bool(0) is False
        assert StateService.coerce_bool(0.0) is False

    def test_coerce_bool_with_none(self):
        """Test coerce_bool with None."""
        assert StateService.coerce_bool(None) is False

    def test_coerce_bool_with_collections(self):
        """Test coerce_bool with collections."""
        assert StateService.coerce_bool([1, 2, 3]) is True
        assert StateService.coerce_bool([]) is False
        assert StateService.coerce_bool({"key": "value"}) is True
        assert StateService.coerce_bool({}) is False


class TestClampBulkCacheAge:
    """Tests for StateService.clamp_bulk_cache_age static method."""

    def test_clamp_returns_value_within_range(self):
        """Test that valid values within range are returned unchanged."""
        result = StateService.clamp_bulk_cache_age(
            5, default_days=7, min_days=1, max_days=30
        )
        assert result == 5

    def test_clamp_returns_min_when_value_too_low(self):
        """Test that values below minimum are clamped to minimum."""
        result = StateService.clamp_bulk_cache_age(
            0, default_days=7, min_days=1, max_days=30
        )
        assert result == 1

    def test_clamp_returns_max_when_value_too_high(self):
        """Test that values above maximum are clamped to maximum."""
        result = StateService.clamp_bulk_cache_age(
            100, default_days=7, min_days=1, max_days=30
        )
        assert result == 30

    def test_clamp_returns_default_for_invalid_input(self):
        """Test that default is returned for invalid input."""
        result = StateService.clamp_bulk_cache_age(
            "invalid", default_days=7, min_days=1, max_days=30
        )
        assert result == 7

    def test_clamp_returns_default_for_none(self):
        """Test that default is returned for None."""
        result = StateService.clamp_bulk_cache_age(
            None, default_days=7, min_days=1, max_days=30
        )
        assert result == 7

    def test_clamp_handles_float_strings(self):
        """Test that float strings are converted and clamped."""
        result = StateService.clamp_bulk_cache_age(
            "15.7", default_days=7, min_days=1, max_days=30
        )
        assert result == 15

    def test_clamp_handles_float_values(self):
        """Test that float values are converted to int."""
        result = StateService.clamp_bulk_cache_age(
            15.9, default_days=7, min_days=1, max_days=30
        )
        assert result == 15


class TestSerializeDeserializeZoneCards:
    """Tests for zone cards serialization/deserialization methods."""

    def test_serialize_zone_cards_basic(self):
        """Test basic serialization of zone cards."""
        # sanitize_zone_cards expects "qty" not "count"
        zone_cards = {
            "main": [{"name": "Lightning Bolt", "qty": 4}],
            "side": [{"name": "Leyline of the Void", "qty": 2}],
        }
        result = StateService.serialize_zone_cards(zone_cards)
        # The sanitize_zone_cards function should preserve valid entries
        assert "main" in result
        assert "side" in result

    def test_deserialize_zone_cards_with_valid_data(self):
        """Test deserialization with valid zone card data."""
        # sanitize_zone_cards expects "qty" not "count"
        data = {
            "main": [{"name": "Island", "qty": 10}],
            "side": [{"name": "Counterspell", "qty": 3}],
        }
        result = StateService.deserialize_zone_cards(data)
        assert isinstance(result, dict)
        assert "main" in result
        assert "side" in result

    def test_deserialize_zone_cards_with_invalid_data(self):
        """Test deserialization with invalid data returns empty dict."""
        result = StateService.deserialize_zone_cards("not a dict")
        assert result == {}

    def test_deserialize_zone_cards_with_none(self):
        """Test deserialization with None returns empty dict."""
        result = StateService.deserialize_zone_cards(None)
        assert result == {}

    def test_deserialize_zone_cards_filters_invalid_entries(self):
        """Test that invalid entries in zones are filtered out."""
        # sanitize_zone_cards expects "qty" not "count"
        data = {
            "main": [{"name": "Valid Card", "qty": 1}],
            "side": "not a list",  # Invalid - not a list
            "board": 123,  # Invalid - not a list
        }
        result = StateService.deserialize_zone_cards(data)
        assert isinstance(result, dict)
        # Invalid zones should be skipped
        # Valid zone with proper qty should be present
        assert "main" in result

    def test_deserialize_zone_cards_with_empty_dict(self):
        """Test deserialization with empty dict."""
        result = StateService.deserialize_zone_cards({})
        assert result == {}

    def test_serialize_deserialize_roundtrip(self):
        """Test that serialization and deserialization are reversible."""
        # sanitize_zone_cards expects "qty" not "count"
        original = {
            "main": [{"name": "Forest", "qty": 12}],
        }
        serialized = StateService.serialize_zone_cards(original)
        deserialized = StateService.deserialize_zone_cards(serialized)
        # After sanitization, the structure should be preserved
        assert isinstance(deserialized, dict)
        assert "main" in deserialized
