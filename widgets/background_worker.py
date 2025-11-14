from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import wx
from loguru import logger

__all__ = ["BackgroundWorker"]


class BackgroundWorker:
    """Run blocking work in a thread and marshal callbacks onto the UI thread."""

    def __init__(
        self,
        func: Callable[..., Any],
        *args: Any,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._func = func
        self._args = args
        self._on_success = on_success
        self._on_error = on_error

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            result = self._func(*self._args)
        except Exception as exc:  # pragma: no cover - UI side effects
            logger.exception(f"Background task failed: {exc}")
            if self._on_error:
                wx.CallAfter(self._on_error, exc)
            return

        if self._on_success:
            wx.CallAfter(self._on_success, result)
