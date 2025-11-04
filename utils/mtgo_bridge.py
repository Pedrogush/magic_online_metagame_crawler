"""Stub MTGOSDK bridge helpers maintained while the integration is rebuilt."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple

from loguru import logger

from . import mtgosdk_runtime

CLI_CANDIDATES: list[Path] = []


def _ensure_runtime() -> bool:
    return mtgosdk_runtime.initialize()


def _resolve_bridge_path(explicit: str | None = None) -> Path | None:
    if explicit:
        candidate = Path(explicit)
        if candidate.exists():
            return candidate
    for candidate in CLI_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def get_game_state(self_name: str | None, bridge_path: str | None = None) -> dict[str, Any]:
    if not _ensure_runtime():
        logger.debug("mtgosdk runtime stubbed; returning empty game state")
        return {}
    return mtgosdk_runtime.get_game_state(self_name)


def accept_pending_trades(bridge_path: str | None = None) -> dict[str, Any]:
    if not _ensure_runtime():
        return {"accepted": False, "reason": "runtime unavailable"}
    return mtgosdk_runtime.accept_pending_trades()


def list_decks(bridge_path: str | None = None) -> list[dict[str, Any]]:
    if not _ensure_runtime():
        return []
    return mtgosdk_runtime.list_decks_grouped()


def get_collection_snapshot(bridge_path: str | None = None) -> list[dict[str, Any]]:
    if not _ensure_runtime():
        return []
    return mtgosdk_runtime.get_collection_snapshot()


def fetch_collection() -> dict[str, Any]:
    if not _ensure_runtime():
        return {}
    return mtgosdk_runtime.get_full_collection()


def get_full_collection() -> dict[str, Any]:
    return fetch_collection()


def get_match_history(limit: int = 50, bridge_path: str | None = None) -> list[dict[str, Any]]:
    if not _ensure_runtime():
        return []
    return mtgosdk_runtime.get_match_history(limit=limit)


def list_active_matches(bridge_path: str | None = None) -> list[dict[str, Any]]:
    if not _ensure_runtime():
        return []
    return mtgosdk_runtime.list_active_matches()


def ensure_runtime_ready() -> Tuple[bool, str | None]:
    ready = _ensure_runtime()
    error: str | None = None
    if not ready:
        last_error = mtgosdk_runtime.availability_error()
        error = str(last_error) if last_error else "mtgosdk runtime unavailable"
    return ready, error


def runtime_status() -> Tuple[bool, str | None]:
    ready = mtgosdk_runtime.is_initialized()
    error: str | None = None
    if not ready:
        last_error = mtgosdk_runtime.availability_error()
        error = str(last_error) if last_error else "mtgosdk runtime unavailable"
    return ready, error
