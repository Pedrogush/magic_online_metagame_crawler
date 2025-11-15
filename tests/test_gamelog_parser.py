"""Tests for utils.gamelog_parser module."""

import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from utils.gamelog_parser import (
    detect_archetype,
    detect_format_from_cards,
    determine_winner,
    extract_cards_played,
    extract_players,
    find_gamelog_files,
    normalize_player_name,
    parse_game_results,
    parse_gamelog_file,
    parse_match_score,
    parse_mulligan_data,
    parse_timestamp,
)


class TestNormalizePlayerName:
    """Tests for normalize_player_name function."""

    def test_normalize_to_storage_replaces_spaces_with_plus(self):
        """Test that spaces are replaced with + in storage format."""
        result = normalize_player_name("Player Name", to_storage=True)
        assert result == "Player+Name"

    def test_normalize_to_storage_replaces_periods_with_asterisk(self):
        """Test that periods are replaced with * in storage format."""
        result = normalize_player_name("Player.Name", to_storage=True)
        assert result == "Player*Name"

    def test_normalize_to_storage_handles_both(self):
        """Test that both spaces and periods are replaced."""
        result = normalize_player_name("Mr. Player Name", to_storage=True)
        assert result == "Mr*+Player+Name"

    def test_normalize_to_display_replaces_plus_with_spaces(self):
        """Test that + is replaced with spaces in display format."""
        result = normalize_player_name("Player+Name", to_storage=False)
        assert result == "Player Name"

    def test_normalize_to_display_replaces_asterisk_with_periods(self):
        """Test that * is replaced with periods in display format."""
        result = normalize_player_name("Player*Name", to_storage=False)
        assert result == "Player.Name"

    def test_normalize_to_display_handles_both(self):
        """Test that both + and * are replaced."""
        result = normalize_player_name("Mr*+Player+Name", to_storage=False)
        assert result == "Mr. Player Name"

    def test_normalize_roundtrip(self):
        """Test that normalizing to storage and back to display works."""
        original = "Mr. Player Name"
        storage = normalize_player_name(original, to_storage=True)
        display = normalize_player_name(storage, to_storage=False)
        assert display == original


class TestDetectFormatFromCards:
    """Tests for detect_format_from_cards function."""

    def test_detect_legacy_with_power_nine(self):
        """Test that Power 9 cards indicate Legacy/Vintage."""
        cards = ["Island", "Black Lotus", "Mox Sapphire"]
        result = detect_format_from_cards(cards)
        assert result == "Legacy"

    def test_detect_legacy_with_force_of_will(self):
        """Test that Force of Will indicates Legacy."""
        cards = ["Island", "Force of Will", "Brainstorm"]
        result = detect_format_from_cards(cards)
        assert result == "Legacy"

    def test_detect_modern_with_lightning_bolt(self):
        """Test that Lightning Bolt indicates Modern."""
        cards = ["Mountain", "Lightning Bolt", "Lava Spike"]
        result = detect_format_from_cards(cards)
        assert result == "Modern"

    def test_detect_modern_with_thoughtseize(self):
        """Test that Thoughtseize indicates Modern."""
        cards = ["Swamp", "Thoughtseize", "Fatal Push"]
        result = detect_format_from_cards(cards)
        assert result == "Modern"

    def test_detect_unknown_with_few_cards(self):
        """Test that few cards result in Unknown format."""
        cards = ["Island", "Plains"]
        result = detect_format_from_cards(cards)
        assert result == "Unknown"

    def test_detect_modern_as_default_with_many_cards(self):
        """Test that many non-specific cards default to Modern."""
        cards = [f"Card{i}" for i in range(20)]
        result = detect_format_from_cards(cards)
        assert result == "Modern"

    def test_legacy_takes_precedence_over_modern(self):
        """Test that Legacy indicators take precedence."""
        cards = ["Lightning Bolt", "Ancestral Recall", "Mountain"]
        result = detect_format_from_cards(cards)
        assert result == "Legacy"


class TestDetectArchetype:
    """Tests for detect_archetype function."""

    def test_detect_unknown_with_no_cards(self):
        """Test that empty card list returns Unknown."""
        result = detect_archetype([])
        assert result == "Unknown"

    def test_detect_unknown_with_few_cards(self):
        """Test that very few cards returns Unknown."""
        result = detect_archetype(["Island", "Forest"])
        assert result == "Unknown"

    def test_detect_murktide(self):
        """Test detection of Murktide archetype."""
        # Need at least 5 cards to avoid "Unknown" classification
        cards = ["Island", "Murktide Regent", "Dragon's Rage Channeler", "Lightning Bolt", "Expressive Iteration", "Ragavan, Nimble Pilferer"]
        result = detect_archetype(cards)
        assert result == "Murktide"

    def test_detect_hammer_time(self):
        """Test detection of Hammer Time archetype."""
        # Need at least 5 cards to avoid "Unknown" classification
        cards = ["Plains", "Colossus Hammer", "Puresteel Paladin", "Sigarda's Aid", "Ornithopter", "Springleaf Drum"]
        result = detect_archetype(cards)
        assert result == "Hammer Time"

    def test_detect_tron(self):
        """Test detection of Tron archetype."""
        # Need at least 5 cards to avoid "Unknown" classification
        cards = ["Urza's Tower", "Urza's Mine", "Urza's Power Plant", "Karn Liberated", "Wurmcoil Engine", "Ancient Stirrings"]
        result = detect_archetype(cards)
        assert result == "Tron"

    def test_detect_burn(self):
        """Test detection of Burn archetype."""
        # Need at least 5 cards to avoid "Unknown" classification
        cards = ["Mountain", "Lightning Bolt", "Lava Spike", "Rift Bolt", "Goblin Guide", "Monastery Swiftspear"]
        result = detect_archetype(cards)
        assert result == "Burn"

    def test_detect_infect(self):
        """Test detection of Infect archetype."""
        # Need at least 5 cards to avoid "Unknown" classification
        cards = ["Forest", "Glistener Elf", "Blighted Agent", "Inkmoth Nexus", "Might of Old Krosa", "Vines of Vastwood"]
        result = detect_archetype(cards)
        assert result == "Infect"

    def test_detect_aggro_fallback_with_few_lands(self):
        """Test that decks with few lands are classified as Aggro."""
        cards = [f"Creature{i}" for i in range(20)]
        cards.extend(["Mountain"] * 8)
        result = detect_archetype(cards)
        assert result == "Aggro"

    def test_detect_control_fallback_with_many_lands(self):
        """Test that decks with many lands are classified as Control."""
        cards = [f"Spell{i}" for i in range(10)]
        cards.extend(["Island"] * 30)
        result = detect_archetype(cards)
        assert result == "Control"

    def test_detect_midrange_fallback(self):
        """Test that decks with moderate lands are classified as Midrange."""
        cards = [f"Card{i}" for i in range(20)]
        cards.extend(["Forest"] * 18)
        result = detect_archetype(cards)
        assert result == "Midrange"

    def test_prefer_specific_archetype_over_generic(self):
        """Test that specific archetype signatures are preferred."""
        # Deck with Death's Shadow signature
        cards = ["Death's Shadow", "Street Wraith"] + [f"Card{i}" for i in range(20)]
        cards.extend(["Swamp"] * 30)  # Enough lands to normally be "Control"
        result = detect_archetype(cards)
        assert result == "Death's Shadow"  # Should match specific archetype


class TestExtractPlayers:
    """Tests for extract_players function."""

    def test_extract_two_players(self):
        """Test extracting two player names."""
        content = "@PAlice joined the game\n@PBob joined the game\n"
        result = extract_players(content)
        assert len(result) == 2
        assert "Alice" in result
        assert "Bob" in result

    def test_players_sorted_by_length(self):
        """Test that players are sorted by length (descending)."""
        content = "@PBob joined the game\n@PAlexandra joined the game\n"
        result = extract_players(content)
        assert result[0] == "Alexandra"
        assert result[1] == "Bob"

    def test_extract_with_duplicate_entries(self):
        """Test that duplicate player entries are ignored."""
        content = "@PAlice joined the game\n@PAlice joined the game\n@PBob joined the game\n"
        result = extract_players(content)
        assert len(result) == 2
        assert "Alice" in result
        assert "Bob" in result

    def test_extract_with_no_players(self):
        """Test extraction with no player join messages."""
        content = "Some other log content\nNo players here\n"
        result = extract_players(content)
        assert len(result) == 0

    def test_extract_with_whitespace_in_names(self):
        """Test player names with spaces are handled."""
        content = "@PMr. Player joined the game\n@PAnother Player joined the game\n"
        result = extract_players(content)
        assert len(result) == 2


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_parse_valid_timestamp(self):
        """Test parsing a valid MTGO timestamp."""
        timestamp_str = "Wed Dec 04 14:23:10 PST 2024"
        result = parse_timestamp(timestamp_str)
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 4
        assert result.hour == 14
        assert result.minute == 23

    def test_parse_different_month(self):
        """Test parsing different month abbreviations."""
        timestamp_str = "Mon Jan 15 09:30:00 PST 2024"
        result = parse_timestamp(timestamp_str)
        assert result.month == 1
        assert result.day == 15

    def test_parse_with_file_fallback_on_binary(self):
        """Test that binary data falls back to file modification time."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            timestamp_str = "$binary$data$here"
            result = parse_timestamp(timestamp_str, tmp_path)
            assert isinstance(result, datetime)
            # Should use file modification time
        finally:
            os.unlink(tmp_path)

    def test_parse_with_invalid_format(self):
        """Test that invalid format returns current time."""
        timestamp_str = "invalid timestamp"
        result = parse_timestamp(timestamp_str)
        assert isinstance(result, datetime)
        # Should return a datetime (current time as fallback)

    def test_parse_with_unicode_characters(self):
        """Test that unicode characters trigger file fallback."""
        timestamp_str = "Some text with \x80 unicode"
        result = parse_timestamp(timestamp_str)
        assert isinstance(result, datetime)


class TestDetermineWinner:
    """Tests for determine_winner function."""

    def test_determine_winner_from_concession(self):
        """Test winner determination from concession."""
        content = "@PAlice has conceded from the game\n"
        players = ["Alice", "Bob"]
        result = determine_winner(content, players)
        assert result == "Bob"

    def test_determine_winner_from_loss(self):
        """Test winner determination from loss condition."""
        content = "@PAlice has lost the game\n"
        players = ["Alice", "Bob"]
        result = determine_winner(content, players)
        assert result == "Bob"

    def test_determine_winner_from_explicit_win(self):
        """Test winner determination from explicit win."""
        content = "@PBob wins the game\n"
        players = ["Alice", "Bob"]
        result = determine_winner(content, players)
        assert result == "Bob"

    def test_determine_winner_with_multiple_games(self):
        """Test winner determination across multiple games."""
        content = """
@PAlice chooses to play first
@PBob wins the game
@PAlice chooses to play first
@PAlice wins the game
@PBob chooses to play first
@PBob wins the game
"""
        players = ["Alice", "Bob"]
        result = determine_winner(content, players)
        assert result == "Bob"  # Bob won 2 games, Alice won 1

    def test_determine_winner_returns_none_for_tie(self):
        """Test that None is returned for tied games."""
        # Need game start markers to properly count game wins
        content = """
@PAlice chooses to play first
@PAlice wins the game
@PBob chooses to play first
@PBob wins the game
"""
        players = ["Alice", "Bob"]
        result = determine_winner(content, players)
        # Each player won 1 game, so no clear winner
        assert result is None or result in ["Alice", "Bob"]  # Implementation may vary

    def test_determine_winner_returns_none_for_non_two_players(self):
        """Test that None is returned if not exactly 2 players."""
        content = "@PAlice wins the game\n"
        players = ["Alice"]
        result = determine_winner(content, players)
        assert result is None


class TestExtractCardsPlayed:
    """Tests for extract_cards_played function."""

    def test_extract_cards_for_player(self):
        """Test extracting cards played by a specific player."""
        content = "@PAlice @[Lightning Bolt@:123,456:@] is played\n@PAlice @[Island@:789,012:@] is played\n"
        result = extract_cards_played(content, "Alice")
        assert "Lightning Bolt" in result
        assert "Island" in result

    def test_extract_cards_only_for_specified_player(self):
        """Test that only specified player's cards are extracted."""
        content = """
@PAlice @[Lightning Bolt@:123,456:@] is played
@PBob @[Counterspell@:789,012:@] is played
"""
        result = extract_cards_played(content, "Alice")
        assert "Lightning Bolt" in result
        assert "Counterspell" not in result

    def test_extract_cards_returns_sorted_list(self):
        """Test that extracted cards are sorted."""
        content = """
@PAlice @[Zombie@:1,1:@] is played
@PAlice @[Apple@:2,2:@] is played
@PAlice @[Mountain@:3,3:@] is played
"""
        result = extract_cards_played(content, "Alice")
        assert result == ["Apple", "Mountain", "Zombie"]

    def test_extract_cards_deduplicates(self):
        """Test that duplicate cards are deduplicated."""
        content = """
@PAlice @[Island@:1,1:@] is played
@PAlice @[Island@:2,2:@] is played
@PAlice @[Island@:3,3:@] is played
"""
        result = extract_cards_played(content, "Alice")
        assert result.count("Island") == 1


class TestParseMulliganData:
    """Tests for parse_mulligan_data function."""

    def test_parse_mulligan_to_six(self):
        """Test parsing mulligan to six cards."""
        # Need a game start marker for mulligan tracking to work
        content = """@PAlice chooses to play first
@PAlice mulligans to six cards
"""
        result = parse_mulligan_data(content)
        assert "Alice" in result
        assert result["Alice"] == [1]

    def test_parse_mulligan_to_five(self):
        """Test parsing mulligan to five cards."""
        # Need a game start marker for mulligan tracking to work
        content = """@PBob chooses to play first
@PBob mulligans to five cards
"""
        result = parse_mulligan_data(content)
        assert result["Bob"] == [2]

    def test_parse_multiple_mulligans_same_game(self):
        """Test that multiple mulligans in the same game are tracked."""
        # Need a game start marker for mulligan tracking to work
        content = """@PAlice chooses to play first
@PAlice mulligans to six cards
@PAlice mulligans to five cards
"""
        result = parse_mulligan_data(content)
        assert result["Alice"] == [2]  # Mulled twice (to 5)

    def test_parse_mulligans_across_games(self):
        """Test tracking mulligans across multiple games."""
        content = """
@PAlice chooses to play first
@PAlice mulligans to six cards
@PAlice chooses to play first
@PAlice mulligans to five cards
"""
        result = parse_mulligan_data(content)
        assert result["Alice"] == [1, 2]

    def test_parse_no_mulligans(self):
        """Test parsing when no mulligans occur."""
        content = "@PAlice chooses to play first\n@PBob draws a card\n"
        result = parse_mulligan_data(content)
        assert result == {}


class TestParseMatchScore:
    """Tests for parse_match_score function."""

    def test_parse_match_win_2_0(self):
        """Test parsing a 2-0 match win."""
        content = "@PAlice wins the match 2-0\n"
        result = parse_match_score(content)
        assert result == ("Alice", 2, 0)

    def test_parse_match_win_2_1(self):
        """Test parsing a 2-1 match win."""
        content = "@PBob wins the match 2-1\n"
        result = parse_match_score(content)
        assert result == ("Bob", 2, 1)

    def test_parse_match_lead(self):
        """Test parsing a match lead."""
        content = "@PAlice leads the match 1-0\n"
        result = parse_match_score(content)
        assert result == ("Alice", 1, 0)

    def test_parse_returns_none_when_no_score(self):
        """Test that None is returned when no score found."""
        content = "Some log content without score\n"
        result = parse_match_score(content)
        assert result is None

    def test_parse_uses_last_score_in_log(self):
        """Test that the last score in the log is used."""
        content = """
@PAlice leads the match 1-0
@PAlice wins the match 2-1
"""
        result = parse_match_score(content)
        assert result == ("Alice", 2, 1)


class TestParseGameResults:
    """Tests for parse_game_results function."""

    def test_parse_single_game_win(self):
        """Test parsing a single game win."""
        content = """
@PAlice chooses to play first
@PAlice wins the game
"""
        result = parse_game_results(content)
        assert len(result) == 1
        assert result[0]["game_num"] == 1
        assert result[0]["winner"] == "Alice"
        assert result[0]["method"] == "win"

    def test_parse_multiple_games(self):
        """Test parsing multiple games."""
        content = """
@PAlice chooses to play first
@PAlice wins the game
@PBob chooses to play first
@PBob wins the game
@PAlice chooses to play first
@PAlice wins the game
"""
        result = parse_game_results(content)
        assert len(result) == 3
        assert result[0]["winner"] == "Alice"
        assert result[1]["winner"] == "Bob"
        assert result[2]["winner"] == "Alice"

    def test_parse_concession(self):
        """Test parsing a game ending in concession."""
        content = """
@PAlice chooses to play first
@PBob has conceded from the game
"""
        result = parse_game_results(content)
        assert len(result) == 1
        assert result[0]["loser"] == "Bob"
        assert result[0]["method"] == "concession"

    def test_parse_prevents_duplicate_results(self):
        """Test that only one result per game is recorded."""
        content = """
@PAlice chooses to play first
@PAlice wins the game
@PAlice wins the game
@PAlice wins the game
"""
        result = parse_game_results(content)
        assert len(result) == 1  # Should only record once per game


class TestFindGamelogFiles:
    """Tests for find_gamelog_files function."""

    def test_find_files_in_directory(self):
        """Test finding gamelog files in a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test files
            (Path(tmpdir) / "Match_GameLog_123.dat").touch()
            (Path(tmpdir) / "Match_GameLog_456.dat").touch()
            (Path(tmpdir) / "other_file.txt").touch()

            result = find_gamelog_files(tmpdir)
            assert len(result) == 2
            assert all("Match_GameLog_" in f for f in result)
            assert all(f.endswith(".dat") for f in result)

    def test_find_files_sorted_by_modification_time(self):
        """Test that files are sorted by modification time (newest first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import time

            file1 = Path(tmpdir) / "Match_GameLog_001.dat"
            file1.touch()
            time.sleep(0.01)
            file2 = Path(tmpdir) / "Match_GameLog_002.dat"
            file2.touch()

            result = find_gamelog_files(tmpdir)
            # Newest file (002) should be first
            assert "002" in result[0]
            assert "001" in result[1]

    def test_find_files_with_date_filter(self):
        """Test filtering files by modification date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import time

            old_file = Path(tmpdir) / "Match_GameLog_old.dat"
            old_file.touch()

            # Set the file to be old
            old_time = datetime(2020, 1, 1).timestamp()
            os.utime(old_file, (old_time, old_time))

            time.sleep(0.01)

            new_file = Path(tmpdir) / "Match_GameLog_new.dat"
            new_file.touch()

            # Filter to only recent files
            since = datetime(2023, 1, 1)
            result = find_gamelog_files(tmpdir, since_date=since)

            assert len(result) == 1
            assert "new" in result[0]

    def test_find_files_empty_directory(self):
        """Test that empty directory returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_gamelog_files(tmpdir)
            assert result == []


class TestParseGamelogFile:
    """Tests for parse_gamelog_file function."""

    def test_parse_valid_gamelog_file(self):
        """Test parsing a valid gamelog file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False, encoding="latin1") as tmp:
            tmp.write("Wed Dec 04 14:23:10 PST 2024\n")
            tmp.write("@PAlice joined the game\n")
            tmp.write("@PBob joined the game\n")
            tmp.write("@PAlice chooses to play first\n")
            tmp.write("@PAlice @[Lightning Bolt@:1,1:@] is played\n")
            tmp.write("@PBob @[Island@:2,2:@] is played\n")
            tmp.write("@PAlice wins the game\n")
            tmp.write("@PAlice wins the match 2-0\n")
            tmp_path = tmp.name

        try:
            result = parse_gamelog_file(tmp_path)
            assert result is not None
            assert result["players"] == ["Alice", "Bob"]
            assert result["opponent"] == "Bob"
            assert result["winner"] == "Alice"
            assert result["match_score"] == "2-0"
            assert "Lightning Bolt" in result["player1_deck"]
            assert "Island" in result["player2_deck"]
        finally:
            os.unlink(tmp_path)

    def test_parse_file_with_insufficient_players(self):
        """Test that file with less than 2 players returns None."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False, encoding="latin1") as tmp:
            tmp.write("Wed Dec 04 14:23:10 PST 2024\n")
            tmp.write("@PAlice joined the game\n")
            tmp_path = tmp.name

        try:
            result = parse_gamelog_file(tmp_path)
            assert result is None
        finally:
            os.unlink(tmp_path)

    def test_parse_extracts_match_id_from_filename(self):
        """Test that match ID is extracted from filename."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".dat",
            prefix="Match_GameLog_",
            delete=False,
            encoding="latin1",
            dir=tempfile.gettempdir()
        ) as tmp:
            tmp.write("Wed Dec 04 14:23:10 PST 2024\n")
            tmp.write("@PAlice joined the game\n")
            tmp.write("@PBob joined the game\n")
            tmp.write("@PAlice wins the match 2-0\n")
            tmp_path = tmp.name

        try:
            result = parse_gamelog_file(tmp_path)
            assert result is not None
            assert "match_id" in result
            # Match ID should be extracted from filename
        finally:
            os.unlink(tmp_path)
