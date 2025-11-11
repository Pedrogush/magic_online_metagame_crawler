"""Tests for DeckService."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from services.deck_service import DeckService


@pytest.fixture
def deck_service(tmp_path):
    """Create a DeckService instance with temporary directory."""
    return DeckService(tmp_path)


@pytest.fixture
def sample_deck_text():
    """Sample deck text for testing."""
    return """4 Lightning Bolt
4 Monastery Swiftspear
20 Mountain

Sideboard
3 Skullcrack
2 Smash to Smithereens
"""


class TestDeckServiceInitialization:
    """Test DeckService initialization."""

    def test_initialization_creates_directory(self, tmp_path):
        """Test that service creates deck directory on init."""
        deck_dir = tmp_path / "decks"
        assert not deck_dir.exists()

        service = DeckService(deck_dir)

        assert deck_dir.exists()
        assert deck_dir.is_dir()

    def test_initialization_with_existing_directory(self, tmp_path):
        """Test initialization with existing directory works."""
        tmp_path.mkdir(exist_ok=True)
        service = DeckService(tmp_path)

        assert service.deck_save_dir == tmp_path


class TestParseDeck:
    """Test deck parsing functionality."""

    def test_parse_basic_deck(self, deck_service, sample_deck_text):
        """Test parsing a basic deck with mainboard and sideboard."""
        zones = deck_service.parse_deck(sample_deck_text)

        assert "main" in zones
        assert "side" in zones
        assert "out" in zones

        # Check mainboard
        assert len(zones["main"]) == 3
        assert zones["main"][0]["name"] == "Lightning Bolt"
        assert zones["main"][0]["quantity"] == 4
        assert zones["main"][1]["name"] == "Monastery Swiftspear"
        assert zones["main"][1]["quantity"] == 4
        assert zones["main"][2]["name"] == "Mountain"
        assert zones["main"][2]["quantity"] == 20

        # Check sideboard
        assert len(zones["side"]) == 2
        assert zones["side"][0]["name"] == "Skullcrack"
        assert zones["side"][0]["quantity"] == 3

    def test_parse_deck_without_sideboard(self, deck_service):
        """Test parsing deck with only mainboard."""
        deck_text = """4 Lightning Bolt
20 Mountain"""

        zones = deck_service.parse_deck(deck_text)

        assert len(zones["main"]) == 2
        assert len(zones["side"]) == 0
        assert len(zones["out"]) == 0

    def test_parse_empty_deck(self, deck_service):
        """Test parsing empty deck."""
        zones = deck_service.parse_deck("")

        assert len(zones["main"]) == 0
        assert len(zones["side"]) == 0
        assert len(zones["out"]) == 0

    def test_parse_deck_ignores_invalid_lines(self, deck_service):
        """Test that parser ignores invalid lines."""
        deck_text = """4 Lightning Bolt
Invalid line without number
20 Mountain
Another invalid line
"""

        zones = deck_service.parse_deck(deck_text)

        assert len(zones["main"]) == 2
        assert zones["main"][0]["name"] == "Lightning Bolt"
        assert zones["main"][1]["name"] == "Mountain"

    def test_parse_deck_with_blank_lines(self, deck_service):
        """Test parsing deck with blank lines."""
        deck_text = """4 Lightning Bolt

20 Mountain

Sideboard

3 Skullcrack
"""

        zones = deck_service.parse_deck(deck_text)

        assert len(zones["main"]) == 2
        assert len(zones["side"]) == 1


class TestBuildDeckText:
    """Test deck text building functionality."""

    def test_build_deck_text_with_main_and_side(self, deck_service):
        """Test building deck text from zones."""
        zones = {
            "main": [
                {"name": "Lightning Bolt", "quantity": 4},
                {"name": "Mountain", "quantity": 20},
            ],
            "side": [
                {"name": "Skullcrack", "quantity": 3},
            ],
        }

        deck_text = deck_service.build_deck_text(zones)

        assert "4 Lightning Bolt" in deck_text
        assert "20 Mountain" in deck_text
        assert "Sideboard" in deck_text
        assert "3 Skullcrack" in deck_text

    def test_build_deck_text_without_sideboard(self, deck_service):
        """Test building deck text without sideboard."""
        zones = {
            "main": [
                {"name": "Lightning Bolt", "quantity": 4},
            ],
            "side": [],
        }

        deck_text = deck_service.build_deck_text(zones)

        assert "4 Lightning Bolt" in deck_text
        assert "Sideboard" not in deck_text

    def test_build_deck_text_empty(self, deck_service):
        """Test building empty deck text."""
        zones = {"main": [], "side": []}

        deck_text = deck_service.build_deck_text(zones)

        assert deck_text == ""


class TestSaveDeck:
    """Test deck saving functionality."""

    def test_save_deck_creates_file(self, deck_service, sample_deck_text):
        """Test that save_deck creates a file."""
        filepath = deck_service.save_deck(sample_deck_text, "test_deck")

        assert filepath.exists()
        assert filepath.name == "test_deck.txt"
        assert filepath.read_text(encoding="utf-8") == sample_deck_text

    def test_save_deck_sanitizes_filename(self, deck_service, sample_deck_text):
        """Test that filename is sanitized."""
        filepath = deck_service.save_deck(sample_deck_text, "test/deck<>")

        assert filepath.exists()
        assert "/" not in filepath.name
        assert "<" not in filepath.name
        assert ">" not in filepath.name

    def test_save_deck_handles_duplicates(self, deck_service, sample_deck_text):
        """Test that duplicate filenames get numbered."""
        filepath1 = deck_service.save_deck(sample_deck_text, "test_deck")
        filepath2 = deck_service.save_deck(sample_deck_text, "test_deck")

        assert filepath1.exists()
        assert filepath2.exists()
        assert filepath1 != filepath2
        assert filepath1.name == "test_deck.txt"
        assert filepath2.name == "test_deck_1.txt"

    def test_save_deck_with_empty_name(self, deck_service, sample_deck_text):
        """Test save with empty name uses default."""
        filepath = deck_service.save_deck(sample_deck_text, "")

        assert filepath.exists()
        assert "deck" in filepath.name


class TestAnalyzeDeck:
    """Test deck analysis functionality."""

    @patch("services.deck_service.analyze_deck")
    def test_analyze_deck_calls_utility(self, mock_analyze, deck_service, sample_deck_text):
        """Test that analyze_deck calls the utility function."""
        expected_stats = {"curve": {}, "colors": {}}
        mock_analyze.return_value = expected_stats

        result = deck_service.analyze_deck(sample_deck_text)

        mock_analyze.assert_called_once_with(sample_deck_text)
        assert result == expected_stats


class TestDeckToDictionary:
    """Test deck to dictionary conversion."""

    @patch("services.deck_service.deck_to_dictionary")
    def test_deck_to_dictionary_calls_utility(
        self, mock_to_dict, deck_service, sample_deck_text
    ):
        """Test that deck_to_dictionary calls utility function."""
        expected_dict = {"Lightning Bolt": 4, "Mountain": 20}
        mock_to_dict.return_value = expected_dict

        result = deck_service.deck_to_dictionary(sample_deck_text)

        mock_to_dict.assert_called_once_with(sample_deck_text)
        assert result == expected_dict


class TestSaveToDb:
    """Test database saving functionality."""

    @patch("services.deck_service.save_deck_to_db")
    def test_save_to_db_calls_utility(self, mock_save_db, deck_service, sample_deck_text):
        """Test that save_to_db calls the database utility."""
        metadata = {"format": "Modern", "archetype": "Burn"}

        deck_service.save_to_db(sample_deck_text, metadata)

        mock_save_db.assert_called_once_with(sample_deck_text, metadata)

    @patch("services.deck_service.save_deck_to_db")
    def test_save_to_db_with_no_metadata(
        self, mock_save_db, deck_service, sample_deck_text
    ):
        """Test save_to_db with no metadata."""
        deck_service.save_to_db(sample_deck_text)

        mock_save_db.assert_called_once_with(sample_deck_text, {})

    @patch("services.deck_service.save_deck_to_db")
    def test_save_to_db_handles_exception(
        self, mock_save_db, deck_service, sample_deck_text
    ):
        """Test that save_to_db handles exceptions gracefully."""
        mock_save_db.side_effect = Exception("Database error")

        # Should not raise exception
        deck_service.save_to_db(sample_deck_text)


class TestDownloadDeck:
    """Test deck downloading functionality."""

    @patch("services.deck_service.download_deck")
    def test_download_deck_success(self, mock_download, deck_service):
        """Test successful deck download."""
        deck_dict = {"number": "12345", "player": "Test"}
        expected_text = "4 Lightning Bolt\n20 Mountain"
        mock_download.return_value = expected_text

        result = deck_service.download_deck(deck_dict)

        mock_download.assert_called_once_with("12345")
        assert result == expected_text

    def test_download_deck_no_number(self, deck_service):
        """Test download with missing deck number raises error."""
        deck_dict = {"player": "Test"}

        with pytest.raises(ValueError, match="Deck number not found"):
            deck_service.download_deck(deck_dict)


class TestBuildDailyAverage:
    """Test daily average building functionality."""

    @patch("services.deck_service.download_deck")
    @patch("services.deck_service.add_dicts")
    def test_build_daily_average_multiple_decks(
        self, mock_add_dicts, mock_download, deck_service
    ):
        """Test building daily average from multiple decks."""
        decks = [
            {"number": "123"},
            {"number": "456"},
        ]
        mock_download.side_effect = [
            "4 Lightning Bolt\n20 Mountain",
            "4 Lava Spike\n20 Mountain",
        ]
        mock_add_dicts.side_effect = [
            {"Lightning Bolt": 4, "Mountain": 20},
            {"Lightning Bolt": 4, "Lava Spike": 4, "Mountain": 40},
        ]

        buffer, count = deck_service.build_daily_average(decks, "Modern")

        assert count == 2
        assert mock_download.call_count == 2

    @patch("services.deck_service.download_deck")
    def test_build_daily_average_skips_invalid_decks(
        self, mock_download, deck_service
    ):
        """Test that invalid decks are skipped."""
        decks = [
            {"number": "123"},
            {},  # No number
            {"number": "456"},
        ]
        mock_download.side_effect = [
            "4 Lightning Bolt",
            "4 Lava Spike",
        ]

        buffer, count = deck_service.build_daily_average(decks, "Modern")

        # Only 2 valid decks processed
        assert count == 2

    @patch("services.deck_service.download_deck")
    def test_build_daily_average_handles_download_errors(
        self, mock_download, deck_service
    ):
        """Test that download errors are handled gracefully."""
        decks = [
            {"number": "123"},
            {"number": "456"},
        ]
        mock_download.side_effect = [
            "4 Lightning Bolt",
            Exception("Download failed"),
        ]

        buffer, count = deck_service.build_daily_average(decks, "Modern")

        # Only 1 deck processed successfully
        assert count == 1


class TestRenderAverageDeck:
    """Test average deck rendering functionality."""

    def test_render_average_deck_basic(self, deck_service):
        """Test rendering average deck."""
        buffer = {
            "Lightning Bolt": 8.0,
            "Mountain": 40.0,
            "Lava Spike": 2.0,
        }
        decks_added = 2

        result = deck_service.render_average_deck(buffer, decks_added)

        assert "4 Lightning Bolt" in result
        assert "20 Mountain" in result
        assert "1 Lava Spike" in result
        assert "# Average of 2 decks" in result

    def test_render_average_deck_empty(self, deck_service):
        """Test rendering empty average deck."""
        buffer = {}
        decks_added = 0

        result = deck_service.render_average_deck(buffer, decks_added)

        assert result == ""

    def test_render_average_deck_separates_main_and_side(self, deck_service):
        """Test that high frequency cards go to main, low to side."""
        buffer = {
            "Lightning Bolt": 8.0,  # 4 per deck
            "Mountain": 40.0,  # 20 per deck
            "Skullcrack": 0.5,  # 0.25 per deck (< 50%)
        }
        decks_added = 2

        result = deck_service.render_average_deck(buffer, decks_added)

        # High frequency should be in main
        lines = result.split("\n")
        main_section = "\n".join(lines[:lines.index("Sideboard")])
        side_section = "\n".join(lines[lines.index("Sideboard"):])

        assert "Lightning Bolt" in main_section
        assert "Mountain" in main_section
        assert "Skullcrack" in side_section or "Skullcrack" not in result  # Rounds to 0
