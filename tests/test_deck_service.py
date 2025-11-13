from types import SimpleNamespace

import pytest

from services.deck_service import DeckService


@pytest.fixture
def deck_service():
    """DeckService that uses dummy repositories to avoid external dependencies."""
    return DeckService(deck_repository=SimpleNamespace(), metagame_repository=SimpleNamespace())


def test_deck_to_dictionary_preserves_fractional_counts(deck_service):
    deck_text = "2 Island\n" "0.5 Consider\n" "\n" "Sideboard\n" "1.25 Dismember\n"

    deck_dict = deck_service.deck_to_dictionary(deck_text)

    assert deck_dict["Island"] == 2.0
    assert deck_dict["Consider"] == pytest.approx(0.5)
    assert deck_dict["Sideboard Dismember"] == pytest.approx(1.25)


def test_deck_to_dictionary_handles_empty_lines(deck_service):
    deck_text = "1 Mountain\n\nSideboard\n2 Lightning Bolt\n\n"

    deck_dict = deck_service.deck_to_dictionary(deck_text)

    assert deck_dict["Mountain"] == 1.0
    assert deck_dict["Sideboard Lightning Bolt"] == 2.0
