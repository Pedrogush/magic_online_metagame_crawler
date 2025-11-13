"""
Image Service - Business logic for card image and bulk data management.

This module handles:
- Bulk data freshness checking
- Bulk metadata downloading
- Printing index loading
- Image cache management
"""

import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from loguru import logger

from utils.card_images import (
    BULK_DATA_CACHE,
    BulkImageDownloader,
    ensure_printing_index_cache,
    get_cache,
)


class ImageService:
    """Service for managing card image bulk data and printing indices."""

    def __init__(self):
        """Initialize the image service."""
        self.image_cache = get_cache()
        self.image_downloader: BulkImageDownloader | None = None
        self.bulk_data_by_name: dict[str, list[dict[str, Any]]] | None = None
        self.printing_index_loading: bool = False

    # ============= Bulk Data Management =============

    def check_bulk_data_freshness(self) -> tuple[bool, str]:
        """
        Check if bulk data needs to be downloaded.

        Returns:
            Tuple of (needs_download: bool, reason: str)
        """
        if self.image_downloader is None:
            self.image_downloader = BulkImageDownloader(self.image_cache)

        if not BULK_DATA_CACHE.exists():
            return True, "Bulk data cache not found"

        # Try vendor metadata check first
        try:
            needs_download, metadata = self.image_downloader.is_bulk_data_outdated()
            if not needs_download:
                reason = f"Bulk data current (updated_at={metadata.get('updated_at')})"
                logger.info(reason)
                return False, reason

            reason = f"Bulk data stale (updated_at={metadata.get('updated_at')})"
            logger.info(reason)
            return True, reason

        except Exception as exc:
            logger.warning(f"Failed to check bulk data metadata: {exc}")

            # Fallback to age-based check
            try:
                age_seconds = datetime.now().timestamp() - BULK_DATA_CACHE.stat().st_mtime
                if age_seconds < 86400:  # Less than 24 hours
                    reason = f"Bulk data cache is recent ({age_seconds/3600:.1f}h old)"
                    logger.info(reason)
                    return False, reason

                reason = f"Bulk data cache is stale ({age_seconds/3600:.1f}h old)"
                logger.info(reason)
                return True, reason

            except Exception as exc2:
                logger.warning(f"Failed to check bulk data age: {exc2}")
                return False, f"Error checking cache: {exc2}"

    def download_bulk_metadata_async(
        self,
        on_success: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        """
        Download bulk metadata in a background thread.

        Args:
            on_success: Callback for successful download (receives success message)
            on_error: Callback for failed download (receives error message)
        """
        if self.image_downloader is None:
            self.image_downloader = BulkImageDownloader(self.image_cache)

        def worker():
            try:
                success, msg = self.image_downloader.download_bulk_metadata(force=True)
                if success:
                    on_success(msg)
                else:
                    on_error(msg)
            except Exception as exc:
                logger.exception("Failed to download bulk data")
                on_error(str(exc))

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
        if self.printing_index_loading and not force:
            logger.debug("Printing index already loading")
            return False

        if self.bulk_data_by_name and not force:
            logger.debug("Printing index already loaded")
            return False

        self.printing_index_loading = True

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
                on_success(data, stats)
            except Exception as exc:
                logger.exception("Failed to prepare card printings index")
                on_error(str(exc))

        threading.Thread(target=worker, daemon=True).start()
        return True

    def set_bulk_data(self, bulk_data: dict[str, list[dict[str, Any]]]) -> None:
        """Set the bulk data reference."""
        self.bulk_data_by_name = bulk_data

    def clear_printing_index_loading(self) -> None:
        """Clear the printing index loading flag."""
        self.printing_index_loading = False

    def get_bulk_data(self) -> dict[str, list[dict[str, Any]]] | None:
        """Get the current bulk data."""
        return self.bulk_data_by_name

    def is_loading(self) -> bool:
        """Check if printing index is currently loading."""
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
