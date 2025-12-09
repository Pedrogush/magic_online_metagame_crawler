"""Helpers for centralized UI copy (tooltips, labels, hints)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Default locations for editable UI copy (dev tree first, then alongside executable).
DEFAULT_COPY_PATHS = [
    Path(__file__).resolve().parent.parent / "resources" / "ui_copy.json",
    Path(sys.argv[0]).resolve().parent / "resources" / "ui_copy.json",
]

# Built-in fallbacks so copy still appears if file is missing.
FALLBACK_COPY: dict[str, Any] = {
    "tooltips": {
        "guide": {
            "enable_double_entries": (
                "If unchecked, will overwrite existing entries for this archetype. "
                "If checked, will add new entry even if archetype already exists."
            ),
            "import": {
                "enable_double_entries": (
                    "If unchecked, will overwrite existing entries for matching archetypes. "
                    "If checked, will add entries even if archetypes already exist."
                )
            },
        },
        "sideboard_selector": {
            "set_zero": "Set to 0",
            "set_max": "Set to max ({max_qty})",
        },
    },
    "hints": {"guide": {"notes": "Strategy notes for this matchup"}},
    "labels": {"guide": {"enable_double_entries": "Enable double entries"}},
    "messages": {
        "guide": {
            "select_entry_edit": "Select an entry to edit.",
            "select_entry_remove": "Select an entry to remove.",
            "exclude_prompt": "Select archetypes to exclude from the printed guide.",
        }
    },
}

# Cache the loaded copy to avoid re-reading the file.
_copy_cache: dict[str, Any] | None = None


def _load_copy() -> dict[str, Any]:
    """Load UI copy from disk once, returning an empty dict if missing."""
    global _copy_cache
    if _copy_cache is not None:
        return _copy_cache

    for path in DEFAULT_COPY_PATHS:
        try:
            with open(path, encoding="utf-8") as fh:
                _copy_cache = json.load(fh)
                return _copy_cache
        except FileNotFoundError:
            continue
        except json.JSONDecodeError:
            continue

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

    # Try fallback table when the file is missing or malformed, or when we only hit the provided
    # default (to keep copy visible even if the resource file is absent at runtime).
    if not isinstance(value, str) or value == default:
        fallback: Any = FALLBACK_COPY
        for part in path.split("."):
            if isinstance(fallback, dict) and part in fallback:
                fallback = fallback[part]
            else:
                fallback = default
                break
        if isinstance(fallback, str):
            value = fallback
        elif not isinstance(value, str):
            value = default

    if fmt:
        try:
            return value.format(**fmt)
        except Exception:
            return value
    return value


__all__ = ["get_copy", "DEFAULT_COPY_PATHS", "FALLBACK_COPY"]
