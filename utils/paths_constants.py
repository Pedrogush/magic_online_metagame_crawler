"""Filesystem-related constants used across services."""

from pathlib import Path

MANA_RENDER_LOG = Path("cache") / "mana_render.log"

__all__ = ["MANA_RENDER_LOG"]
