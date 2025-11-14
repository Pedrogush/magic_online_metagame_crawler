from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from services.image_service import ImageService


class DeckSelectorImageManager:
    """Coordinate card image bulk data lifecycle for the deck selector."""

    def __init__(self, image_service: ImageService) -> None:
        self.image_service = image_service
        self._bulk_check_worker_active = False

    def ensure_data_ready(
        self,
        *,
        force_cached: bool,
        max_age_days: int,
        worker_factory: Callable[..., Any],
        set_status: Callable[[str], None],
        on_load_success: Callable[[dict[str, list[dict[str, Any]]], dict[str, Any]], None],
        on_load_error: Callable[[str], None],
        on_download_success: Callable[[str], None],
        on_download_error: Callable[[str], None],
        on_check_failed: Callable[[Exception], None],
    ) -> None:
        if self._bulk_check_worker_active:
            logger.debug("Bulk data check already running")
            return

        status_msg = (
            "Loading cached card image database…"
            if force_cached
            else "Checking card image database…"
        )
        set_status(status_msg)
        self._bulk_check_worker_active = True

        def worker():
            if force_cached:
                return False, "Cached-only mode enabled"
            return self.image_service.check_bulk_data_freshness(max_age_days=max_age_days)

        def on_success(result: tuple[bool, str]) -> None:
            self._bulk_check_worker_active = False
            needs_download, reason = result
            self._handle_check_result(
                needs_download=needs_download,
                reason=reason,
                force_cached=force_cached,
                set_status=set_status,
                on_load_success=on_load_success,
                on_load_error=on_load_error,
                on_download_success=on_download_success,
                on_download_error=on_download_error,
            )

        def on_error(exc: Exception) -> None:
            self._bulk_check_worker_active = False
            on_check_failed(exc)

        worker_factory(worker, on_success=on_success, on_error=on_error).start()

    def _handle_check_result(
        self,
        *,
        needs_download: bool,
        reason: str,
        force_cached: bool,
        set_status: Callable[[str], None],
        on_load_success: Callable[[dict[str, list[dict[str, Any]]], dict[str, Any]], None],
        on_load_error: Callable[[str], None],
        on_download_success: Callable[[str], None],
        on_download_error: Callable[[str], None],
    ) -> None:
        if force_cached or not needs_download:
            self._load_bulk_data(
                set_status=set_status,
                force=force_cached,
                on_success=on_load_success,
                on_error=on_load_error,
            )
            if force_cached:
                set_status("Using cached card image database")
            else:
                set_status("Card image database ready")
            return

        if not self.image_service.get_bulk_data():
            self._load_bulk_data(
                set_status=set_status,
                force=False,
                on_success=on_load_success,
                on_error=on_load_error,
            )

        logger.info(f"Bulk data needs update: {reason}")
        set_status("Downloading card image database...")
        self.image_service.download_bulk_metadata_async(
            on_success=on_download_success,
            on_error=on_download_error,
        )

    def _load_bulk_data(
        self,
        *,
        set_status: Callable[[str], None],
        force: bool,
        on_success: Callable[[dict[str, list[dict[str, Any]]], dict[str, Any]], None],
        on_error: Callable[[str], None],
    ) -> None:
        set_status("Preparing card printings cache…")
        started = self.image_service.load_printing_index_async(
            force=force,
            on_success=on_success,
            on_error=on_error,
        )
        if not started:
            set_status("Ready")

    def load_bulk_data_direct(
        self,
        *,
        force: bool,
        set_status: Callable[[str], None],
        on_load_success: Callable[[dict[str, list[dict[str, Any]]], dict[str, Any]], None],
        on_load_error: Callable[[str], None],
    ) -> None:
        """Expose bulk data loading for fallback flows."""
        self._load_bulk_data(
            set_status=set_status,
            force=force,
            on_success=on_load_success,
            on_error=on_load_error,
        )


__all__ = ["DeckSelectorImageManager"]
