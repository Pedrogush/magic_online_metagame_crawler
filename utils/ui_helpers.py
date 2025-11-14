"""Utility helpers for wx UI interactions shared across widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import wx
from loguru import logger


def widget_exists(window: wx.Window | None) -> bool:
    """
    Check if a wx window reference is still valid and shown.

    Args:
        window: Window instance or None

    Returns:
        True if the window exists and is shown, else False
    """
    if window is None:
        return False
    try:
        return bool(window.IsShown())
    except wx.PyDeadObjectError:
        return False


def open_child_window(
    owner: Any,
    attr: str,
    window_class: type[wx.Window],
    title: str,
    on_close: Callable[[wx.CloseEvent, str], None],
    *args,
    **kwargs,
) -> wx.Window | None:
    """
    Create or raise a child window tracked on the parent frame.

    Args:
        owner: Parent frame that owns the window reference
        attr: Attribute name on the owner storing the window
        window_class: wx window class to instantiate
        title: Friendly title used in error dialogs
        on_close: Callback invoked when the window closes
        *args: Positional args passed to the window constructor
        **kwargs: Keyword args passed to the window constructor

    Returns:
        The opened window instance or None if creation failed
    """
    existing = getattr(owner, attr, None)
    if widget_exists(existing):
        existing.Raise()
        return existing
    try:
        window = window_class(owner, *args, **kwargs)
        window.Bind(wx.EVT_CLOSE, lambda evt: on_close(evt, attr))
        window.Show()
        setattr(owner, attr, window)
        return window
    except Exception as exc:  # pragma: no cover - UI side-effects
        logger.error(f"Failed to open {title.lower()}: {exc}")
        wx.MessageBox(
            f"Unable to open {title.lower()}:\n{exc}",
            title,
            wx.OK | wx.ICON_ERROR,
        )
        return None
