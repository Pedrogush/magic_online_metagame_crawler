"""Tests for ImageService business logic."""

from services.image_service import ImageService


def test_image_service_initialization():
    """Test ImageService initializes with correct default state."""
    service = ImageService()

    assert service.bulk_data_by_name is None
    assert service.printing_index_loading is False
    assert service.image_downloader is None


def test_set_bulk_data():
    """Test setting bulk data."""
    service = ImageService()
    test_data = {
        "Lightning Bolt": [{"name": "Lightning Bolt", "set": "LEA"}],
        "Island": [{"name": "Island", "set": "LEA"}],
    }

    service.set_bulk_data(test_data)

    assert service.get_bulk_data() == test_data


def test_get_bulk_data_initially_none():
    """Test that bulk data is initially None."""
    service = ImageService()

    assert service.get_bulk_data() is None


def test_clear_printing_index_loading():
    """Test clearing the printing index loading flag."""
    service = ImageService()
    service.printing_index_loading = True

    service.clear_printing_index_loading()

    assert service.printing_index_loading is False


def test_is_loading_initially_false():
    """Test that loading flag is initially false."""
    service = ImageService()

    assert service.is_loading() is False


def test_is_loading_when_loading():
    """Test that is_loading returns True when loading."""
    service = ImageService()
    service.printing_index_loading = True

    assert service.is_loading() is True
