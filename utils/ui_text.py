"""Helpers for centralized UI copy (tooltips, labels, hints)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Default location for editable UI copy.
DEFAULT_COPY_PATH = Path(__file__).resolve().parent.parent / "resources" / "ui_copy.json"

# Cache the loaded copy to avoid re-reading the file.
_copy_cache: dict[str, Any] | None = None


def _load_copy() -> dict[str, Any]:
    """Load UI copy from disk once, returning an empty dict if missing."""
    global _copy_cache
    if _copy_cache is not None:
        return _copy_cache

    try:
        with open(DEFAULT_COPY_PATH, encoding="utf-8") as fh:
            _copy_cache = json.load(fh)
    except FileNotFoundError:
        _copy_cache = {}
    return _copy_cache


def get_copy(path: str, default: str = "", **fmt: Any) -> str:
    """
    Retrieve a copy string by dotted path with an optional default and formatting.

    Example:
        get_copy("tooltips.sideboard_selector.set_max", "Set to max ({max_qty})", max_qty=4)
    """
    data = _load_copy()
    value: Any = data
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            value = default
            break

    if not isinstance(value, str):
        value = default

    if fmt:
        try:
            return value.format(**fmt)
        except Exception:
            return value
    return value


__all__ = ["get_copy", "DEFAULT_COPY_PATH"]
