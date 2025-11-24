"""
Deck Selector Controller - Application logic for the deck selector window.

This controller separates business logic and state management from UI presentation.
It coordinates between services, repositories, and provides a clean interface
for the UI layer to interact with application logic.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from navigators.mtggoldfish import download_deck, get_archetype_decks, get_archetypes
from repositories.card_repository import get_card_repository
from repositories.deck_repository import get_deck_repository
from repositories.metagame_repository import get_metagame_repository
from services.collection_service import get_collection_service
from services.deck_service import get_deck_service
from services.image_service import get_image_service
from services.search_service import get_search_service
from services.store_service import get_store_service
from utils.card_data import CardDataManager
from utils.deck import read_curr_deck_file
from utils.paths import CACHE_DIR
from utils.service_config import COLLECTION_CACHE_MAX_AGE_SECONDS

NOTES_STORE = CACHE_DIR / "deck_notes.json"
OUTBOARD_STORE = CACHE_DIR / "deck_outboard.json"
GUIDE_STORE = CACHE_DIR / "deck_sbguides.json"


class BackgroundWorker:
    """Helper for dispatching background work and returning results via callbacks."""

    def __init__(
        self,
        func: Callable,
        *args,
        on_success: Callable | None = None,
        on_error: Callable | None = None,
    ) -> None:
        self.func = func
        self.args = args
        self.on_success = on_success
        self.on_error = on_error

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            result = self.func(*self.args)
        except Exception as exc:
            logger.exception(f"Background task failed: {exc}")
            if self.on_error:
                self.on_error(exc)
            return
        if self.on_success:
            self.on_success(result)


class DeckSelectorController:
    """
    Application controller for the deck selector window.

    This class manages application state, coordinates between services and repositories,
    and provides business logic operations. It is UI-agnostic and communicates with
    the presentation layer via callbacks.
    """

    def __init__(self):
        """Initialize the controller with services, repositories, and initial state."""
        # Services and repositories
        self.deck_repo = get_deck_repository()
        self.metagame_repo = get_metagame_repository()
        self.card_repo = get_card_repository()
        self.deck_service = get_deck_service()
        self.search_service = get_search_service()
        self.collection_service = get_collection_service()
        self.image_service = get_image_service()
        self.store_service = get_store_service()

        # Application state
        self.current_format = "Modern"
        self.archetypes: list[dict[str, Any]] = []
        self.filtered_archetypes: list[dict[str, Any]] = []
        self.zone_cards: dict[str, list[dict[str, Any]]] = {"main": [], "side": [], "out": []}
        self.sideboard_guide_entries: list[dict[str, str]] = []
        self.sideboard_exclusions: list[str] = []

        # Thread-safe loading state flags
        self._loading_lock = threading.Lock()
        self.loading_archetypes = False
        self.loading_decks = False
        self.loading_daily_average = False

        # Load stores
        self.notes_store_path = NOTES_STORE
        self.outboard_store_path = OUTBOARD_STORE
        self.guide_store_path = GUIDE_STORE
        self.deck_notes_store = self.store_service.load_store(self.notes_store_path)
        self.outboard_store = self.store_service.load_store(self.outboard_store_path)
        self.guide_store = self.store_service.load_store(self.guide_store_path)

        self._bulk_check_worker_active = False

    # ============= Card Data Management =============

    def ensure_card_data_loaded(
        self,
        on_success: Callable[[CardDataManager], None],
        on_error: Callable[[Exception], None],
        on_status: Callable[[str], None],
    ) -> None:
        """
        Ensure card data is loaded in background if not already loading/loaded.

        Args:
            on_success: Callback when card data is loaded successfully (receives CardDataManager)
            on_error: Callback when loading fails (receives Exception)
            on_status: Callback for status updates (receives status message string)
        """
        if self.card_repo.get_card_manager() or self.card_repo.is_card_data_loading():
            return

        self.card_repo.set_card_data_loading(True)
        on_status("Loading card database...")

        def worker():
            return self.card_repo.ensure_card_data_loaded()

        def success_handler(manager: CardDataManager):
            self.card_repo.set_card_manager(manager)
            self.card_repo.set_card_data_loading(False)
            self.card_repo.set_card_data_ready(True)
            on_status("Card database loaded")
            on_success(manager)

        def error_handler(error: Exception):
            self.card_repo.set_card_data_loading(False)
            logger.error(f"Failed to load card data: {error}")
            on_status(f"Card database load failed: {error}")
            on_error(error)

        BackgroundWorker(worker, on_success=success_handler, on_error=error_handler).start()

    # ============= Archetype Management =============

    def fetch_archetypes(
        self,
        on_success: Callable[[list[dict[str, Any]]], None],
        on_error: Callable[[Exception], None],
        on_status: Callable[[str], None],
        force: bool = False,
    ) -> None:
        """
        Fetch archetypes for the current format.

        Args:
            on_success: Callback when archetypes are loaded (receives list of archetypes)
            on_error: Callback when loading fails (receives Exception)
            on_status: Callback for status updates (receives status message string)
            force: If True, bypass cache and fetch fresh data
        """
        with self._loading_lock:
            if self.loading_archetypes:
                return
            self.loading_archetypes = True

        on_status(f"Loading archetypes for {self.current_format}…")

        def loader(fmt: str):
            return get_archetypes(fmt.lower(), allow_stale=not force)

        def success_handler(archetypes: list[dict[str, Any]]):
            with self._loading_lock:
                self.loading_archetypes = False
            self.archetypes = archetypes
            self.filtered_archetypes = archetypes
            on_success(archetypes)

        def error_handler(error: Exception):
            with self._loading_lock:
                self.loading_archetypes = False
            logger.error(f"Failed to fetch archetypes: {error}")
            on_error(error)

        BackgroundWorker(
            loader,
            self.current_format,
            on_success=success_handler,
            on_error=error_handler,
        ).start()

    def load_decks_for_archetype(
        self,
        archetype: dict[str, Any],
        on_success: Callable[[str, list[dict[str, Any]]], None],
        on_error: Callable[[Exception], None],
        on_status: Callable[[str], None],
    ) -> None:
        """
        Load decks for a specific archetype.

        Args:
            archetype: Archetype data dictionary
            on_success: Callback when decks are loaded (receives archetype name and deck list)
            on_error: Callback when loading fails (receives Exception)
            on_status: Callback for status updates (receives status message string)
        """
        with self._loading_lock:
            if self.loading_decks:
                return
            self.loading_decks = True

        name = archetype.get("name", "Unknown")
        href = archetype.get("href")
        on_status(f"Loading decks for {name}…")

        def loader(identifier: str):
            return get_archetype_decks(identifier)

        def success_handler(decks: list[dict[str, Any]]):
            with self._loading_lock:
                self.loading_decks = False
            self.deck_repo.set_decks_list(decks)
            on_success(name, decks)

        def error_handler(error: Exception):
            with self._loading_lock:
                self.loading_decks = False
            logger.error(f"Failed to load decks: {error}")
            on_error(error)

        BackgroundWorker(
            loader,
            href,
            on_success=success_handler,
            on_error=error_handler,
        ).start()

    # ============= Deck Management =============

    def download_and_display_deck(
        self,
        deck: dict[str, Any],
        on_success: Callable[[str], None],
        on_error: Callable[[Exception], None],
        on_status: Callable[[str], None],
    ) -> None:
        """
        Download a deck from MTGGoldfish and prepare it for display.

        Args:
            deck: Deck data dictionary with 'number' key
            on_success: Callback when deck is downloaded (receives deck text)
            on_error: Callback when download fails (receives Exception)
            on_status: Callback for status updates (receives status message string)
        """
        deck_number = deck.get("number")
        if not deck_number:
            on_error(ValueError("Deck identifier missing"))
            return

        on_status("Downloading deck…")

        def worker(number: str):
            download_deck(number)
            return read_curr_deck_file()

        BackgroundWorker(worker, deck_number, on_success=on_success, on_error=on_error).start()

    def build_daily_average_deck(
        self,
        on_success: Callable[[dict[str, float], int], None],
        on_error: Callable[[Exception], None],
        on_status: Callable[[str], None],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> tuple[bool, str]:
        """
        Build a daily average deck from today's decks in the current archetype.

        Args:
            on_success: Callback when average is built (receives buffer dict and deck count)
            on_error: Callback when building fails (receives Exception)
            on_status: Callback for status updates (receives status message string)
            on_progress: Optional callback for progress updates (receives current, total)

        Returns:
            Tuple of (can_proceed, message) - False with message if no decks found
        """
        today = time.strftime("%Y-%m-%d").lower()
        todays_decks = [
            deck
            for deck in self.deck_repo.get_decks_list()
            if today in deck.get("date", "").lower()
        ]

        if not todays_decks:
            return False, "No decks from today found for this archetype."

        with self._loading_lock:
            self.loading_daily_average = True

        on_status("Building daily average deck…")

        def worker(rows: list[dict[str, Any]]):
            def progress_callback(index: int, total: int) -> None:
                if on_progress:
                    on_progress(index, total)

            return self.deck_repo.build_daily_average_deck(
                rows,
                download_deck,
                read_curr_deck_file,
                self.deck_service.add_deck_to_buffer,
                progress_callback=progress_callback,
            )

        def success_handler(buffer: dict[str, float]):
            with self._loading_lock:
                self.loading_daily_average = False
            on_success(buffer, len(todays_decks))

        def error_handler(error: Exception):
            with self._loading_lock:
                self.loading_daily_average = False
            logger.error(f"Daily average error: {error}")
            on_error(error)

        BackgroundWorker(
            worker,
            todays_decks,
            on_success=success_handler,
            on_error=error_handler,
        ).start()

        return True, f"Processing {len(todays_decks)} decks"

    # ============= Collection Management =============

    def load_collection_from_cache(self, directory: Path) -> tuple[bool, dict[str, Any] | None]:
        """
        Load collection from cached file without calling MTGO Bridge.

        Args:
            directory: Directory to look for collection cache

        Returns:
            Tuple of (success, info_dict or None)
            info_dict contains: filepath, card_count, age_hours
        """
        try:
            info = self.collection_service.load_from_cached_file(directory)
            return True, info
        except (FileNotFoundError, ValueError) as exc:
            logger.debug(f"Could not load collection from cache: {exc}")
            return False, None

    def refresh_collection_from_bridge(
        self,
        directory: Path,
        on_success: Callable[[Path, dict], None],
        on_error: Callable[[str], None],
        on_status: Callable[[str], None],
        force: bool = False,
    ) -> None:
        """
        Fetch collection from MTGO Bridge and export to JSON.

        Args:
            directory: Directory to save collection file
            on_success: Callback when collection is fetched (receives filepath and cards dict)
            on_error: Callback when fetch fails (receives error message)
            on_status: Callback for status updates (receives status message string)
            force: If True, force refresh even if cache is fresh
        """
        on_status("Fetching collection from MTGO...")
        logger.info("Fetching collection from MTGO Bridge")

        self.collection_service.refresh_from_bridge_async(
            directory=directory,
            force=force,
            on_success=on_success,
            on_error=on_error,
            cache_max_age_seconds=COLLECTION_CACHE_MAX_AGE_SECONDS,
        )

    # ============= Bulk Data Management =============

    def check_and_download_bulk_data(
        self,
        max_age_days: int,
        force_cached: bool,
        on_download_needed: Callable[[str], None],
        on_download_complete: Callable[[str], None],
        on_download_failed: Callable[[str], None],
        on_status: Callable[[str], None],
    ) -> None:
        """
        Check bulk data freshness and download if needed.

        Args:
            max_age_days: Maximum age in days before data is considered stale
            force_cached: If True, skip freshness check and use cached data only
            on_download_needed: Callback when download is needed (receives reason)
            on_download_complete: Callback when download completes (receives message)
            on_download_failed: Callback when download fails (receives message)
            on_status: Callback for status updates (receives status message string)
        """
        if self._bulk_check_worker_active:
            logger.debug("Bulk data check already running")
            return

        status_msg = (
            "Loading cached card image database…"
            if force_cached
            else "Checking card image database…"
        )
        on_status(status_msg)
        self._bulk_check_worker_active = True

        def worker():
            if force_cached:
                return False, "Cached-only mode enabled"
            return self.image_service.check_bulk_data_freshness(max_age_days=max_age_days)

        def success_handler(result: tuple[bool, str]):
            self._bulk_check_worker_active = False
            needs_download, reason = result

            if force_cached or not needs_download:
                self._load_bulk_data_into_memory(on_status)
                if force_cached:
                    on_status("Using cached card image database")
                else:
                    on_status("Card image database ready")
                return

            # Data is stale - load cached while downloading fresh
            if not self.image_service.get_bulk_data():
                self._load_bulk_data_into_memory(on_status)

            logger.info(f"Bulk data needs update: {reason}")
            on_download_needed(reason)
            on_status("Downloading card image database...")

            # Download in background
            self.image_service.download_bulk_metadata_async(
                on_success=on_download_complete,
                on_error=on_download_failed,
            )

        def error_handler(exc: Exception):
            self._bulk_check_worker_active = False
            logger.warning(f"Failed to check bulk data freshness: {exc}")
            if not self.image_service.get_bulk_data():
                self._load_bulk_data_into_memory(on_status)
            else:
                on_status("Ready")

        BackgroundWorker(worker, on_success=success_handler, on_error=error_handler).start()

    def _load_bulk_data_into_memory(
        self, on_status: Callable[[str], None], force: bool = False
    ) -> None:
        """Load the compact card printings index in the background."""
        on_status("Preparing card printings cache…")

        def success_callback(data, stats):
            # Stats logging handled by service
            pass

        def error_callback(msg):
            logger.warning(f"Bulk data load issue: {msg}")

        started = self.image_service.load_printing_index_async(
            force=force,
            on_success=success_callback,
            on_error=error_callback,
        )

        if not started:
            on_status("Ready")

    # ============= State Accessors =============

    def get_current_format(self) -> str:
        """Get the currently selected format."""
        return self.current_format

    def set_current_format(self, format_name: str) -> None:
        """Set the current format."""
        self.current_format = format_name

    def get_zone_cards(self) -> dict[str, list[dict[str, Any]]]:
        """Get current zone cards state."""
        return self.zone_cards

    def get_archetypes(self) -> list[dict[str, Any]]:
        """Get loaded archetypes."""
        return self.archetypes

    def get_filtered_archetypes(self) -> list[dict[str, Any]]:
        """Get filtered archetypes list."""
        return self.filtered_archetypes

    def set_filtered_archetypes(self, archetypes: list[dict[str, Any]]) -> None:
        """Set filtered archetypes."""
        self.filtered_archetypes = archetypes


# Singleton instance
_controller_instance: DeckSelectorController | None = None


def get_deck_selector_controller() -> DeckSelectorController:
    """Get or create the singleton deck selector controller instance."""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = DeckSelectorController()
    return _controller_instance


def reset_deck_selector_controller() -> None:
    """Reset the controller instance (primarily for testing)."""
    global _controller_instance
    _controller_instance = None
