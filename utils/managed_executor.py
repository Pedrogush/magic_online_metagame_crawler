from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from loguru import logger

__all__ = ["ManagedExecutor"]


class ManagedExecutor:
    """Manages background worker threads with lifecycle control and graceful shutdown."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()

    def submit(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Submit a task to run in a background thread.

        The task should periodically check self.is_stopped() and exit when True.
        """
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        with self._lock:
            self._threads.append(thread)
        thread.start()
        logger.debug(f"Started background thread: {func.__name__}")

    def is_stopped(self) -> bool:
        """Check if executor has been stopped."""
        return self._stop_event.is_set()

    def shutdown(self, timeout: float = 10.0) -> None:
        """Signal all threads to stop and wait for them to finish."""
        logger.info("Shutting down managed executor...")
        self._stop_event.set()

        with self._lock:
            threads = list(self._threads)

        for thread in threads:
            if thread.is_alive():
                logger.debug(f"Waiting for thread {thread.name} to finish...")
                thread.join(timeout=timeout)
                if thread.is_alive():
                    logger.warning(f"Thread {thread.name} did not finish within {timeout}s")

        logger.info("Managed executor shutdown complete")

    def __enter__(self) -> ManagedExecutor:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()
