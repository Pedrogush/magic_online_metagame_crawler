"""Background service to pre-fetch and cache MTGO decklist data for all formats."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from navigators import mtgo_decklists
from utils.constants import MTGO_DECK_CACHE_FILE


class CachePreloaderService:
    """
    Background service that proactively fetches MTGO decklist data for all formats.

    This service:
    - Runs in a low-priority background thread
    - Checks if we have recent data for each format
    - Fetches missing data gradually over time
    - Uses format-specific cache files to avoid race conditions
    - Periodically merges into the main cache
    """

    # Formats to pre-fetch
    FORMATS = ["Modern", "Legacy", "Standard", "Pioneer", "Pauper"]

    # How many days of data to keep cached
    CACHE_DAYS = 30

    # Delay between format fetches (seconds) - don't overwhelm the server
    FETCH_DELAY = 60

    # How often to merge format caches into main cache (seconds)
    MERGE_INTERVAL = 300  # 5 minutes

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background preloader service."""
        if self._running:
            logger.warning("Cache preloader is already running")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="CachePreloader",
            daemon=True  # Don't prevent app exit
        )
        self._thread.start()
        logger.info("Cache preloader service started")

    def stop(self) -> None:
        """Stop the background preloader service."""
        if not self._running:
            return

        logger.info("Stopping cache preloader service...")
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._running = False
        logger.info("Cache preloader service stopped")

    def is_running(self) -> bool:
        """Check if the service is currently running."""
        return self._running

    def _run_loop(self) -> None:
        """Main loop that runs in the background thread."""
        logger.info("Cache preloader loop started")

        try:
            while not self._stop_event.is_set():
                # Check each format and fetch if needed
                for fmt in self.FORMATS:
                    if self._stop_event.is_set():
                        break

                    try:
                        self._fetch_format_if_needed(fmt)
                    except Exception as exc:
                        logger.error(f"Error pre-fetching {fmt}: {exc}")

                    # Wait between formats to not overwhelm server
                    if not self._stop_event.wait(timeout=self.FETCH_DELAY):
                        continue
                    else:
                        break

                # After checking all formats, merge caches
                if not self._stop_event.is_set():
                    try:
                        self._merge_format_caches()
                    except Exception as exc:
                        logger.error(f"Error merging format caches: {exc}")

                # Wait before next cycle
                self._stop_event.wait(timeout=self.MERGE_INTERVAL)

        except Exception as exc:
            logger.error(f"Cache preloader loop crashed: {exc}")
        finally:
            logger.info("Cache preloader loop ended")

    def _fetch_format_if_needed(self, fmt: str) -> None:
        """
        Check if format data is stale and fetch if needed.

        Args:
            fmt: Format name (e.g., "Modern", "Legacy")
        """
        # Check if we need to fetch this format
        if not self._should_fetch_format(fmt):
            logger.debug(f"Format {fmt} cache is fresh, skipping")
            return

        logger.info(f"Pre-fetching data for {fmt}...")

        # Fetch events for the last CACHE_DAYS
        now = datetime.utcnow()
        cutoff = now - timedelta(days=self.CACHE_DAYS)

        # Collect months to fetch
        months_to_fetch: set[tuple[int, int]] = set()
        current = cutoff
        while current <= now:
            months_to_fetch.add((current.year, current.month))
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        # Fetch each month
        format_cache_path = self._get_format_cache_path(fmt)
        format_cache = self._load_format_cache(fmt)

        newly_fetched = 0
        for year, month in sorted(months_to_fetch):
            if self._stop_event.is_set():
                break

            try:
                # Fetch events with format filtering
                events = mtgo_decklists.fetch_recent_events_parallel(
                    year, month, max_events=50, mtg_format=fmt
                )

                # Add to format cache
                events_cache = format_cache.setdefault("events", {})
                for entry, payload in events:
                    url = entry.get("url")
                    if url and url not in events_cache:
                        events_cache[url] = payload
                        newly_fetched += 1

                logger.debug(f"Fetched {len(events)} events for {fmt} {year}-{month:02d}")

            except Exception as exc:
                logger.warning(f"Failed to fetch {fmt} {year}-{month:02d}: {exc}")

        # Save format cache
        if newly_fetched > 0:
            format_cache["last_updated"] = datetime.utcnow().isoformat()
            self._save_format_cache(fmt, format_cache)
            logger.info(f"Pre-fetched {newly_fetched} new events for {fmt}")

        # Also build archetype-level caches for this format
        # This ensures user gets instant results when clicking archetypes
        try:
            logger.debug(f"Building archetype cache for {fmt}...")
            archetypes = mtgo_decklists.get_archetypes(fmt, cache_only=False)
            if archetypes:
                logger.debug(f"Cached {len(archetypes)} archetypes for {fmt}")

                # Pre-cache decks for top 3 most popular archetypes
                # This makes the most common user actions instant
                for archetype in archetypes[:3]:
                    if self._stop_event.is_set():
                        break
                    try:
                        archetype_name = archetype.get("name", "")
                        if archetype_name:
                            logger.debug(f"Pre-caching decks for {archetype_name}...")
                            decks = mtgo_decklists.get_archetype_decks(
                                archetype_name, mtg_format=fmt, cache_only=False
                            )
                            if decks:
                                logger.debug(f"Cached {len(decks)} decks for {archetype_name}")
                    except Exception as exc:
                        logger.warning(f"Failed to pre-cache decks for archetype: {exc}")
        except Exception as exc:
            logger.warning(f"Failed to build archetype cache for {fmt}: {exc}")

    def _should_fetch_format(self, fmt: str) -> bool:
        """
        Check if format data needs to be fetched.

        Args:
            fmt: Format name

        Returns:
            True if data is stale or missing
        """
        format_cache = self._load_format_cache(fmt)

        # Check if we have any events
        events = format_cache.get("events", {})
        if not events:
            return True

        # Check last updated time
        last_updated_str = format_cache.get("last_updated")
        if not last_updated_str:
            return True

        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            # Refresh if older than 12 hours
            if datetime.utcnow() - last_updated > timedelta(hours=12):
                return True
        except (ValueError, AttributeError):
            return True

        return False

    def _get_format_cache_path(self, fmt: str) -> Path:
        """Get the cache file path for a specific format."""
        cache_dir = MTGO_DECK_CACHE_FILE.parent
        return cache_dir / f"mtgo_decks_{fmt.lower()}.json"

    def _load_format_cache(self, fmt: str) -> dict[str, Any]:
        """Load format-specific cache."""
        cache_path = self._get_format_cache_path(fmt)
        if not cache_path.exists():
            return {}

        try:
            with cache_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            logger.warning(f"Failed to load {fmt} cache: {exc}")
            return {}

    def _save_format_cache(self, fmt: str, cache: dict[str, Any]) -> None:
        """Save format-specific cache with Windows-safe file handling."""
        import platform
        import time
        import uuid

        cache_path = self._get_format_cache_path(fmt)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Use unique temp filename to avoid conflicts
            temp_path = cache_path.with_suffix(f".tmp.{uuid.uuid4().hex}")
            with temp_path.open("w", encoding="utf-8") as fh:
                json.dump(cache, fh, indent=2)

            # On Windows, delete target file first (with retry for file locking)
            if platform.system() == 'Windows' and cache_path.exists():
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        cache_path.unlink()
                        break
                    except OSError:
                        if attempt < max_retries - 1:
                            time.sleep(0.1 * (attempt + 1))

            # Atomic replace
            temp_path.replace(cache_path)

        except Exception as exc:
            logger.error(f"Failed to save {fmt} cache: {exc}")
            # Clean up temp file
            if 'temp_path' in locals() and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def _merge_format_caches(self) -> None:
        """Merge all format-specific caches into the main cache."""
        logger.debug("Merging format caches into main cache...")

        # Load main cache
        main_cache = mtgo_decklists._load_cache()
        main_events = main_cache.setdefault("events", {})

        merged_count = 0

        # Merge each format cache
        for fmt in self.FORMATS:
            format_cache = self._load_format_cache(fmt)
            format_events = format_cache.get("events", {})

            for url, payload in format_events.items():
                if url not in main_events:
                    main_events[url] = payload
                    merged_count += 1

        # Save merged cache if we added anything
        if merged_count > 0:
            mtgo_decklists._save_cache(main_cache)
            logger.info(f"Merged {merged_count} events into main cache")


# Global instance
_preloader_instance: CachePreloaderService | None = None


def get_cache_preloader() -> CachePreloaderService:
    """Get the singleton cache preloader service instance."""
    global _preloader_instance
    if _preloader_instance is None:
        _preloader_instance = CachePreloaderService()
    return _preloader_instance


__all__ = ["CachePreloaderService", "get_cache_preloader"]
