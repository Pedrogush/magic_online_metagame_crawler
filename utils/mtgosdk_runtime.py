"""Lightweight MTGOSDK runtime shim used during bridge refactors."""

from __future__ import annotations

from typing import Any

_LAST_ERROR: Exception | None = RuntimeError("MTGOSDK runtime stubbed out")


def is_available() -> bool:
    return False


def is_initialized() -> bool:
    return False


def availability_error() -> Exception | None:
    return _LAST_ERROR


def initialize(force: bool = False) -> bool:
    return False


def get_game_state(self_name: str | None = None) -> dict[str, Any]:
    return {}


def accept_pending_trades() -> dict[str, Any]:
    return {"accepted": False, "reason": "mtgosdk runtime unavailable"}


def list_decks_grouped() -> list[dict[str, Any]]:
    return []


def get_collection_snapshot() -> list[dict[str, Any]]:
    return []


def get_full_collection() -> dict[str, Any]:
    return {}


def get_match_history(limit: int = 50) -> list[dict[str, Any]]:
    return []


def list_active_matches() -> list[dict[str, Any]]:
    return []


def get_available_binder_names() -> list[str]:
    return []
