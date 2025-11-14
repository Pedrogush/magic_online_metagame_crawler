"""Tests for the match history aggregation service."""

from datetime import datetime, timedelta

import pytest

from services.match_history_service import MatchHistoryService


def _make_match(
    player_one: str,
    player_two: str,
    winner: str,
    score: str,
    timestamp: datetime,
) -> dict:
    return {
        "players": [player_one, player_two],
        "winner": winner,
        "match_score": score,
        "timestamp": timestamp,
    }


def test_aggregates_overall_and_per_opponent() -> None:
    """Service should return sane overall and per-opponent statistics."""

    base_time = datetime(2024, 1, 1, 12, 0, 0)
    matches = [
        _make_match("Alice", "Bob", "Alice", "2-0", base_time),
        _make_match("Alice", "Charlie", "Charlie", "1-2", base_time + timedelta(hours=2)),
        _make_match("Alice", "Bob", "Alice", "2-1", base_time + timedelta(days=1)),
    ]

    service = MatchHistoryService(parser=lambda: matches, username_provider=lambda: "Alice")

    stats = service.get_win_rate_stats()

    assert stats["total_matches"] == 3
    assert stats["wins"] == 2
    assert stats["losses"] == 1
    assert stats["win_rate"] == pytest.approx(66.666, rel=1e-3)

    per_opp = {entry["opponent"]: entry for entry in stats["per_opponent"]}
    assert per_opp["Bob"]["wins"] == 2
    assert per_opp["Bob"]["losses"] == 0
    assert per_opp["Bob"]["matches"] == 2
    assert per_opp["Charlie"]["wins"] == 0
    assert per_opp["Charlie"]["losses"] == 1
    assert per_opp["Charlie"]["win_rate"] == 0.0


def test_caches_until_force_refresh() -> None:
    """Parsing should only happen once unless force refresh is requested."""

    call_counter = {"count": 0}

    def parser() -> list[dict]:
        call_counter["count"] += 1
        return [
            _make_match(
                "Alice",
                "Bob",
                "Alice",
                "2-0",
                datetime(2024, 1, 1, 12, 0, 0),
            )
        ]

    service = MatchHistoryService(parser=parser, username_provider=lambda: "Alice")

    service.get_win_rate_stats()
    service.get_win_rate_stats()
    assert call_counter["count"] == 1

    service.get_win_rate_stats(force_refresh=True)
    assert call_counter["count"] == 2
