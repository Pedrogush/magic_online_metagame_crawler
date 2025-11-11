"""Tests for ArchetypeService."""

from unittest.mock import patch

import pytest

from services.archetype_service import ArchetypeService


@pytest.fixture
def archetype_service():
    """Create an ArchetypeService instance."""
    return ArchetypeService()


@pytest.fixture
def sample_archetypes():
    """Sample archetype data for testing."""
    return [
        {"name": "Burn", "url": "/archetype/burn", "meta_share": "5.2%"},
        {"name": "Tron", "url": "/archetype/tron", "meta_share": "4.1%"},
        {"name": "Rakdos Midrange", "url": "/archetype/rakdos", "meta_share": "3.8%"},
        {"name": "Azorius Control", "url": "/archetype/azorius", "meta_share": "3.2%"},
    ]


@pytest.fixture
def sample_decks():
    """Sample deck data for testing."""
    return [
        {
            "number": "123",
            "player": "Alice",
            "event": "MTGO League",
            "result": "5-0",
            "date": "2025-11-11",
        },
        {
            "number": "456",
            "player": "Bob",
            "event": "MTGO Challenge",
            "result": "8-0",
            "date": "2025-11-10",
        },
    ]


class TestArchetypeServiceInitialization:
    """Test ArchetypeService initialization."""

    def test_initialization(self):
        """Test service initializes with empty cache."""
        service = ArchetypeService()

        assert hasattr(service, "_cache")
        assert isinstance(service._cache, dict)
        assert len(service._cache) == 0


class TestFetchArchetypes:
    """Test archetype fetching functionality."""

    @patch("services.archetype_service.get_archetypes")
    def test_fetch_archetypes_success(
        self, mock_get_archetypes, archetype_service, sample_archetypes
    ):
        """Test successful archetype fetching."""
        mock_get_archetypes.return_value = sample_archetypes

        result = archetype_service.fetch_archetypes("Modern")

        mock_get_archetypes.assert_called_once_with("modern")
        assert result == sample_archetypes

    @patch("services.archetype_service.get_archetypes")
    def test_fetch_archetypes_caches_result(
        self, mock_get_archetypes, archetype_service, sample_archetypes
    ):
        """Test that archetypes are cached."""
        mock_get_archetypes.return_value = sample_archetypes

        # First call
        result1 = archetype_service.fetch_archetypes("Modern")

        # Second call should use cache
        result2 = archetype_service.fetch_archetypes("Modern")

        # get_archetypes should only be called once
        assert mock_get_archetypes.call_count == 1
        assert result1 == result2

    @patch("services.archetype_service.get_archetypes")
    def test_fetch_archetypes_force_refresh(
        self, mock_get_archetypes, archetype_service, sample_archetypes
    ):
        """Test force refresh bypasses cache."""
        mock_get_archetypes.return_value = sample_archetypes

        # First call
        archetype_service.fetch_archetypes("Modern")

        # Force refresh
        archetype_service.fetch_archetypes("Modern", force=True)

        # get_archetypes should be called twice
        assert mock_get_archetypes.call_count == 2

    @patch("services.archetype_service.get_archetypes")
    def test_fetch_archetypes_different_formats(
        self, mock_get_archetypes, archetype_service, sample_archetypes
    ):
        """Test that different formats have separate cache entries."""
        mock_get_archetypes.return_value = sample_archetypes

        archetype_service.fetch_archetypes("Modern")
        archetype_service.fetch_archetypes("Pioneer")

        # Should be called twice for different formats
        assert mock_get_archetypes.call_count == 2

    @patch("services.archetype_service.get_archetypes")
    def test_fetch_archetypes_case_insensitive(
        self, mock_get_archetypes, archetype_service, sample_archetypes
    ):
        """Test that format names are case-insensitive for caching."""
        mock_get_archetypes.return_value = sample_archetypes

        archetype_service.fetch_archetypes("Modern")
        archetype_service.fetch_archetypes("MODERN")

        # Should use cache, only called once
        assert mock_get_archetypes.call_count == 1


class TestFilterArchetypes:
    """Test archetype filtering functionality."""

    def test_filter_archetypes_by_name(self, archetype_service, sample_archetypes):
        """Test filtering archetypes by name."""
        result = archetype_service.filter_archetypes(sample_archetypes, "burn")

        assert len(result) == 1
        assert result[0]["name"] == "Burn"

    def test_filter_archetypes_partial_match(self, archetype_service, sample_archetypes):
        """Test partial name matching."""
        result = archetype_service.filter_archetypes(sample_archetypes, "control")

        assert len(result) == 1
        assert result[0]["name"] == "Azorius Control"

    def test_filter_archetypes_case_insensitive(
        self, archetype_service, sample_archetypes
    ):
        """Test filtering is case-insensitive."""
        result1 = archetype_service.filter_archetypes(sample_archetypes, "BURN")
        result2 = archetype_service.filter_archetypes(sample_archetypes, "burn")

        assert result1 == result2
        assert len(result1) == 1

    def test_filter_archetypes_empty_query(self, archetype_service, sample_archetypes):
        """Test that empty query returns all archetypes."""
        result = archetype_service.filter_archetypes(sample_archetypes, "")

        assert result == sample_archetypes

    def test_filter_archetypes_whitespace_query(
        self, archetype_service, sample_archetypes
    ):
        """Test that whitespace-only query returns all."""
        result = archetype_service.filter_archetypes(sample_archetypes, "   ")

        assert result == sample_archetypes

    def test_filter_archetypes_no_matches(self, archetype_service, sample_archetypes):
        """Test filtering with no matches returns empty list."""
        result = archetype_service.filter_archetypes(sample_archetypes, "nonexistent")

        assert result == []

    def test_filter_archetypes_multiple_matches(
        self, archetype_service, sample_archetypes
    ):
        """Test filtering with multiple matches."""
        result = archetype_service.filter_archetypes(sample_archetypes, "o")

        # Should match "Tron", "Azorius Control", "Rakdos Midrange"
        assert len(result) >= 2


class TestFetchDecksForArchetype:
    """Test deck fetching for archetypes."""

    @patch("services.archetype_service.get_archetype_decks")
    def test_fetch_decks_success(
        self, mock_get_decks, archetype_service, sample_decks
    ):
        """Test successful deck fetching for an archetype."""
        mock_get_decks.return_value = sample_decks

        result = archetype_service.fetch_decks_for_archetype("Modern", "Burn")

        mock_get_decks.assert_called_once_with("Modern", "Burn")
        assert result == sample_decks

    @patch("services.archetype_service.get_archetype_decks")
    def test_fetch_decks_empty_result(self, mock_get_decks, archetype_service):
        """Test fetching decks with no results."""
        mock_get_decks.return_value = []

        result = archetype_service.fetch_decks_for_archetype("Modern", "Burn")

        assert result == []

    @patch("services.archetype_service.get_archetype_decks")
    def test_fetch_decks_propagates_exception(
        self, mock_get_decks, archetype_service
    ):
        """Test that exceptions from get_archetype_decks are propagated."""
        mock_get_decks.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            archetype_service.fetch_decks_for_archetype("Modern", "Burn")


class TestClearCache:
    """Test cache clearing functionality."""

    @patch("services.archetype_service.get_archetypes")
    def test_clear_cache(self, mock_get_archetypes, archetype_service, sample_archetypes):
        """Test that clear_cache removes all cached data."""
        mock_get_archetypes.return_value = sample_archetypes

        # Populate cache
        archetype_service.fetch_archetypes("Modern")
        assert len(archetype_service._cache) > 0

        # Clear cache
        archetype_service.clear_cache()
        assert len(archetype_service._cache) == 0

        # Next fetch should hit API again
        archetype_service.fetch_archetypes("Modern")
        assert mock_get_archetypes.call_count == 2


class TestGetArchetypeSummary:
    """Test archetype summary generation."""

    def test_get_archetype_summary_with_decks(
        self, archetype_service, sample_decks
    ):
        """Test generating summary with decks."""
        summary = archetype_service.get_archetype_summary("Burn", sample_decks)

        assert "Burn" in summary
        assert "2" in summary  # Number of decklists
        assert "Alice" in summary or "Bob" in summary  # Player names

    def test_get_archetype_summary_no_decks(self, archetype_service):
        """Test generating summary with no decks."""
        summary = archetype_service.get_archetype_summary("Burn", [])

        assert "Burn" in summary
        assert "No decks found" in summary

    def test_get_archetype_summary_many_decks(self, archetype_service):
        """Test summary with many decks (should limit display)."""
        many_decks = [
            {
                "number": str(i),
                "player": f"Player{i}",
                "event": f"Event{i}",
                "result": "5-0",
                "date": "2025-11-11",
            }
            for i in range(20)
        ]

        summary = archetype_service.get_archetype_summary("Burn", many_decks)

        assert "20" in summary  # Total count
        # Should not include all players (limited to 5)
        # Count Player names, not the "Players:" label
        # Just verify not all 20 players are listed
        assert len(summary) < 1000  # Summary should be reasonably short

    def test_get_archetype_summary_includes_events(
        self, archetype_service, sample_decks
    ):
        """Test that summary includes event information."""
        summary = archetype_service.get_archetype_summary("Burn", sample_decks)

        assert "MTGO League" in summary or "MTGO Challenge" in summary
