from utils.deck import analyze_deck, deck_to_dictionary

SAMPLE_DECK = """4 Ragavan, Nimble Pilferer
2 Blood Moon
1 Otawara, Soaring City

2 Sideboard Card
3 Force of Vigor
"""


def test_deck_to_dictionary_parses_main_and_side():
    parsed = deck_to_dictionary(SAMPLE_DECK)
    assert parsed["Ragavan, Nimble Pilferer"] == 4
    assert parsed["Blood Moon"] == 2
    assert parsed["Otawara, Soaring City"] == 1
    assert parsed["Sideboard Sideboard Card"] == 2
    assert parsed["Sideboard Force of Vigor"] == 3


def test_analyze_deck_counts_cards_correctly():
    summary = analyze_deck(SAMPLE_DECK)
    assert summary["mainboard_count"] == 7
    assert summary["sideboard_count"] == 5
    assert summary["total_cards"] == 12
    assert summary["unique_mainboard"] == 3
    assert summary["unique_sideboard"] == 2


def test_analyze_deck_sums_land_counts():
    """Verify that estimated_lands sums card counts, not just unique names."""
    deck_with_lands = """4 Mountain
3 Island
2 Swamp
1 Forest
4 Lightning Bolt
2 Counterspell

3 Duress
"""
    summary = analyze_deck(deck_with_lands)
    # Should sum 4+3+2+1 = 10 lands, not count 4 unique land names
    assert summary["estimated_lands"] == 10
    assert summary["mainboard_count"] == 16
    assert summary["unique_mainboard"] == 6


def test_analyze_deck_detects_land_keywords():
    """Verify that lands are detected by various keywords."""
    deck_with_various_lands = """2 Hallowed Fountain
3 Breeding Pool
1 Urza's Saga
4 Misty Rainforest
2 Flooded Strand
1 Scalding Tarn
2 Path to Exile
"""
    summary = analyze_deck(deck_with_various_lands)
    # Lands with "land" in their name should be counted
    # (Misty Rainforest, Flooded Strand, Scalding Tarn all contain "land")
    # 4 + 2 + 1 = 7 lands
    assert summary["estimated_lands"] == 7
    assert summary["mainboard_count"] == 15
    assert summary["unique_mainboard"] == 7


def test_analyze_deck_no_lands():
    """Verify that decks without lands report 0 estimated_lands."""
    deck_without_lands = """4 Lightning Bolt
4 Counterspell
4 Opt

3 Duress
"""
    summary = analyze_deck(deck_without_lands)
    assert summary["estimated_lands"] == 0
    assert summary["mainboard_count"] == 12
