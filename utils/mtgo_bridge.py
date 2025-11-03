"""Integration helpers for MTGOSDK via pythonnet."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Tuple

from loguru import logger

from utils import mtgosdk_runtime
from navigators import mtgo_decklists

_RUNTIME_WARNED = False
_LAST_RUNTIME_ERROR: str | None = None

CLI_CANDIDATES = [
    Path("dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/win-x64/publish/mtgo_bridge.exe"),
    Path("dotnet/MTGOBridge/bin/Debug/net9.0-windows7.0/win-x64/publish/mtgo_bridge.exe"),
    Path("dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/mtgo_bridge.exe"),
    Path("dotnet/MTGOBridge/bin/Debug/net9.0-windows7.0/mtgo_bridge.exe"),
    Path("dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/mtgo_bridge"),
    Path("dotnet/MTGOBridge/bin/Debug/net9.0-windows7.0/mtgo_bridge"),
    Path("dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/win-x64/publish/mtgo_bridge"),
    Path("dotnet/MTGOBridge/bin/Debug/net9.0-windows7.0/win-x64/publish/mtgo_bridge"),
]


def _ensure_runtime() -> bool:
    global _RUNTIME_WARNED, _LAST_RUNTIME_ERROR
    available = mtgosdk_runtime.initialize()
    if available:
        _RUNTIME_WARNED = False
        _LAST_RUNTIME_ERROR = None
        return True
    if not _RUNTIME_WARNED:
        error = mtgosdk_runtime.availability_error()
        if error:
            message = str(error)
            logger.error(f"MTGOSDK runtime unavailable: {message}")
            if "pythonnet" in message.lower():
                logger.error("Install pythonnet in your environment (pip install pythonnet) and ensure MTGOSDK DLLs are published.")
            _LAST_RUNTIME_ERROR = message
        else:
            logger.error("MTGOSDK runtime failed to initialize (unknown reason)")
            _LAST_RUNTIME_ERROR = "Unknown initialization failure"
        _RUNTIME_WARNED = True
    return False


def _resolve_cli_path(explicit: str | None = None) -> Path | None:
    if explicit:
        candidate = Path(explicit)
        return candidate if candidate.exists() else None

    env_path = os.environ.get("MTGO_BRIDGE_PATH")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate

    for candidate in CLI_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def get_game_state(self_name: str | None, bridge_path: str | None = None) -> dict[str, Any]:
    if not _ensure_runtime():
        return {}
    state = mtgosdk_runtime.get_game_state(self_name)
    return _normalize_state(state)


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


def fetch_collection() -> list[dict[str, Any]] | None:
    cards: dict[str, Any] 
    if _ensure_runtime():
        try:
            cards = mtgosdk_runtime.get_full_collection()
        except Exception as exc:  # pragma: no cover
            logger.warning(f"MTGOSDK runtime binder lookup failed: {exc}")
    return cards


def get_match_history(limit: int = 50, bridge_path: str | None = None) -> list[dict[str, Any]]:
    if not _ensure_runtime():
        history = []
    else:
        history = mtgosdk_runtime.get_match_history(limit=limit)
    if history:
        return history
    logger.info("MTGOSDK returned no match history; falling back to MTGO decklists scrape")
    return mtgo_decklists.fetch_recent_event_history(limit=limit)


def list_active_matches(bridge_path: str | None = None) -> list[dict[str, Any]]:
    if not _ensure_runtime():
        return []
    return mtgosdk_runtime.list_active_matches()


def ensure_runtime_ready() -> Tuple[bool, str | None]:
    ready = _ensure_runtime()
    return ready, None if ready else _LAST_RUNTIME_ERROR


def runtime_status() -> Tuple[bool, str | None]:
    ready = mtgosdk_runtime.is_initialized()
    return ready, None if ready else _LAST_RUNTIME_ERROR


def _normalize_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    game = state.get("game")
    if isinstance(game, dict):
        players = game.get("players")
        if isinstance(players, list) and "players" not in state:
            state["players"] = players
    return state


def get_full_collection() -> dict[str, Any] | None:
    try:
        return fetch_collection()
    except RuntimeError as exc:
        logger.warning(str(exc))
        return None
