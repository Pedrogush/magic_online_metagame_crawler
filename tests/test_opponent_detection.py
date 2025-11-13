from collections.abc import Iterable

import pytest

from utils.find_opponent_names import find_opponent_names


@pytest.mark.parametrize(
    "titles, expected",
    [
        (
            [
                "MTGO — Player Bootcamp vs. Champion",
                "Other window",
                "vs. SecondPlayer",
                "Not a match",
            ],
            ["Champion", "SecondPlayer"],
        ),
        (
            ["Waiting room vs. ThirdPlayer", "vs. FourthPlayer vs. FifthPlayer"],
            ["ThirdPlayer", "FifthPlayer"],
        ),
    ],
)
def test_find_opponent_names_detects_windows(
    monkeypatch: pytest.MonkeyPatch, titles: Iterable[str], expected: list[str]
) -> None:
    """Verify we capture opponent names from window titles containing vs."""
    monkeypatch.setattr(
        "utils.find_opponent_names.pygetwindow.getAllTitles",
        lambda: list(titles),
    )
    assert find_opponent_names() == expected


def test_find_opponent_names_ignores_non_match_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure titles without the vs. marker are skipped."""
    monkeypatch.setattr(
        "utils.find_opponent_names.pygetwindow.getAllTitles",
        lambda: ["MTGO Lobby", "Deck building", ""],
    )
    assert find_opponent_names() == []
