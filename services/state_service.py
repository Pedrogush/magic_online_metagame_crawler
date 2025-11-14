from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

from utils import paths
from utils.deck import sanitize_zone_cards
from utils.game_constants import FORMAT_OPTIONS
from utils.service_config import DEFAULT_BULK_DATA_MAX_AGE_DAYS


@dataclass
class DeckSelectorState:
    """Mutable runtime state for the deck selector UI."""

    current_format: str = "Modern"
    left_mode: str = "research"
    force_cached_bulk_data: bool = False
    bulk_data_max_age_days: int = int(DEFAULT_BULK_DATA_MAX_AGE_DAYS)
    loading_archetypes: bool = False
    loading_decks: bool = False
    loading_daily_average: bool = False
    card_data_dialogs_disabled: bool = False


class StateService:
    """Loads and persists application state."""

    def __init__(self, settings_path: Path | None = None) -> None:
        self.settings_path = settings_path or paths.DECK_SELECTOR_SETTINGS_FILE
        self._deck_selector_state: DeckSelectorState | None = None

    def load(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        try:
            with self.settings_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
            logger.warning(f"Failed to load deck selector settings: {exc}")
            return {}

    def save(self, data: dict[str, Any]) -> None:
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with self.settings_path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:  # pragma: no cover - defensive logging
            logger.warning(f"Unable to persist deck selector settings: {exc}")

    @staticmethod
    def coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def clamp_bulk_cache_age(
        value: Any,
        *,
        default_days: int,
        min_days: int,
        max_days: int,
    ) -> int:
        try:
            days = int(float(value))
        except (TypeError, ValueError):
            days = default_days
        return max(min_days, min(days, max_days))

    @staticmethod
    def serialize_zone_cards(
        zone_cards: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        return {zone: sanitize_zone_cards(cards) for zone, cards in zone_cards.items()}

    @staticmethod
    def deserialize_zone_cards(value: Any) -> dict[str, list[dict[str, Any]]]:
        if not isinstance(value, dict):
            return {}
        restored: dict[str, list[dict[str, Any]]] = {}
        for zone, entries in value.items():
            if not isinstance(entries, list):
                continue
            sanitized = sanitize_zone_cards(entries)
            if sanitized:
                restored[zone] = sanitized
        return restored

    def build_deck_selector_state(
        self,
        settings: dict[str, Any],
        *,
        format_options: Iterable[str] | None = None,
        default_format: str = "Modern",
        default_left_mode: str = "research",
        default_bulk_days: int = int(DEFAULT_BULK_DATA_MAX_AGE_DAYS),
        min_bulk_days: int = 1,
        max_bulk_days: int = 365,
    ) -> DeckSelectorState:
        """Initialize deck selector runtime state using persisted preferences."""
        available_formats = set(format_options or FORMAT_OPTIONS)
        selected_format = settings.get("format", default_format)
        if selected_format not in available_formats:
            selected_format = default_format

        raw_force = settings.get("force_cached_bulk_data", False)
        force_cached = self.coerce_bool(raw_force)
        bulk_age = self.clamp_bulk_cache_age(
            settings.get("bulk_data_max_age_days", default_bulk_days),
            default_days=default_bulk_days,
            min_days=min_bulk_days,
            max_days=max_bulk_days,
        )
        left_mode = settings.get("left_mode")
        normalized_left_mode = "builder" if left_mode == "builder" else default_left_mode

        state = DeckSelectorState(
            current_format=selected_format,
            left_mode=normalized_left_mode,
            force_cached_bulk_data=force_cached,
            bulk_data_max_age_days=bulk_age,
        )
        self._deck_selector_state = state

        settings.setdefault("format", selected_format)
        settings.setdefault("left_mode", normalized_left_mode)
        settings.setdefault("force_cached_bulk_data", force_cached)
        settings.setdefault("bulk_data_max_age_days", bulk_age)
        return state

    def get_deck_selector_state(self) -> DeckSelectorState:
        if self._deck_selector_state is None:
            self._deck_selector_state = DeckSelectorState()
        return self._deck_selector_state


__all__ = ["DeckSelectorState", "StateService"]
