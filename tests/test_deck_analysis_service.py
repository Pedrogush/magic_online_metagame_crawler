"""Tests for DeckAnalysisService."""

from unittest.mock import patch

import pytest

from services.deck_analysis_service import DeckAnalysisService


@pytest.fixture
def analysis_service():
    """Create a DeckAnalysisService instance."""
    return DeckAnalysisService()


@pytest.fixture
def sample_cards():
    """Sample card list for testing."""
    return [
        {
            "name": "Lightning Bolt",
            "quantity": 4,
            "mana_value": 1,
            "mana_cost": "{R}",
            "type_line": "Instant",
            "colors": ["R"],
        },
        {
            "name": "Monastery Swiftspear",
            "quantity": 4,
            "mana_value": 1,
            "mana_cost": "{R}",
            "type_line": "Creature — Human Monk",
            "colors": ["R"],
        },
        {
            "name": "Lava Spike",
            "quantity": 4,
            "mana_value": 1,
            "mana_cost": "{R}",
            "type_line": "Sorcery — Arcane",
            "colors": ["R"],
        },
        {
            "name": "Eidolon of the Great Revel",
            "quantity": 4,
            "mana_value": 2,
            "mana_cost": "{R}{R}",
            "type_line": "Enchantment Creature — Spirit",
            "colors": ["R"],
        },
        {
            "name": "Mountain",
            "quantity": 20,
            "mana_value": 0,
            "mana_cost": "",
            "type_line": "Basic Land — Mountain",
            "colors": [],
        },
    ]


class TestAnalyze:
    """Test main analyze functionality."""

    @patch("services.deck_analysis_service.analyze_deck")
    def test_analyze_calls_utility(self, mock_analyze, analysis_service):
        """Test that analyze calls the utility function."""
        expected_stats = {"curve": {}, "colors": {}}
        mock_analyze.return_value = expected_stats

        result = analysis_service.analyze("4 Lightning Bolt\n20 Mountain")

        mock_analyze.assert_called_once_with("4 Lightning Bolt\n20 Mountain")
        assert result == expected_stats


class TestCalculateManaCurve:
    """Test mana curve calculation."""

    def test_calculate_mana_curve_basic(self, analysis_service, sample_cards):
        """Test basic mana curve calculation."""
        curve = analysis_service.calculate_mana_curve(sample_cards)

        assert curve[0] == 20  # 20 lands
        assert curve[1] == 12  # 4 Bolts + 4 Swiftspears + 4 Spikes
        assert curve[2] == 4  # 4 Eidolons

    def test_calculate_mana_curve_caps_at_seven(self, analysis_service):
        """Test that mana curve caps at 7+."""
        cards = [
            {"name": "Test", "quantity": 1, "mana_value": 10},
            {"name": "Test2", "quantity": 1, "mana_value": 8},
            {"name": "Test3", "quantity": 1, "mana_value": 7},
        ]

        curve = analysis_service.calculate_mana_curve(cards)

        # Both 7, 8, and 10 should be capped at 7
        assert curve[7] == 3

    def test_calculate_mana_curve_empty(self, analysis_service):
        """Test mana curve with empty card list."""
        curve = analysis_service.calculate_mana_curve([])

        assert curve == {}

    def test_calculate_mana_curve_ignores_invalid(self, analysis_service):
        """Test that invalid mana values are ignored."""
        cards = [
            {"name": "Valid", "quantity": 4, "mana_value": 1},
            {"name": "No MV", "quantity": 2},  # Missing mana_value
            {"name": "String MV", "quantity": 1, "mana_value": "X"},  # Invalid type
        ]

        curve = analysis_service.calculate_mana_curve(cards)

        assert curve == {1: 4}

    def test_calculate_mana_curve_handles_float(self, analysis_service):
        """Test mana curve handles float values."""
        cards = [{"name": "Test", "quantity": 2, "mana_value": 3.0}]

        curve = analysis_service.calculate_mana_curve(cards)

        assert curve[3] == 2


class TestCalculateColorDistribution:
    """Test color distribution calculation."""

    def test_calculate_color_distribution_basic(self, analysis_service, sample_cards):
        """Test basic color distribution."""
        colors = analysis_service.calculate_color_distribution(sample_cards)

        # 4 Bolts + 4 Swiftspears + 4 Spikes + 8 Eidolons = 20 red symbols
        assert colors["R"] == 20
        assert colors["W"] == 0
        assert colors["U"] == 0
        assert colors["B"] == 0
        assert colors["G"] == 0

    def test_calculate_color_distribution_multicolor(self, analysis_service):
        """Test distribution with multicolor cards."""
        cards = [
            {"name": "Bolt", "quantity": 4, "mana_cost": "{R}"},
            {"name": "Counterspell", "quantity": 4, "mana_cost": "{U}{U}"},
            {"name": "Terminate", "quantity": 2, "mana_cost": "{B}{R}"},
        ]

        colors = analysis_service.calculate_color_distribution(cards)

        assert colors["R"] == 6  # 4 from Bolt + 2 from Terminate
        assert colors["U"] == 8  # 8 from Counterspell
        assert colors["B"] == 2  # 2 from Terminate

    def test_calculate_color_distribution_hybrid(self, analysis_service):
        """Test distribution counts hybrid mana separately."""
        cards = [
            {
                "name": "Boros Charm",
                "quantity": 4,
                "mana_cost": "{R}{W}",
            }  # Each symbol counted
        ]

        colors = analysis_service.calculate_color_distribution(cards)

        assert colors["R"] == 4
        assert colors["W"] == 4

    def test_calculate_color_distribution_colorless(self, analysis_service):
        """Test distribution with colorless cards."""
        cards = [{"name": "Wastes", "quantity": 4, "mana_cost": ""}]

        colors = analysis_service.calculate_color_distribution(cards)

        assert all(count == 0 for count in colors.values())

    def test_calculate_color_distribution_generic_mana(self, analysis_service):
        """Test that generic mana symbols are not counted."""
        cards = [{"name": "Fireball", "quantity": 4, "mana_cost": "{X}{R}"}]

        colors = analysis_service.calculate_color_distribution(cards)

        # Only R should be counted, not X
        assert colors["R"] == 4
        assert colors["C"] == 0


class TestIdentifyKeyCards:
    """Test key card identification."""

    def test_identify_key_cards_default_threshold(self, analysis_service, sample_cards):
        """Test identifying key cards with default threshold of 3."""
        key_cards = analysis_service.identify_key_cards(sample_cards)

        # Should include 4-ofs and exclude lands
        assert len(key_cards) == 5  # All non-lands have 4 copies or 20 copies
        card_names = [card["name"] for card in key_cards]
        assert "Lightning Bolt" in card_names
        assert "Mountain" in card_names

    def test_identify_key_cards_custom_threshold(self, analysis_service, sample_cards):
        """Test identifying key cards with custom threshold."""
        key_cards = analysis_service.identify_key_cards(sample_cards, threshold=4)

        # Should only include 4-ofs and above
        assert len(key_cards) == 5
        assert all(card["quantity"] >= 4 for card in key_cards)

    def test_identify_key_cards_high_threshold(self, analysis_service, sample_cards):
        """Test with high threshold."""
        key_cards = analysis_service.identify_key_cards(sample_cards, threshold=10)

        # Only lands meet threshold
        assert len(key_cards) == 1
        assert key_cards[0]["name"] == "Mountain"

    def test_identify_key_cards_empty(self, analysis_service):
        """Test with empty card list."""
        key_cards = analysis_service.identify_key_cards([])

        assert key_cards == []


class TestCalculateDeckTotals:
    """Test deck totals calculation."""

    def test_calculate_deck_totals_basic(self, analysis_service):
        """Test calculating totals for all zones."""
        zones = {
            "main": [
                {"name": "Card1", "quantity": 4},
                {"name": "Card2", "quantity": 56},
            ],
            "side": [{"name": "Card3", "quantity": 15}],
            "out": [{"name": "Card4", "quantity": 10}],
        }

        totals = analysis_service.calculate_deck_totals(zones)

        assert totals["main"] == 60
        assert totals["side"] == 15
        assert totals["out"] == 10

    def test_calculate_deck_totals_empty_zones(self, analysis_service):
        """Test with empty zones."""
        zones = {"main": [], "side": [], "out": []}

        totals = analysis_service.calculate_deck_totals(zones)

        assert totals["main"] == 0
        assert totals["side"] == 0
        assert totals["out"] == 0

    def test_calculate_deck_totals_missing_zones(self, analysis_service):
        """Test with missing zones."""
        zones = {"main": [{"name": "Card1", "quantity": 60}]}

        totals = analysis_service.calculate_deck_totals(zones)

        assert totals["main"] == 60
        # Missing zones should not be in result


class TestFindDuplicates:
    """Test finding duplicate cards between zones."""

    def test_find_duplicates_basic(self, analysis_service):
        """Test finding basic duplicates."""
        main = [
            {"name": "Lightning Bolt"},
            {"name": "Mountain"},
        ]
        side = [
            {"name": "Skullcrack"},
            {"name": "Mountain"},
        ]

        duplicates = analysis_service.find_duplicates(main, side)

        assert "Mountain" in duplicates
        assert len(duplicates) == 1

    def test_find_duplicates_none(self, analysis_service):
        """Test with no duplicates."""
        main = [{"name": "Lightning Bolt"}]
        side = [{"name": "Skullcrack"}]

        duplicates = analysis_service.find_duplicates(main, side)

        assert duplicates == []

    def test_find_duplicates_multiple(self, analysis_service):
        """Test with multiple duplicates."""
        main = [
            {"name": "Lightning Bolt"},
            {"name": "Lava Spike"},
            {"name": "Mountain"},
        ]
        side = [
            {"name": "Lightning Bolt"},
            {"name": "Lava Spike"},
            {"name": "Skullcrack"},
        ]

        duplicates = analysis_service.find_duplicates(main, side)

        assert len(duplicates) == 2
        assert "Lightning Bolt" in duplicates
        assert "Lava Spike" in duplicates

    def test_find_duplicates_empty_zones(self, analysis_service):
        """Test with empty zones."""
        duplicates = analysis_service.find_duplicates([], [])

        assert duplicates == []


class TestValidateDeck:
    """Test deck validation."""

    def test_validate_deck_valid(self, analysis_service):
        """Test validation of valid deck."""
        zones = {
            "main": [{"name": f"Main{i}", "quantity": 1} for i in range(60)],
            "side": [{"name": f"Side{i}", "quantity": 1} for i in range(15)],
        }

        result = analysis_service.validate_deck(zones, "Modern")

        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_validate_deck_too_few_cards(self, analysis_service):
        """Test validation with too few cards."""
        zones = {
            "main": [{"name": "Card", "quantity": 50}],
            "side": [],
        }

        result = analysis_service.validate_deck(zones, "Modern")

        assert result["valid"] is False
        assert any("minimum 60" in issue for issue in result["issues"])

    def test_validate_deck_too_many_sideboard(self, analysis_service):
        """Test validation with too many sideboard cards."""
        zones = {
            "main": [{"name": "Card", "quantity": 60}],
            "side": [{"name": "Card", "quantity": 20}],
        }

        result = analysis_service.validate_deck(zones, "Modern")

        assert result["valid"] is False
        assert any("maximum 15" in issue for issue in result["issues"])

    def test_validate_deck_commander_format(self, analysis_service):
        """Test that Commander format doesn't enforce 60-card minimum."""
        zones = {
            "main": [{"name": "Card", "quantity": 100}],
            "side": [],
        }

        result = analysis_service.validate_deck(zones, "Commander")

        # Should not complain about deck size for Commander
        assert not any("minimum 60" in issue for issue in result["issues"])

    def test_validate_deck_with_duplicates(self, analysis_service):
        """Test validation detects duplicates."""
        zones = {
            "main": [{"name": "Lightning Bolt", "quantity": 4}],
            "side": [{"name": "Lightning Bolt", "quantity": 2}],
        }

        result = analysis_service.validate_deck(zones, "Modern")

        assert result["valid"] is False
        assert any("both main and side" in issue for issue in result["issues"])

    def test_validate_deck_includes_totals(self, analysis_service):
        """Test that validation includes totals."""
        zones = {
            "main": [{"name": "Card", "quantity": 60}],
            "side": [{"name": "Card", "quantity": 10}],
        }

        result = analysis_service.validate_deck(zones, "Modern")

        assert "totals" in result
        assert result["totals"]["main"] == 60
        assert result["totals"]["side"] == 10


class TestCalculateCardTypeDistribution:
    """Test card type distribution calculation."""

    def test_calculate_type_distribution_basic(self, analysis_service, sample_cards):
        """Test basic type distribution."""
        types = analysis_service.calculate_card_type_distribution(sample_cards)

        assert types["Instant"] == 4  # Lightning Bolt
        assert types["Creature"] == 8  # Swiftspear + Eidolon
        assert types["Sorcery"] == 4  # Lava Spike
        assert types["Land"] == 20  # Mountain
        # Eidolon is counted as Creature (first match)

    def test_calculate_type_distribution_multitype(self, analysis_service):
        """Test distribution with multitype cards."""
        cards = [
            {
                "name": "Dryad Arbor",
                "quantity": 1,
                "type_line": "Land Creature — Forest Dryad",
            },
        ]

        types = analysis_service.calculate_card_type_distribution(cards)

        # Should count as Creature (first match in check order)
        assert types["Creature"] == 1

    def test_calculate_type_distribution_empty(self, analysis_service):
        """Test with empty card list."""
        types = analysis_service.calculate_card_type_distribution([])

        assert types == {}

    def test_calculate_type_distribution_unknown_type(self, analysis_service):
        """Test with unknown card type."""
        cards = [
            {"name": "Unknown", "quantity": 4, "type_line": "Unknown Type"}
        ]

        types = analysis_service.calculate_card_type_distribution(cards)

        # Unknown types are not counted
        assert types == {}
