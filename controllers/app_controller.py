"""
Deck Selector Controller - Application logic for the deck selector window.

This controller separates business logic and state management from UI presentation.
It coordinates between services, repositories, and provides a clean interface
for the UI layer to interact with application logic.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    import wx

    from widgets.app_frame import AppFrame

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
from utils.deck import read_curr_deck_file, sanitize_filename, sanitize_zone_cards
from utils.game_constants import FORMAT_OPTIONS
from utils.paths import CACHE_DIR, CONFIG_FILE, DECK_SELECTOR_SETTINGS_FILE, DECKS_DIR
from utils.service_config import (
    COLLECTION_CACHE_MAX_AGE_SECONDS,
    DEFAULT_BULK_DATA_MAX_AGE_DAYS,
)

NOTES_STORE = CACHE_DIR / "deck_notes.json"
OUTBOARD_STORE = CACHE_DIR / "deck_outboard.json"
GUIDE_STORE = CACHE_DIR / "deck_sbguides.json"

BULK_CACHE_MIN_AGE_DAYS = 1
BULK_CACHE_MAX_AGE_DAYS = 365


class BackgroundWorker:
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


class AppController:

    def __init__(self):
        # Services and repositories
        self.deck_repo = get_deck_repository()
        self.metagame_repo = get_metagame_repository()
        self.card_repo = get_card_repository()
        self.deck_service = get_deck_service()
        self.search_service = get_search_service()
        self.collection_service = get_collection_service()
        self.image_service = get_image_service()
        self.store_service = get_store_service()

        # Settings management
        self.settings = self._load_settings()
        self.current_format = self.settings.get("format", "Modern")
        if self.current_format not in FORMAT_OPTIONS:
            self.current_format = "Modern"

        # Config management
        self.config = self._load_config()
        default_deck_dir = Path(self.config.get("deck_selector_save_path") or DECKS_DIR)
        self.deck_save_dir = default_deck_dir.expanduser()
        try:
            self.deck_save_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(f"Unable to create deck save directory '{self.deck_save_dir}': {exc}")
        self.config.setdefault("deck_selector_save_path", str(self.deck_save_dir))

        # Bulk data settings
        raw_force = self.settings.get("force_cached_bulk_data", False)
        self._bulk_cache_force = self._coerce_bool(raw_force)
        self._bulk_data_age_days = self._validate_bulk_cache_age(
            self.settings.get("bulk_data_max_age_days", DEFAULT_BULK_DATA_MAX_AGE_DAYS)
        )
        self.settings.setdefault("force_cached_bulk_data", self._bulk_cache_force)
        self.settings.setdefault("bulk_data_max_age_days", self._bulk_data_age_days)

        # Application state
        self.archetypes: list[dict[str, Any]] = []
        self.filtered_archetypes: list[dict[str, Any]] = []
        self.zone_cards: dict[str, list[dict[str, Any]]] = {"main": [], "side": [], "out": []}
        self.sideboard_guide_entries: list[dict[str, str]] = []
        self.sideboard_exclusions: list[str] = []
        self.left_mode = "builder" if self.settings.get("left_mode") == "builder" else "research"

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
        self._ui_callbacks: dict[str, Callable[..., Any]] = {}
        self.frame = self.create_frame()

    # ============= Card Data Management =============

    def ensure_card_data_loaded(
        self,
        on_success: Callable[[CardDataManager], None],
        on_error: Callable[[Exception], None],
        on_status: Callable[[str], None],
    ) -> None:
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
        deck_number = deck.get("number")
        if not deck_number:
            on_error(ValueError("Deck identifier missing"))
            return

        on_status("Downloading deck…")

        def worker(number: str):
            download_deck(number)
            return read_curr_deck_file()

        BackgroundWorker(worker, deck_number, on_success=on_success, on_error=on_error).start()

    def build_deck_text(self, zone_cards: dict[str, list[dict[str, Any]]] | None = None) -> str:
        deck_text = self.deck_repo.get_current_deck_text()
        if deck_text:
            return deck_text

        zones = zone_cards if zone_cards is not None else self.zone_cards
        if zones:
            try:
                deck_text = self.deck_service.build_deck_text_from_zones(zones)
            except Exception as exc:  # pragma: no cover - defensive log
                logger.debug(f"Failed to build deck text from zones: {exc}")
            else:
                if deck_text:
                    return deck_text

        current_deck = self.deck_repo.get_current_deck() or {}
        for key in ("deck_text", "content", "text"):
            value = current_deck.get(key)
            if value:
                return value

        return ""

    def save_deck(
        self,
        deck_name: str,
        deck_content: str,
        format_name: str,
        deck: dict[str, Any] | None = None,
    ) -> tuple[Path, int | None]:
        safe_name = sanitize_filename(deck_name or "saved_deck") or "saved_deck"
        file_path = self.deck_save_dir / f"{safe_name}.txt"
        with file_path.open("w", encoding="utf-8") as fh:
            fh.write(deck_content)

        deck_id = None
        try:
            deck_id = self.deck_repo.save_to_db(
                deck_name=deck_name,
                deck_content=deck_content,
                format_type=format_name,
                archetype=deck.get("name") if deck else None,
                player=deck.get("player") if deck else None,
                source="mtggoldfish" if deck else "manual",
                metadata=deck or {},
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning(f"Deck saved to file but not database: {exc}")
        else:
            logger.info(f"Deck saved to database: {deck_name} (ID: {deck_id})")

        return file_path, deck_id

    def build_daily_average_deck(
        self,
        on_success: Callable[[dict[str, float], int], None],
        on_error: Callable[[Exception], None],
        on_status: Callable[[str], None],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> tuple[bool, str]:
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
        try:
            info = self.collection_service.load_from_cached_file(directory)
            return True, info
        except (FileNotFoundError, ValueError) as exc:
            logger.debug(f"Could not load collection from cache: {exc}")
            return False, None

    def refresh_collection_from_bridge(
        self, directory: Path | None = None, force: bool = False
    ) -> None:
        callbacks = self._ui_callbacks
        on_status = callbacks.get("on_status", lambda msg: None)
        on_success = callbacks.get("on_collection_refresh_success")
        on_error = callbacks.get("on_collection_failed")
        directory = directory or self.deck_save_dir

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
        max_age_days: int | None = None,
        force_cached: bool | None = None,
    ) -> None:
        if self._bulk_check_worker_active:
            logger.debug("Bulk data check already running")
            return

        callbacks = self._ui_callbacks
        on_status = callbacks.get("on_status", lambda msg: None)
        on_download_needed = callbacks.get("on_bulk_download_needed", lambda reason: None)
        on_download_complete = callbacks.get("on_bulk_download_complete", lambda msg: None)
        on_download_failed = callbacks.get("on_bulk_download_failed", lambda msg: None)

        max_age_days = max_age_days if max_age_days is not None else self._bulk_data_age_days
        force_cached = force_cached if force_cached is not None else self._bulk_cache_force

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
        on_status("Preparing card printings cache…")

        def success_callback(data, stats):
            import wx

            # Persist bulk data and notify UI
            self.image_service.set_bulk_data(data)
            if self.frame:
                wx.CallAfter(self.frame._on_bulk_data_loaded, data, stats)

        def error_callback(msg):
            import wx

            logger.warning(f"Bulk data load issue: {msg}")
            if self.frame:
                wx.CallAfter(self.frame._on_bulk_data_load_failed, msg)

        started = self.image_service.load_printing_index_async(
            force=force,
            on_success=success_callback,
            on_error=error_callback,
        )

        if not started:
            on_status("Ready")

    def load_bulk_data_into_memory(
        self, on_status: Callable[[str], None], force: bool = False
    ) -> None:
        """Public wrapper for UI callers."""
        self._load_bulk_data_into_memory(on_status=on_status, force=force)

    # ============= Settings Management =============

    def _load_settings(self) -> dict[str, Any]:
        if not DECK_SELECTOR_SETTINGS_FILE.exists():
            return {}
        try:
            with DECK_SELECTOR_SETTINGS_FILE.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:
            logger.warning(f"Failed to load deck selector settings: {exc}")
            return {}

    def _load_config(self) -> dict[str, Any]:
        if not CONFIG_FILE.exists():
            logger.debug(f"{CONFIG_FILE} not found; using default deck save path")
            return {}
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:
            logger.warning(f"Invalid {CONFIG_FILE} ({exc}); using default deck save path")
            return {}

    def save_settings(
        self, window_size: tuple[int, int] | None = None, screen_pos: tuple[int, int] | None = None
    ) -> None:
        data = dict(self.settings)
        data.update(
            {
                "format": self.current_format,
                "left_mode": self.left_mode,
                "force_cached_bulk_data": self._bulk_cache_force,
                "bulk_data_max_age_days": self._bulk_data_age_days,
                "saved_deck_text": self.deck_repo.get_current_deck_text(),
                "saved_zone_cards": self._serialize_zone_cards(),
            }
        )

        if window_size:
            data["window_size"] = list(window_size)
        if screen_pos:
            data["screen_pos"] = list(screen_pos)

        current_deck = self.deck_repo.get_current_deck()
        if current_deck:
            data["saved_deck_info"] = current_deck
        elif "saved_deck_info" in data:
            data.pop("saved_deck_info")

        try:
            with DECK_SELECTOR_SETTINGS_FILE.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:
            logger.warning(f"Unable to persist deck selector settings: {exc}")
        self.settings = data

    def _serialize_zone_cards(self) -> dict[str, list[dict[str, Any]]]:
        return {zone: sanitize_zone_cards(cards) for zone, cards in self.zone_cards.items()}

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _validate_bulk_cache_age(self, value: Any) -> int:
        try:
            days = int(float(value))
        except (TypeError, ValueError):
            days = int(DEFAULT_BULK_DATA_MAX_AGE_DAYS)
        return max(BULK_CACHE_MIN_AGE_DAYS, min(days, BULK_CACHE_MAX_AGE_DAYS))

    def get_bulk_cache_age_days(self) -> int:
        return self._bulk_data_age_days

    def is_forcing_cached_bulk_data(self) -> bool:
        return self._bulk_cache_force

    def set_force_cached_bulk_data(self, enabled: bool) -> None:
        if self._bulk_cache_force == enabled:
            return
        self._bulk_cache_force = enabled
        self.settings["force_cached_bulk_data"] = enabled

    def set_bulk_cache_age_days(self, days: int) -> None:
        clamped = self._validate_bulk_cache_age(days)
        if clamped == self._bulk_data_age_days:
            return
        self._bulk_data_age_days = clamped
        self.settings["bulk_data_max_age_days"] = clamped

    def restore_session_state(self) -> dict[str, Any]:
        result: dict[str, Any] = {"left_mode": self.left_mode}

        # Restore zone cards
        saved_zones = self.settings.get("saved_zone_cards") or {}
        changed = False
        for zone in ("main", "side", "out"):
            entries = saved_zones.get(zone, [])
            if not isinstance(entries, list):
                continue
            sanitized = sanitize_zone_cards(entries)
            if sanitized:
                self.zone_cards[zone] = sanitized
                changed = True
        if changed:
            result["zone_cards"] = self.zone_cards

        # Restore deck text
        saved_text = self.settings.get("saved_deck_text", "")
        if saved_text:
            self.deck_repo.set_current_deck_text(saved_text)
            result["deck_text"] = saved_text

        # Restore deck info
        saved_deck = self.settings.get("saved_deck_info")
        if isinstance(saved_deck, dict):
            self.deck_repo.set_current_deck(saved_deck)
            result["deck_info"] = saved_deck

        # Window preferences
        window_size = self.settings.get("window_size")
        if isinstance(window_size, list) and len(window_size) == 2:
            result["window_size"] = tuple(window_size)

        screen_pos = self.settings.get("screen_pos")
        if isinstance(screen_pos, list) and len(screen_pos) == 2:
            result["screen_pos"] = tuple(screen_pos)

        return result

    # ============= Business Logic Methods =============

    def download_deck(
        self,
        deck_number: str,
        on_success: Callable[[str], None],
        on_error: Callable[[Exception], None],
        on_status: Callable[[str], None],
    ) -> None:
        on_status("Downloading deck…")

        def worker(number: str):
            download_deck(number)
            return read_curr_deck_file()

        BackgroundWorker(worker, deck_number, on_success=on_success, on_error=on_error).start()

    def check_bulk_data_freshness(self, max_age_days: int) -> tuple[bool, str]:
        return self.image_service.check_bulk_data_freshness(max_age_days=max_age_days)

    def download_bulk_data(
        self, on_success: Callable[[str], None], on_error: Callable[[str], None]
    ) -> None:
        self.image_service.download_bulk_metadata_async(on_success=on_success, on_error=on_error)

    def start_daily_average_build(
        self,
        on_success: Callable[[dict[str, float], int], None],
        on_error: Callable[[Exception], None],
        on_status: Callable[[str], None],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> tuple[bool, str]:
        return self.build_daily_average_deck(
            on_success=on_success,
            on_error=on_error,
            on_status=on_status,
            on_progress=on_progress,
        )

    # ============= State Accessors =============

    def get_current_format(self) -> str:
        return self.current_format

    def set_current_format(self, format_name: str) -> None:
        self.current_format = format_name

    def get_zone_cards(self) -> dict[str, list[dict[str, Any]]]:
        return self.zone_cards

    def get_archetypes(self) -> list[dict[str, Any]]:
        return self.archetypes

    def get_filtered_archetypes(self) -> list[dict[str, Any]]:
        return self.filtered_archetypes

    def set_filtered_archetypes(self, archetypes: list[dict[str, Any]]) -> None:
        self.filtered_archetypes = archetypes

    def get_left_mode(self) -> str:
        return self.left_mode

    def set_left_mode(self, mode: str) -> None:
        self.left_mode = mode

    # ============= Initial Loading Orchestration =============

    def run_initial_loads(self, deck_save_dir: Path, force_archetypes: bool = False) -> None:
        callbacks = self._ui_callbacks

        self.fetch_archetypes(
            on_success=callbacks.get("on_archetypes_success"),
            on_error=callbacks.get("on_archetypes_error"),
            on_status=callbacks.get("on_status"),
            force=force_archetypes,
        )

        # Step 3: Load collection from cache (non-blocking)
        success, info = self.load_collection_from_cache(deck_save_dir)
        if success and info:
            callback = callbacks.get("on_collection_loaded")
            if callback:
                callback(info)
        else:
            callback = callbacks.get("on_collection_not_found")
            if callback:
                callback()

        # Step 4: Check and download bulk data if needed (non-blocking)
        self.check_and_download_bulk_data(
            max_age_days=self._bulk_data_age_days,
            force_cached=self._bulk_cache_force,
        )

    # ============= Frame Factory =============

    def create_frame(self, parent: wx.Window | None = None) -> AppFrame:
        import wx

        from widgets.app_frame import AppFrame

        # Create the frame
        frame = AppFrame(controller=self, parent=parent)

        def _format_collection_label(info: dict[str, Any]) -> str:
            filepath = info["filepath"]
            card_count = info["card_count"]
            age_hours = info["age_hours"]
            age_str = f"{age_hours}h ago" if age_hours > 0 else "recent"
            return f"Collection: {filepath.name} ({card_count} entries, {age_str})"

        def _on_collection_loaded(info: dict[str, Any]) -> None:
            wx.CallAfter(
                frame.collection_status_label.SetLabel,
                _format_collection_label(info),
            )
            wx.CallAfter(frame.main_table.set_cards, self.zone_cards["main"])
            wx.CallAfter(frame.side_table.set_cards, self.zone_cards["side"])

        # Define UI callback functions that marshal to UI thread
        self._ui_callbacks = {
            "on_archetypes_success": lambda archetypes: wx.CallAfter(
                frame._on_archetypes_loaded, archetypes
            ),
            "on_archetypes_error": lambda error: wx.CallAfter(frame._on_archetypes_error, error),
            "on_collection_loaded": _on_collection_loaded,
            "on_collection_not_found": lambda: wx.CallAfter(
                frame.collection_status_label.SetLabel,
                "No collection found. Click 'Refresh Collection' to fetch from MTGO.",
            ),
            "on_collection_refresh_success": lambda filepath, cards: wx.CallAfter(
                frame._on_collection_fetched, filepath, cards
            ),
            "on_collection_failed": lambda msg: wx.CallAfter(
                frame._on_collection_fetch_failed, msg
            ),
            "on_status": lambda message: wx.CallAfter(frame._set_status, message),
            "on_bulk_download_needed": lambda reason: logger.info(
                f"Bulk data needs update: {reason}"
            ),
            "on_bulk_download_complete": lambda msg: wx.CallAfter(
                frame._on_bulk_data_downloaded, msg
            ),
            "on_bulk_download_failed": lambda msg: wx.CallAfter(frame._on_bulk_data_failed, msg),
        }

        # Restore UI state from controller's session data
        wx.CallAfter(frame._restore_session_state)

        # Trigger initial loading after frame is ready
        wx.CallAfter(
            lambda: self.run_initial_loads(
                deck_save_dir=self.deck_save_dir,
            )
        )

        return frame


# Singleton instance
_controller_instance: AppController | None = None


def get_deck_selector_controller() -> AppController:
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = AppController()
    return _controller_instance


def reset_deck_selector_controller() -> None:
    global _controller_instance
    _controller_instance = None
