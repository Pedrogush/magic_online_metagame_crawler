"""
Match history aggregation service.

This module provides cached access to MTGO GameLog-derived match data
and exposes helper methods for computing win-rate statistics that can
be consumed by multiple UI widgets without re-parsing the logs.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from threading import Lock
from typing import Any, Callable

from loguru import logger

from utils.gamelog_parser import get_current_username, parse_all_gamelogs


class MatchHistoryService:
    """Service that loads GameLog entries and computes cached win-rate metrics."""

    def __init__(
        self,
        parser: Callable[..., list[dict[str, Any]]] | None = None,
        username_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self._parser = parser or parse_all_gamelogs
        self._username_provider = username_provider or get_current_username
        self._lock = Lock()
        self._matches: list[dict[str, Any]] = []
        self._stats_cache: dict[str, Any] | None = None
        self._last_refreshed: datetime | None = None
        self._username: str | None = None

    # ------------------------------------------------------------------ Public API ---------------------------------------------------------
    def refresh_matches(self, force: bool = False) -> list[dict[str, Any]]:
        """
        Load and cache match history.

        Args:
            force: When True, forces the underlying GameLogs to be re-parsed.

        Returns:
            List of parsed match dictionaries.
        """
        with self._lock:
            if force or not self._matches:
                matches = self._parser()
                self._matches = matches
                self._stats_cache = None
                self._last_refreshed = datetime.utcnow()
                self._username = self._resolve_username(matches)
        return self._matches

    def get_win_rate_stats(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Return aggregate win-rate statistics, optionally forcing a refresh.

        Args:
            force_refresh: Re-parse GameLogs before computing stats.

        Returns:
            Dictionary with overall and per-opponent win-rate data.
        """
        matches = self.refresh_matches(force=force_refresh or not self._matches)
        with self._lock:
            if self._stats_cache and not force_refresh:
                return self._stats_cache

            stats = self._calculate_stats(matches, self._username)
            stats["username"] = self._username
            stats["last_updated"] = self._last_refreshed
            self._stats_cache = stats
            return stats

    # ------------------------------------------------------------------ Internal helpers ---------------------------------------------------
    def _resolve_username(self, matches: list[dict[str, Any]]) -> str | None:
        try:
            username = self._username_provider()
        except Exception as exc:  # pragma: no cover - defensive guardrail
            logger.debug("Unable to resolve MTGO username via bridge: {}", exc)
            username = None

        if username:
            return username

        counts: dict[str, int] = defaultdict(int)
        for match in matches:
            players = match.get("players") or []
            if players:
                counts[players[0]] += 1

        return max(counts, key=counts.get) if counts else None

    def _calculate_stats(
        self, matches: list[dict[str, Any]], username: str | None
    ) -> dict[str, Any]:
        total_matches = 0
        wins = 0
        losses = 0
        games_won = 0
        games_lost = 0
        per_opponent: dict[str, dict[str, Any]] = {}

        for match in matches:
            normalized = self._normalize_match(match, username)
            if not normalized:
                continue

            total_matches += 1
            result = normalized["win"]
            if result is True:
                wins += 1
            elif result is False:
                losses += 1

            games_won += normalized["games_won"]
            games_lost += normalized["games_lost"]

            opponent = normalized["opponent"]
            if not opponent:
                continue

            key = opponent.lower()
            record = per_opponent.setdefault(
                key,
                {
                    "opponent": opponent,
                    "wins": 0,
                    "losses": 0,
                    "matches": 0,
                    "last_played": None,
                },
            )
            record["matches"] += 1
            if result is True:
                record["wins"] += 1
            elif result is False:
                record["losses"] += 1

            timestamp = normalized["timestamp"]
            if timestamp:
                last_played = record["last_played"]
                if last_played is None or timestamp > last_played:
                    record["last_played"] = timestamp

        win_rate = (wins / total_matches * 100) if total_matches else 0.0
        games_played = games_won + games_lost
        game_win_rate = (games_won / games_played * 100) if games_played else 0.0

        per_opponent_list = []
        for record in per_opponent.values():
            matches_played = record["matches"]
            opp_win_rate = (record["wins"] / matches_played * 100) if matches_played else 0.0
            per_opponent_list.append(
                {
                    "opponent": record["opponent"],
                    "wins": record["wins"],
                    "losses": record["losses"],
                    "matches": matches_played,
                    "win_rate": opp_win_rate,
                    "last_played": record["last_played"],
                }
            )

        per_opponent_list.sort(key=lambda item: (item["matches"], item["win_rate"]), reverse=True)

        return {
            "total_matches": total_matches,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "games_won": games_won,
            "games_lost": games_lost,
            "game_win_rate": game_win_rate,
            "per_opponent": per_opponent_list,
        }

    def _normalize_match(
        self, match: dict[str, Any], username: str | None
    ) -> dict[str, Any] | None:
        players = match.get("players") or []
        if len(players) < 2:
            return None

        player1 = players[0]
        player2 = players[1]

        score = match.get("match_score", "0-0")
        try:
            player1_score, player2_score = map(int, score.split("-"))
        except (ValueError, AttributeError):
            player1_score, player2_score = 0, 0

        our_name: str | None = None
        opp_name: str | None = None
        our_score = player1_score
        opp_score = player2_score

        if username:
            username_lower = username.lower()
            if player1 and player1.lower() == username_lower:
                our_name = player1
                opp_name = player2
                our_score = player1_score
                opp_score = player2_score
            elif player2 and player2.lower() == username_lower:
                our_name = player2
                opp_name = player1
                our_score = player2_score
                opp_score = player1_score

        if our_name is None:
            our_name = player1
            opp_name = player2
            our_score = player1_score
            opp_score = player2_score

        if not opp_name:
            return None

        winner = match.get("winner")
        if winner:
            win_flag: bool | None = winner == our_name
        elif our_score != opp_score:
            win_flag = our_score > opp_score
        else:
            win_flag = None

        timestamp = match.get("timestamp")
        if not isinstance(timestamp, datetime):
            timestamp = None

        return {
            "opponent": opp_name,
            "win": win_flag,
            "games_won": max(our_score, 0),
            "games_lost": max(opp_score, 0),
            "timestamp": timestamp,
        }


_default_match_history_service: MatchHistoryService | None = None


def get_match_history_service() -> MatchHistoryService:
    """Return a shared MatchHistoryService instance."""
    global _default_match_history_service
    if _default_match_history_service is None:
        _default_match_history_service = MatchHistoryService()
    return _default_match_history_service


def reset_match_history_service() -> None:
    """Reset the cached MatchHistoryService instance (used in tests)."""
    global _default_match_history_service
    _default_match_history_service = None


__all__ = [
    "MatchHistoryService",
    "get_match_history_service",
    "reset_match_history_service",
]
