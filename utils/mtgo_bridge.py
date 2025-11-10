"""Compatibility helpers bridging the CLI-based MTGO bridge into Python."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from loguru import logger

from . import mtgo_bridge_client


def _bridge_available(bridge_path: str | None = None) -> tuple[bool, str | None]:
    try:
        path = mtgo_bridge_client._require_bridge_path(bridge_path)  # type: ignore[attr-defined]
    except FileNotFoundError as exc:
        return False, str(exc)
    return True, str(path)


def ensure_runtime_ready(bridge_path: str | None = None) -> tuple[bool, str | None]:
    """Return True if the CLI bridge executable exists."""
    return runtime_status(bridge_path)


def runtime_status(bridge_path: str | None = None) -> tuple[bool, str | None]:
    ready, message = _bridge_available(bridge_path)
    return ready, None if ready else message


def get_collection_snapshot(
    bridge_path: str | None = None,
    timeout: float | None = None,
) -> Mapping[str, Any]:
    """Return the collection snapshot payload from the bridge."""
    payload = mtgo_bridge_client.run_bridge_command(
        "collection", bridge_path=bridge_path, timeout=timeout
    )
    collection = payload.get("collection") if isinstance(payload, dict) else None
    if not isinstance(collection, dict):
        logger.debug("Collection payload missing or malformed; returning empty dict")
        return {}
    return collection


def get_match_history(
    bridge_path: str | None = None,
    timeout: float | None = None,
) -> Mapping[str, Any]:
    """Return the match history payload from the bridge."""
    payload = mtgo_bridge_client.run_bridge_command(
        "history", bridge_path=bridge_path, timeout=timeout
    )
    history = payload.get("history") if isinstance(payload, dict) else None
    if not isinstance(history, dict):
        logger.debug("History payload missing or malformed; returning empty dict")
        return {}
    return history


def fetch_collection_async(
    *,
    bridge_path: str | None = None,
    context=None,
):
    return mtgo_bridge_client.fetch_collection_snapshot_async(
        bridge_path=bridge_path, context=context
    )


def fetch_history_async(
    *,
    bridge_path: str | None = None,
    context=None,
):
    return mtgo_bridge_client.fetch_match_history_async(bridge_path=bridge_path, context=context)


def start_watch(
    *,
    bridge_path: str | None = None,
    interval_ms: int = 500,
    context=None,
):
    return mtgo_bridge_client.start_watch(
        bridge_path=bridge_path, interval_ms=interval_ms, context=context
    )


def accept_pending_trades(*_args, **_kwargs) -> dict[str, Any]:
    """Legacy API placeholder—trade interactions are not supported via the CLI bridge."""
    return {"accepted": False, "reason": "not_supported"}


def list_decks(*_args, **_kwargs) -> list[dict[str, Any]]:
    """Legacy API placeholder—deck grouping is not exposed by the CLI bridge."""
    return []


def get_full_collection(*_args, **_kwargs) -> Mapping[str, Any]:
    """Backward compatible alias for ``get_collection_snapshot``."""
    return get_collection_snapshot(*_args, **_kwargs)
