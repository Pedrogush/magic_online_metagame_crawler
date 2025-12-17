"""
Image Service - Business logic for card image and bulk data management.

This module handles:
- Bulk data existence checking
- Bulk metadata downloading
- Printing index loading
- Image cache management
"""

import threading
from collections.abc import Callable
from typing import Any

from loguru import logger

from utils.card_images import (
    BULK_DATA_CACHE,
    BulkImageDownloader,
    ensure_printing_index_cache,
    get_cache,
)

DOWNLOAD_IN_PROGRESS_MSG = "Bulk data download already in progress"


class ImageService:
    """Service for managing card image bulk data and printing indices."""

    def __init__(self):
        """Initialize the image service."""
        self.image_cache = get_cache()
        self.image_downloader: BulkImageDownloader | None = None
        self.bulk_data_by_name: dict[str, list[dict[str, Any]]] | None = None
        self.printing_index_loading: bool = False
        self.bulk_download_in_progress: bool = False
        self._download_lock = threading.Lock()
        self._load_lock = threading.Lock()

    # ============= Bulk Data Management =============

    def check_bulk_data_exists(self) -> tuple[bool, str]:
        """
        Check if bulk data exists.

        Returns:
            Tuple of (exists: bool, reason: str)
        """
        if not BULK_DATA_CACHE.exists():
            return False, "Bulk data cache not found"

        return True, "Bulk data cache exists"

    def download_bulk_metadata_async(
        self,
        on_success: Callable[[str], None],
        on_error: Callable[[str], None],
        force: bool = False,
    ) -> None:
        """
        Download bulk metadata in a background thread.

        Args:
            on_success: Callback for successful download (receives success message)
            on_error: Callback for failed download (receives error message)
            force: Force download even if vendor metadata matches cache
        """
        if self.image_downloader is None:
            self.image_downloader = BulkImageDownloader(self.image_cache)

        def worker():
            with self._download_lock:
                if self.bulk_download_in_progress:
                    logger.info("{}; skipping new request", DOWNLOAD_IN_PROGRESS_MSG)
                    on_error(DOWNLOAD_IN_PROGRESS_MSG)
                    return
                self.bulk_download_in_progress = True

            logger.info("Starting bulk data download (force={})", force)
            try:
                success, msg = self.image_downloader.download_bulk_metadata(force=force)
                if success:
                    on_success(msg)
                else:
                    on_error(msg)
            except Exception as exc:
                logger.exception("Failed to download bulk data")
                on_error(str(exc))
            finally:
                with self._download_lock:
                    self.bulk_download_in_progress = False
                logger.info("Finished bulk data download")

        threading.Thread(target=worker, daemon=True).start()

    # ============= Printing Index Management =============

    def load_printing_index_async(
        self,
        force: bool,
        on_success: Callable[[dict[str, list[dict[str, Any]]], dict[str, Any]], None],
        on_error: Callable[[str], None],
    ) -> bool:
        """
        Load printing index in a background thread.

        Args:
            force: Force reload even if already loading/loaded
            on_success: Callback for successful load (receives bulk_data_by_name, stats)
            on_error: Callback for failed load (receives error message)

        Returns:
            True if load was started, False if skipped
        """
        with self._load_lock:
            if self.printing_index_loading and not force:
                logger.debug("Printing index already loading")
                return False

            if self.bulk_data_by_name and not force:
                logger.debug("Printing index already loaded")
                return False

            self.printing_index_loading = True

        logger.info("Starting printing index load (force={})", force)

        def worker():
            try:
                payload = ensure_printing_index_cache(force=force)
                data = payload.get("data", {})
                stats = {
                    "unique_names": payload.get("unique_names", len(data)),
                    "total_printings": payload.get(
                        "total_printings", sum(len(v) for v in data.values())
                    ),
                }
                with self._load_lock:
                    self.bulk_data_by_name = data
                on_success(data, stats)
            except Exception as exc:
                logger.exception("Failed to prepare card printings index")
                on_error(str(exc))
            finally:
                with self._load_lock:
                    self.printing_index_loading = False
                logger.info("Finished printing index load")

        threading.Thread(target=worker, daemon=True).start()
        return True

    def set_bulk_data(self, bulk_data: dict[str, list[dict[str, Any]]]) -> None:
        """Set the bulk data reference."""
        with self._load_lock:
            self.bulk_data_by_name = bulk_data

    def clear_printing_index_loading(self) -> None:
        """Clear the printing index loading flag."""
        with self._load_lock:
            self.printing_index_loading = False

    def get_bulk_data(self) -> dict[str, list[dict[str, Any]]] | None:
        """Get the current bulk data."""
        with self._load_lock:
            return self.bulk_data_by_name

    def is_loading(self) -> bool:
        """Check if printing index is currently loading."""
        with self._load_lock:
            return self.printing_index_loading


# Global instance for backward compatibility
_default_service = None


def get_image_service() -> ImageService:
    """Get the default image service instance."""
    global _default_service
    if _default_service is None:
        _default_service = ImageService()
    return _default_service


def reset_image_service() -> None:
    """
    Reset the global image service instance.

    This is primarily useful for testing to ensure test isolation
    and prevent state leakage between tests.
    """
    global _default_service
    _default_service = None
