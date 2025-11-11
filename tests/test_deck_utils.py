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
