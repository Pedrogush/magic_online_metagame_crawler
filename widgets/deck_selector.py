import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import wx
from loguru import logger

from navigators.mtggoldfish import download_deck, get_archetype_decks, get_archetypes
from repositories.card_repository import get_card_repository
from repositories.deck_repository import get_deck_repository
from repositories.metagame_repository import get_metagame_repository
from services.collection_service import get_collection_service
from services.deck_service import get_deck_service
from services.image_service import get_image_service
from services.search_service import get_search_service
from utils.card_data import CardDataManager
from utils.constants import (
    DARK_ALT,
    DARK_BG,
    DARK_PANEL,
    FULL_MANA_SYMBOLS,
    LIGHT_TEXT,
    SUBDUED_TEXT,
    ZONE_TITLES,
)
from utils.deck import (
    read_curr_deck_file,
    sanitize_filename,
    sanitize_zone_cards,
)
from utils.mana_icon_factory import ManaIconFactory, type_global_mana_symbol
from utils.paths import (
    CACHE_DIR,
    CONFIG_FILE,
    DECK_SELECTOR_SETTINGS_FILE,
    DECKS_DIR,
)
from utils.stylize import stylize_listbox, stylize_textctrl
from widgets.buttons.deck_action_buttons import DeckActionButtons
from widgets.buttons.mana_button import create_mana_button, get_mana_font
from widgets.dialogs.image_download_dialog import show_image_download_dialog
from widgets.identify_opponent import MTGOpponentDeckSpy
from widgets.match_history import MatchHistoryFrame
from widgets.metagame_analysis import MetagameAnalysisFrame
from widgets.panels.card_inspector_panel import CardInspectorPanel
from widgets.panels.card_table_panel import CardTablePanel
from widgets.panels.deck_builder_panel import DeckBuilderPanel
from widgets.panels.deck_notes_panel import DeckNotesPanel
from widgets.panels.deck_research_panel import DeckResearchPanel
from widgets.panels.deck_stats_panel import DeckStatsPanel
from widgets.panels.sideboard_guide_panel import (
    SideboardGuideHandlers,
    SideboardGuidePanel,
)
from widgets.timer_alert import TimerAlertFrame

FORMAT_OPTIONS = [
    "Modern",
    "Standard",
    "Pioneer",
    "Legacy",
    "Vintage",
    "Pauper",
    "Commander",
    "Brawl",
    "Historic",
]

LEGACY_CONFIG_FILE = Path("config.json")
LEGACY_CURR_DECK_CACHE = Path("cache") / "curr_deck.txt"
LEGACY_CURR_DECK_ROOT = Path("curr_deck.txt")
NOTES_STORE = CACHE_DIR / "deck_notes.json"
OUTBOARD_STORE = CACHE_DIR / "deck_outboard.json"
GUIDE_STORE = CACHE_DIR / "deck_sbguides.json"
LEGACY_NOTES_STORE = CACHE_DIR / "deck_notes_wx.json"
LEGACY_OUTBOARD_STORE = CACHE_DIR / "deck_outboard_wx.json"
LEGACY_GUIDE_STORE = CACHE_DIR / "deck_sbguides_wx.json"
CARD_INSPECTOR_LOG = CACHE_DIR / "card_inspector_debug.log"

for new_path, legacy_path in [
    (NOTES_STORE, LEGACY_NOTES_STORE),
    (OUTBOARD_STORE, LEGACY_OUTBOARD_STORE),
    (GUIDE_STORE, LEGACY_GUIDE_STORE),
]:
    if not new_path.exists() and legacy_path.exists():
        try:
            legacy_path.replace(new_path)
            logger.info(f"Migrated {legacy_path.name} to {new_path.name}")
        except OSError as exc:  # pragma: no cover - migration best-effort
            logger.warning(f"Failed to migrate {legacy_path} to {new_path}: {exc}")


CONFIG: dict[str, Any] = {}
if CONFIG_FILE.exists():
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as _cfg_file:
            CONFIG = json.load(_cfg_file)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
        logger.warning(f"Invalid {CONFIG_FILE} ({exc}); using default deck save path")
        CONFIG = {}
elif LEGACY_CONFIG_FILE.exists():
    try:
        with LEGACY_CONFIG_FILE.open("r", encoding="utf-8") as _cfg_file:
            CONFIG = json.load(_cfg_file)
        logger.warning(
            "Loaded legacy config.json from project root; migrating to config/ directory"
        )
        try:
            with CONFIG_FILE.open("w", encoding="utf-8") as fh:
                json.dump(CONFIG, fh, indent=4)
        except OSError as exc:
            logger.warning(f"Failed to write migrated config.json: {exc}")
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
        logger.warning(f"Invalid legacy config.json ({exc}); using default deck save path")
        CONFIG = {}
else:
    logger.debug(f"{CONFIG_FILE} not found; using default deck save path")

default_deck_dir = Path(CONFIG.get("deck_selector_save_path") or DECKS_DIR)
DECK_SAVE_DIR = default_deck_dir.expanduser()
try:
    DECK_SAVE_DIR.mkdir(parents=True, exist_ok=True)
except OSError as exc:  # pragma: no cover - defensive logging
    logger.warning(f"Unable to create deck save directory '{DECK_SAVE_DIR}': {exc}")
CONFIG.setdefault("deck_selector_save_path", str(DECK_SAVE_DIR))


def format_deck_name(deck: dict[str, Any]) -> str:
    """Compose a compact deck line for list display."""
    date = deck.get("date", "")
    player = deck.get("player", "")
    event = deck.get("event", "")
    result = deck.get("result", "")
    return f"{date} | {player} — {event} [{result}]".strip()


class _Worker:
    """Helper for dispatching background work and returning results on the UI thread."""

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
        except Exception as exc:  # pragma: no cover - UI side effects
            logger.exception(f"Background task failed: {exc}")
            if self.on_error:
                wx.CallAfter(self.on_error, exc)
            return
        if self.on_success:
            wx.CallAfter(self.on_success, result)


class ManaKeyboardFrame(wx.Frame):
    def __init__(
        self,
        parent: wx.Window,
        create_button: Callable[[wx.Window, str, Callable[[str], None]], wx.Button],
        on_symbol: Callable[[str], None],
    ) -> None:
        super().__init__(
            parent,
            title="Mana Keyboard",
            size=(620, 330),
            style=wx.CAPTION | wx.CLOSE_BOX | wx.FRAME_TOOL_WINDOW | wx.STAY_ON_TOP,
        )
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DARK_BG)
        root = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(root)

        info = wx.StaticText(panel, label="Click a symbol to type it anywhere")
        info.SetForegroundColour(LIGHT_TEXT)
        root.Add(info, 0, wx.ALIGN_CENTER | wx.ALL, 8)

        wrap = wx.WrapSizer(wx.HORIZONTAL)
        for token in FULL_MANA_SYMBOLS:
            btn = create_button(panel, token, on_symbol)
            wrap.Add(btn, 0, wx.ALL, 4)
        root.Add(wrap, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 10)
        self.CentreOnParent()


class MTGDeckSelectionFrame(wx.Frame, SideboardGuideHandlers):
    """wxPython-based metagame research + deck builder UI."""

    def __init__(self, parent: wx.Window | None = None):
        super().__init__(parent, title="MTGO Deck Research & Builder", size=(1380, 860))

        # Initialize repositories and services
        self.deck_repo = get_deck_repository()
        self.metagame_repo = get_metagame_repository()
        self.card_repo = get_card_repository()
        self.deck_service = get_deck_service()
        self.search_service = get_search_service()
        self.collection_service = get_collection_service()
        self.image_service = get_image_service()
        self.card_data_dialogs_disabled = False

        self.settings = self._load_window_settings()
        self.current_format = self.settings.get("format", "Modern")
        if self.current_format not in FORMAT_OPTIONS:
            self.current_format = "Modern"

        self.archetypes: list[dict[str, Any]] = []
        self.filtered_archetypes: list[dict[str, Any]] = []
        self.zone_cards: dict[str, list[dict[str, Any]]] = {"main": [], "side": [], "out": []}

        # Load deck metadata stores via repository
        self.deck_notes_store = self._load_store(NOTES_STORE)
        self.outboard_store = self._load_store(OUTBOARD_STORE)
        self.guide_store = self._load_store(GUIDE_STORE)
        self.outboard_store_path = OUTBOARD_STORE
        self.guide_store_path = GUIDE_STORE

        self.sideboard_guide_entries: list[dict[str, str]] = []
        self.sideboard_exclusions: list[str] = []
        self.active_inspector_zone: str | None = None
        self.left_mode = "builder" if self.settings.get("left_mode") == "builder" else "research"
        self.left_stack: wx.Simplebook | None = None
        self.research_panel: DeckResearchPanel | None = None
        self.builder_panel: DeckBuilderPanel | None = None

        # Thread-safe loading state flags
        self._loading_lock = threading.Lock()
        self.loading_archetypes = False
        self.loading_decks = False
        self.loading_daily_average = False

        self._save_timer: wx.Timer | None = None
        self.mana_icons = ManaIconFactory()
        self.tracker_window: MTGOpponentDeckSpy | None = None
        self.timer_window: TimerAlertFrame | None = None
        self.history_window: MatchHistoryFrame | None = None
        self.metagame_window: MetagameAnalysisFrame | None = None
        self.mana_keyboard_window: ManaKeyboardFrame | None = None

        self._build_ui()
        self._apply_window_preferences()
        self.SetMinSize((1260, 760))
        self.Centre(wx.BOTH)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SIZE, self.on_window_change)
        self.Bind(wx.EVT_MOVE, self.on_window_change)

        wx.CallAfter(self._run_initial_loads)

    # ------------------------------------------------------------------ UI ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the main UI structure."""
        self.SetBackgroundColour(DARK_BG)
        self._setup_status_bar()

        root_panel = wx.Panel(self)
        root_panel.SetBackgroundColour(DARK_BG)
        root_sizer = wx.BoxSizer(wx.HORIZONTAL)
        root_panel.SetSizer(root_sizer)

        # Build left and right panels
        left_panel = self._build_left_panel(root_panel)
        root_sizer.Add(left_panel, 0, wx.EXPAND | wx.ALL, 10)

        right_panel = self._build_right_panel(root_panel)
        root_sizer.Add(right_panel, 1, wx.EXPAND | wx.ALL, 10)

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetBackgroundColour(DARK_PANEL)
        self.status_bar.SetForegroundColour(LIGHT_TEXT)
        self._set_status("Ready")

    def _build_left_panel(self, parent: wx.Window) -> wx.Panel:
        """Build the left panel with research/builder panels."""
        left_panel = wx.Panel(parent)
        left_panel.SetBackgroundColour(DARK_PANEL)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_panel.SetSizer(left_sizer)

        self.left_stack = wx.Simplebook(left_panel)
        self.left_stack.SetBackgroundColour(DARK_PANEL)
        left_sizer.Add(self.left_stack, 1, wx.EXPAND)

        self.research_panel = DeckResearchPanel(
            parent=self.left_stack,
            format_options=FORMAT_OPTIONS,
            initial_format=self.current_format,
            on_format_changed=self.on_format_changed,
            on_archetype_filter=self.on_archetype_filter,
            on_archetype_selected=self.on_archetype_selected,
            on_reload_archetypes=lambda: self.fetch_archetypes(force=True),
        )
        self.left_stack.AddPage(self.research_panel, "Research")

        self.builder_panel = DeckBuilderPanel(
            parent=self.left_stack,
            mana_icons=self.mana_icons,
            on_switch_to_research=lambda: self._show_left_panel("research"),
            on_ensure_card_data=self.ensure_card_data_loaded,
            get_mana_font=self._get_mana_font,
            create_mana_button=self._create_mana_button,
            open_mana_keyboard=self._open_full_mana_keyboard,
            on_search=self._on_builder_search,
            on_clear=self._on_builder_clear,
            on_result_selected=self._on_builder_result_selected,
        )
        self.left_stack.AddPage(self.builder_panel, "Builder")
        self._show_left_panel(self.left_mode, force=True)

        return left_panel

    def _build_right_panel(self, parent: wx.Window) -> wx.Panel:
        """Build the right panel with all deck management components."""
        right_panel = wx.Panel(parent)
        right_panel.SetBackgroundColour(DARK_BG)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        right_panel.SetSizer(right_sizer)

        # Toolbar
        toolbar = self._build_toolbar(right_panel)
        right_sizer.Add(toolbar, 0, wx.EXPAND | wx.BOTTOM, 6)

        # Upper section with summary/decklist and card inspector
        upper_split = wx.BoxSizer(wx.HORIZONTAL)
        right_sizer.Add(upper_split, 1, wx.EXPAND | wx.BOTTOM, 10)

        # Left side: Summary and deck list
        summary_column = self._build_summary_and_deck_list(right_panel)
        upper_split.Add(summary_column, 1, wx.EXPAND | wx.RIGHT, 10)

        # Right side: Card inspector
        inspector_sizer = self._build_card_inspector(right_panel)
        upper_split.Add(inspector_sizer, 2, wx.EXPAND)

        # Lower section: Deck workspace
        self._build_deck_workspace(right_panel, right_sizer)

        return right_panel

    def _build_toolbar(self, parent: wx.Window) -> wx.BoxSizer:
        """Build the toolbar with utility buttons."""
        toolbar = wx.BoxSizer(wx.HORIZONTAL)

        buttons = [
            ("Opponent Tracker", lambda: self.open_opponent_tracker()),
            ("Timer Alert", lambda: self.open_timer_alert()),
            ("Match History", lambda: self.open_match_history()),
            ("Metagame Analysis", lambda: self.open_metagame_analysis()),
            ("Load Collection", lambda: self._refresh_collection_inventory(force=True)),
            (
                "Download Card Images",
                lambda: show_image_download_dialog(
                    self, self.image_cache, self.image_downloader, self._set_status
                ),
            ),
        ]

        for label, handler in buttons:
            btn = wx.Button(parent, label=label)
            btn.Bind(wx.EVT_BUTTON, lambda evt, h=handler: h())
            toolbar.Add(btn, 0, wx.RIGHT, 6)

        toolbar.AddStretchSpacer(1)
        return toolbar

    def _build_summary_and_deck_list(self, parent: wx.Window) -> wx.BoxSizer:
        """Build the summary text and deck list column."""
        summary_column = wx.BoxSizer(wx.VERTICAL)

        # Archetype summary
        summary_box = wx.StaticBox(parent, label="Archetype Summary")
        summary_box.SetForegroundColour(LIGHT_TEXT)
        summary_box.SetBackgroundColour(DARK_PANEL)
        summary_sizer = wx.StaticBoxSizer(summary_box, wx.VERTICAL)
        summary_column.Add(summary_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.summary_text = wx.TextCtrl(
            summary_box,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP | wx.NO_BORDER,
        )
        stylize_textctrl(self.summary_text, multiline=True)
        self.summary_text.SetMinSize((-1, 110))
        summary_sizer.Add(self.summary_text, 1, wx.EXPAND | wx.ALL, 6)

        # Deck list
        deck_box = wx.StaticBox(parent, label="Deck Results")
        deck_box.SetForegroundColour(LIGHT_TEXT)
        deck_box.SetBackgroundColour(DARK_PANEL)
        deck_sizer = wx.StaticBoxSizer(deck_box, wx.VERTICAL)
        summary_column.Add(deck_sizer, 1, wx.EXPAND)

        self.deck_list = wx.ListBox(deck_box, style=wx.LB_SINGLE)
        stylize_listbox(self.deck_list)
        self.deck_list.Bind(wx.EVT_LISTBOX, self.on_deck_selected)
        deck_sizer.Add(self.deck_list, 1, wx.EXPAND | wx.ALL, 6)

        # Deck action buttons
        self.deck_action_buttons = DeckActionButtons(
            deck_box,
            on_load=lambda: self.on_load_deck_clicked(None),
            on_copy=lambda: self.on_copy_clicked(None),
            on_save=lambda: self.on_save_clicked(None),
            on_daily_average=lambda: self.on_daily_average_clicked(None),
        )
        deck_sizer.Add(self.deck_action_buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Keep references for backward compatibility
        self.load_button = self.deck_action_buttons.load_button
        self.daily_average_button = self.deck_action_buttons.daily_average_button
        self.copy_button = self.deck_action_buttons.copy_button
        self.save_button = self.deck_action_buttons.save_button

        return summary_column

    def _build_card_inspector(self, parent: wx.Window) -> wx.StaticBoxSizer:
        """Build the card inspector panel."""
        inspector_box = wx.StaticBox(parent, label="Card Inspector")
        inspector_box.SetForegroundColour(LIGHT_TEXT)
        inspector_box.SetBackgroundColour(DARK_PANEL)
        inspector_sizer = wx.StaticBoxSizer(inspector_box, wx.VERTICAL)

        self.card_inspector_panel = CardInspectorPanel(
            inspector_box,
            card_manager=self.card_repo.get_card_manager(),
            mana_icons=self.mana_icons,
        )
        inspector_sizer.Add(self.card_inspector_panel, 1, wx.EXPAND)

        # Keep backward compatibility references (delegate to image service)
        self.image_cache = self.image_service.image_cache
        self.image_downloader = self.image_service.image_downloader

        return inspector_sizer

    def _build_deck_workspace(self, parent: wx.Window, parent_sizer: wx.BoxSizer) -> None:
        """Build the deck workspace with tables, stats, guide, and notes."""
        detail_box = wx.StaticBox(parent, label="Deck Workspace")
        detail_box.SetForegroundColour(LIGHT_TEXT)
        detail_box.SetBackgroundColour(DARK_PANEL)
        detail_sizer = wx.StaticBoxSizer(detail_box, wx.VERTICAL)
        parent_sizer.Add(detail_sizer, 1, wx.EXPAND)

        self.deck_tabs = wx.Notebook(detail_box)
        detail_sizer.Add(self.deck_tabs, 1, wx.EXPAND | wx.ALL, 6)

        # Deck tables tab
        self._build_deck_tables_tab()

        # Stats, guide, and notes tabs
        self.deck_stats_panel = DeckStatsPanel(
            self.deck_tabs,
            card_manager=self.card_repo.get_card_manager(),
            deck_service=self.deck_service,
        )
        self.deck_tabs.AddPage(self.deck_stats_panel, "Stats")
        # Maintain compatibility with callers/tests that accessed the old label directly.
        self.stats_summary = self.deck_stats_panel.summary_label

        self.sideboard_guide_panel = SideboardGuidePanel(
            self.deck_tabs,
            on_add_callback=lambda: self._on_add_guide_entry(),
            on_edit_callback=lambda: self._on_edit_guide_entry(),
            on_remove_callback=lambda: self._on_remove_guide_entry(),
            on_exclusions_callback=lambda: self._on_edit_exclusions(),
        )
        self.deck_tabs.AddPage(self.sideboard_guide_panel, "Sideboard Guide")

        self.deck_notes_panel = DeckNotesPanel(
            self.deck_tabs, on_save_callback=lambda notes: self._save_current_notes()
        )
        self.deck_tabs.AddPage(self.deck_notes_panel, "Deck Notes")

    def _build_deck_tables_tab(self) -> None:
        """Build the deck tables tab with main/side/out boards."""
        self.deck_tables_page = wx.Panel(self.deck_tabs)
        self.deck_tabs.AddPage(self.deck_tables_page, "Deck Tables")
        tables_sizer = wx.BoxSizer(wx.VERTICAL)
        self.deck_tables_page.SetSizer(tables_sizer)

        self.zone_notebook = wx.Notebook(self.deck_tables_page)
        tables_sizer.Add(self.zone_notebook, 1, wx.EXPAND | wx.BOTTOM, 6)

        # Create zone tables
        self.main_table = self._create_zone_table("main", "Mainboard")
        self.side_table = self._create_zone_table("side", "Sideboard")
        self.out_table = self._create_zone_table(
            "out", "Outboard", owned_status_func=lambda name, qty: ("Out", wx.Colour(255, 255, 255))
        )

        # Collection status
        self.collection_status_label = wx.StaticText(
            self.deck_tables_page, label="Collection inventory not loaded."
        )
        self.collection_status_label.SetForegroundColour(SUBDUED_TEXT)
        tables_sizer.Add(self.collection_status_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

    def _create_zone_table(
        self, zone: str, tab_name: str, owned_status_func=None
    ) -> CardTablePanel:
        """Create a CardTablePanel for a specific zone."""
        if owned_status_func is None:
            owned_status_func = self._owned_status

        table = CardTablePanel(
            self.zone_notebook,
            zone,
            self.mana_icons,
            self._get_card_metadata,
            owned_status_func,
            self._handle_zone_delta,
            self._handle_zone_remove,
            self._handle_zone_add,
            self._handle_card_focus,
        )
        self.zone_notebook.AddPage(table, tab_name)
        return table

    # ------------------------------------------------------------------ Left panel helpers -------------------------------------------------
    def _show_left_panel(self, mode: str, force: bool = False) -> None:
        target = "builder" if mode == "builder" else "research"
        if self.left_stack:
            index = 1 if target == "builder" else 0
            if force or self.left_stack.GetSelection() != index:
                self.left_stack.ChangeSelection(index)
        if target == "builder":
            self.ensure_card_data_loaded()
        if force or self.left_mode != target:
            self.left_mode = target
            self._schedule_settings_save()

    def _get_mana_font(self, size: int = 14) -> wx.Font:
        """Wrapper for get_mana_font that provides parent font."""
        return get_mana_font(size, self.GetFont())

    def _create_mana_button(
        self, parent: wx.Window, token: str, handler: Callable[[str], None]
    ) -> wx.Button:
        """Wrapper for create_mana_button that provides mana_icons."""
        return create_mana_button(parent, token, handler, self.mana_icons)

    def _open_full_mana_keyboard(self) -> None:
        if self.mana_keyboard_window and self.mana_keyboard_window.IsShown():
            self.mana_keyboard_window.Raise()
            return
        frame = ManaKeyboardFrame(self, self._create_mana_button, type_global_mana_symbol)
        frame.Bind(wx.EVT_CLOSE, self._on_mana_keyboard_closed)
        frame.Show()
        self.mana_keyboard_window = frame

    def _on_mana_keyboard_closed(self, event: wx.CloseEvent) -> None:
        self.mana_keyboard_window = None
        event.Skip()

    def _restore_session_state(self) -> None:
        saved_mode = self.settings.get("left_mode")
        if saved_mode in {"research", "builder"}:
            self.left_mode = saved_mode
            self._show_left_panel(self.left_mode, force=True)
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
            self.main_table.set_cards(self.zone_cards["main"])
            self.side_table.set_cards(self.zone_cards["side"])
            self.out_table.set_cards(self.zone_cards["out"])
        saved_text = self.settings.get("saved_deck_text", "")
        if saved_text:
            self.deck_repo.set_current_deck_text(saved_text)
            self._update_stats(saved_text)
            self.copy_button.Enable(True)
            self.save_button.Enable(True)
        saved_deck = self.settings.get("saved_deck_info")
        if isinstance(saved_deck, dict):
            self.deck_repo.set_current_deck(saved_deck)

    def _run_initial_loads(self) -> None:
        self._restore_session_state()
        self.fetch_archetypes()
        self._load_collection_from_cache()  # Fast cache-only load on startup
        self._check_and_download_bulk_data()  # Download card image bulk data if needed

    def _set_status(self, message: str) -> None:
        if self.status_bar:
            self.status_bar.SetStatusText(message)
        logger.info(message)

    # ------------------------------------------------------------------ Window persistence ---------------------------------------------------
    def _load_window_settings(self) -> dict[str, Any]:
        if not DECK_SELECTOR_SETTINGS_FILE.exists():
            return {}
        try:
            with DECK_SELECTOR_SETTINGS_FILE.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
            logger.warning(f"Failed to load deck selector settings: {exc}")
            return {}

    def _save_window_settings(self) -> None:
        data = dict(self.settings)
        pos = self.GetPosition()
        size = self.GetSize()
        data.update(
            {
                "format": self.current_format,
                "window_size": [size.width, size.height],
                "screen_pos": [pos.x, pos.y],
                "left_mode": self.left_mode,
                "saved_deck_text": self.deck_repo.get_current_deck_text(),
                "saved_zone_cards": self._serialize_zone_cards(),
            }
        )
        current_deck = self.deck_repo.get_current_deck()
        if current_deck:
            data["saved_deck_info"] = current_deck
        elif "saved_deck_info" in data:
            data.pop("saved_deck_info")
        try:
            with DECK_SELECTOR_SETTINGS_FILE.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:  # pragma: no cover - defensive logging
            logger.warning(f"Unable to persist deck selector settings: {exc}")
        self.settings = data

    def _serialize_zone_cards(self) -> dict[str, list[dict[str, Any]]]:
        return {zone: sanitize_zone_cards(cards) for zone, cards in self.zone_cards.items()}

    def _apply_window_preferences(self) -> None:
        size = self.settings.get("window_size")
        if isinstance(size, list) and len(size) == 2:
            try:
                self.SetSize(wx.Size(int(size[0]), int(size[1])))
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid saved window size")
        pos = self.settings.get("screen_pos")
        if isinstance(pos, list) and len(pos) == 2:
            try:
                self.SetPosition(wx.Point(int(pos[0]), int(pos[1])))
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid saved window position")

    def _schedule_settings_save(self) -> None:
        if self._save_timer is None:
            self._save_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._flush_pending_settings, self._save_timer)
        if self._save_timer.IsRunning():
            self._save_timer.Stop()
        self._save_timer.StartOnce(600)

    def on_window_change(self, event: wx.Event) -> None:
        self._schedule_settings_save()
        event.Skip()

    def _flush_pending_settings(self, _event: wx.TimerEvent) -> None:
        self._save_window_settings()

    # ------------------------------------------------------------------ Event handlers -------------------------------------------------------
    def on_format_changed(self) -> None:
        """Handle format selection change."""
        self.current_format = self.research_panel.get_selected_format()
        self.fetch_archetypes(force=True)

    def on_archetype_filter(self) -> None:
        """Handle archetype search filter changes."""
        query = self.research_panel.get_search_query()
        if not query:
            self.filtered_archetypes = list(self.archetypes)
        else:
            self.filtered_archetypes = [
                entry for entry in self.archetypes if query in entry.get("name", "").lower()
            ]
        self._populate_archetype_list()

    def on_archetype_selected(self) -> None:
        """Handle archetype selection from the list."""
        with self._loading_lock:
            if self.loading_archetypes or self.loading_decks:
                return
        idx = self.research_panel.get_selected_archetype_index()
        if idx < 0:
            return
        archetype = self.filtered_archetypes[idx]
        self._load_decks_for_archetype(archetype)

    def on_deck_selected(self, _event: wx.CommandEvent) -> None:
        with self._loading_lock:
            if self.loading_decks:
                return
        idx = self.deck_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        deck = self.deck_repo.get_decks_list()[idx]
        self.deck_repo.set_current_deck(deck)
        self.load_button.Enable()
        self.copy_button.Enable(self._has_deck_loaded())
        self.save_button.Enable(self._has_deck_loaded())
        self._set_status(f"Selected deck {format_deck_name(deck)}")
        self._show_left_panel("builder")
        self._schedule_settings_save()

    def on_load_deck_clicked(self, _event: wx.CommandEvent) -> None:
        current_deck = self.deck_repo.get_current_deck()
        with self._loading_lock:
            if self.loading_decks:
                return
        if not current_deck:
            return
        self._download_and_display_deck(current_deck)

    def on_daily_average_clicked(self, _event: wx.CommandEvent) -> None:
        with self._loading_lock:
            if self.loading_daily_average:
                return
        if not self.deck_repo.get_decks_list():
            return
        self._build_daily_average_deck()

    def on_copy_clicked(self, _event: wx.CommandEvent) -> None:
        deck_content = self._build_deck_text().strip()
        if not deck_content:
            wx.MessageBox("No deck to copy.", "Copy Deck", wx.OK | wx.ICON_INFORMATION)
            return
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(deck_content))
            finally:
                wx.TheClipboard.Close()
            self._set_status("Deck copied to clipboard.")
        else:  # pragma: no cover
            wx.MessageBox("Could not access clipboard.", "Copy Deck", wx.OK | wx.ICON_WARNING)

    def on_save_clicked(self, _event: wx.CommandEvent) -> None:
        deck_content = self._build_deck_text().strip()
        if not deck_content:
            wx.MessageBox("Load a deck first.", "Save Deck", wx.OK | wx.ICON_INFORMATION)
            return
        default_name = "saved_deck"
        current_deck = self.deck_repo.get_current_deck()
        if current_deck:
            default_name = format_deck_name(current_deck).replace(" | ", "_")
        dlg = wx.TextEntryDialog(self, "Deck name:", "Save Deck", default_name=default_name)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        deck_name = dlg.GetValue().strip() or default_name
        dlg.Destroy()

        safe_name = sanitize_filename(deck_name)
        file_path = DECK_SAVE_DIR / f"{safe_name}.txt"
        try:
            with file_path.open("w", encoding="utf-8") as fh:
                fh.write(deck_content)
        except OSError as exc:  # pragma: no cover
            wx.MessageBox(f"Failed to write deck file:\n{exc}", "Save Deck", wx.OK | wx.ICON_ERROR)
            return

        try:
            deck_id = self.deck_repo.save_to_db(
                deck_name=deck_name,
                deck_content=deck_content,
                format_type=self.current_format,
                archetype=current_deck.get("name") if current_deck else None,
                player=current_deck.get("player") if current_deck else None,
                source="mtggoldfish" if current_deck else "manual",
                metadata=(current_deck or {}),
            )
            logger.info(f"Deck saved to database: {deck_name} (ID: {deck_id})")
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Deck saved to file but not database: {exc}")
            deck_id = None

        message = f"Deck saved to {file_path}"
        if deck_id:
            message += f"\nDatabase ID: {deck_id}"
        wx.MessageBox(message, "Deck Saved", wx.OK | wx.ICON_INFORMATION)
        self._set_status("Deck saved successfully.")

    # ------------------------------------------------------------------ Data loading ---------------------------------------------------------
    def fetch_archetypes(self, force: bool = False) -> None:
        with self._loading_lock:
            if self.loading_archetypes:
                return
            self.loading_archetypes = True
        self._set_status(f"Loading archetypes for {self.current_format}…")
        self.research_panel.set_loading_state()
        self.deck_repo.clear_decks_list()
        self.deck_list.Clear()
        self._clear_deck_display()
        self.daily_average_button.Disable()
        self.load_button.Disable()
        self.copy_button.Disable()
        self.save_button.Disable()

        def loader(fmt: str):
            return get_archetypes(fmt.lower(), allow_stale=not force)

        _Worker(
            loader,
            self.current_format,
            on_success=self._on_archetypes_loaded,
            on_error=self._on_archetypes_error,
        ).start()

    def _clear_deck_display(self) -> None:
        self.deck_repo.set_current_deck(None)
        self.summary_text.ChangeValue("Select an archetype to view decks.")
        self.zone_cards = {"main": [], "side": [], "out": []}
        self.main_table.set_cards([])
        self.side_table.set_cards([])
        self.out_table.set_cards(self.zone_cards["out"])
        self.deck_repo.set_current_deck_text("")
        self._update_stats("")
        self.deck_notes_panel.clear()
        self.sideboard_guide_panel.clear()
        self.card_inspector_panel.reset()

    def _on_archetypes_loaded(self, items: list[dict[str, Any]]) -> None:
        with self._loading_lock:
            self.loading_archetypes = False
        self.archetypes = sorted(items, key=lambda entry: entry.get("name", "").lower())
        self.filtered_archetypes = list(self.archetypes)
        self._populate_archetype_list()
        self.research_panel.enable_controls()
        count = len(self.archetypes)
        self._set_status(f"Loaded {count} archetypes for {self.current_format}.")
        self.summary_text.ChangeValue(
            f"Select an archetype to view decks.\nLoaded {count} archetypes."
        )

    def _on_archetypes_error(self, error: Exception) -> None:
        with self._loading_lock:
            self.loading_archetypes = False
        self.research_panel.set_error_state()
        self._set_status(f"Error: {error}")
        wx.MessageBox(
            f"Unable to load archetypes:\n{error}", "Archetype Error", wx.OK | wx.ICON_ERROR
        )

    def _populate_archetype_list(self) -> None:
        archetype_names = [item.get("name", "Unknown") for item in self.filtered_archetypes]
        self.research_panel.populate_archetypes(archetype_names)

    def _load_decks_for_archetype(self, archetype: dict[str, Any]) -> None:
        with self._loading_lock:
            if self.loading_decks:
                return
            self.loading_decks = True
        name = archetype.get("name", "Unknown")
        href = archetype.get("href")
        self._set_status(f"Loading decks for {name}…")
        self.deck_list.Clear()
        self.deck_list.Append("Loading…")
        self.deck_list.Disable()
        self.summary_text.ChangeValue(f"{name}\n\nFetching deck results…")

        def loader(identifier: str):
            return get_archetype_decks(identifier)

        _Worker(
            loader,
            href,
            on_success=lambda decks: self._on_decks_loaded(name, decks),
            on_error=self._on_decks_error,
        ).start()

    def _on_decks_loaded(self, archetype_name: str, decks: list[dict[str, Any]]) -> None:
        with self._loading_lock:
            self.loading_decks = False
        self.deck_repo.set_decks_list(decks)
        self.deck_list.Clear()
        if not decks:
            self.deck_list.Append("No decks found.")
            self.deck_list.Disable()
            self._set_status(f"No decks for {archetype_name}.")
            self.summary_text.ChangeValue(f"{archetype_name}\n\nNo deck data available.")
            return
        for deck in decks:
            self.deck_list.Append(format_deck_name(deck))
        self.deck_list.Enable()
        self.daily_average_button.Enable()
        self._present_archetype_summary(archetype_name, decks)
        self._set_status(f"Loaded {len(decks)} decks for {archetype_name}. Select one to inspect.")

    def _on_decks_error(self, error: Exception) -> None:
        with self._loading_lock:
            self.loading_decks = False
        self.deck_list.Clear()
        self.deck_list.Append("Failed to load decks.")
        self._set_status(f"Error loading decks: {error}")
        wx.MessageBox(f"Failed to load deck lists:\n{error}", "Deck Error", wx.OK | wx.ICON_ERROR)

    def _present_archetype_summary(self, archetype_name: str, decks: list[dict[str, Any]]) -> None:
        by_date: dict[str, int] = {}
        for deck in decks:
            date = deck.get("date", "").lower()
            by_date[date] = by_date.get(date, 0) + 1
        latest_dates = sorted(by_date.items(), reverse=True)[:7]
        lines = [archetype_name, "", f"Total decks loaded: {len(decks)}", ""]
        if latest_dates:
            lines.append("Recent activity:")
            for day, count in latest_dates:
                lines.append(f"  {day}: {count} deck(s)")
        else:
            lines.append("No recent deck activity.")
        self.summary_text.ChangeValue("\n".join(lines))

    def _download_and_display_deck(self, deck: dict[str, Any]) -> None:
        deck_number = deck.get("number")
        if not deck_number:
            wx.MessageBox("Deck identifier missing.", "Deck Error", wx.OK | wx.ICON_ERROR)
            return
        self._set_status("Downloading deck…")
        self.load_button.Disable()
        self.copy_button.Disable()
        self.save_button.Disable()

        def worker(number: str):
            download_deck(number)
            return read_curr_deck_file()

        def on_success(content: str):
            self._on_deck_content_ready(content, source="mtggoldfish")
            self.load_button.Enable()

        _Worker(
            worker, deck_number, on_success=on_success, on_error=self._on_deck_download_error
        ).start()

    def _on_deck_download_error(self, error: Exception) -> None:
        self.load_button.Enable()
        self._set_status(f"Deck download failed: {error}")
        wx.MessageBox(f"Failed to download deck:\n{error}", "Deck Download", wx.OK | wx.ICON_ERROR)

    def _on_deck_content_ready(self, deck_text: str, source: str = "manual") -> None:
        self.deck_repo.set_current_deck_text(deck_text)
        stats = self.deck_service.analyze_deck(deck_text)
        self.zone_cards["main"] = [
            {"name": name, "qty": qty} for name, qty in stats["mainboard_cards"]
        ]
        self.zone_cards["side"] = [
            {"name": name, "qty": qty} for name, qty in stats["sideboard_cards"]
        ]
        self.zone_cards["out"] = self._load_outboard_for_current()
        self.main_table.set_cards(self.zone_cards["main"])
        self.side_table.set_cards(self.zone_cards["side"])
        self.out_table.set_cards(self.zone_cards["out"])
        self._update_stats(deck_text)
        self.copy_button.Enable(True)
        self.save_button.Enable(True)
        self._load_notes_for_current()
        self._load_guide_for_current()
        self._set_status(f"Deck ready ({source}).")
        self._show_left_panel("builder")
        self._schedule_settings_save()

    def _has_deck_loaded(self) -> bool:
        return bool(self.zone_cards["main"] or self.zone_cards["side"])

    # ------------------------------------------------------------------ Collection + card data -----------------------------------------------

    def _load_collection_from_cache(self) -> bool:
        """Load collection from cached file without calling bridge. Returns True if loaded."""
        success, info = self.collection_service.load_from_cached_file(DECK_SAVE_DIR)

        if not success:
            self.collection_status_label.SetLabel(
                "No collection found. Click 'Refresh Collection' to fetch from MTGO."
            )
            return False

        # Update UI with collection info
        filepath = info["filepath"]
        card_count = info["card_count"]
        age_hours = info["age_hours"]
        age_str = f"{age_hours}h ago" if age_hours > 0 else "recent"

        self.collection_status_label.SetLabel(
            f"Collection: {filepath.name} ({card_count} entries, {age_str})"
        )
        self.main_table.set_cards(self.zone_cards["main"])
        self.side_table.set_cards(self.zone_cards["side"])
        return True

    def _refresh_collection_inventory(self, force: bool = False) -> None:
        """Fetch collection from MTGO Bridge and export to JSON."""
        self.collection_status_label.SetLabel("Fetching collection from MTGO...")
        logger.info("Fetching collection from MTGO Bridge")

        # Use service to handle the fetch asynchronously
        self.collection_service.refresh_from_bridge_async(
            directory=DECK_SAVE_DIR,
            force=force,
            on_success=lambda filepath, cards: wx.CallAfter(
                self._on_collection_fetched, filepath, cards
            ),
            on_error=lambda error_msg: wx.CallAfter(self._on_collection_fetch_failed, error_msg),
            cache_max_age_seconds=3600,  # 1 hour
        )

    def _on_collection_fetched(self, filepath: Path, cards: list) -> None:
        """Handle successful collection fetch."""
        # If cards list is empty, this was a cache hit - collection is already loaded
        if cards:
            success, info = self.collection_service.load_from_card_list(cards, filepath)
            if not success:
                error = info.get("error", "Unknown error")
                self.collection_status_label.SetLabel(f"Collection load failed: {error}")
                return
            card_count = info["card_count"]
        else:
            # Cache hit - get card count from already-loaded inventory
            card_count = len(self.collection_service.get_inventory())

        self.collection_status_label.SetLabel(f"Collection: {filepath.name} ({card_count} entries)")
        self.main_table.set_cards(self.zone_cards["main"])
        self.side_table.set_cards(self.zone_cards["side"])

    def _on_collection_fetch_failed(self, error_msg: str) -> None:
        """Handle collection fetch failure."""
        self.collection_service.clear_inventory()
        self.collection_status_label.SetLabel(f"Collection fetch failed: {error_msg}")
        logger.warning(f"Collection fetch failed: {error_msg}")

    def _check_and_download_bulk_data(self) -> None:
        """Check if bulk data exists, and download/load in background if needed."""
        needs_download, reason = self.image_service.check_bulk_data_freshness()

        if not needs_download:
            # Data is fresh, just load into memory
            self._load_bulk_data_into_memory()
            return

        # Data is stale or missing - attempt to load cached data while we download
        if not self.image_service.get_bulk_data():
            self._load_bulk_data_into_memory()

        logger.info(f"Bulk data needs update: {reason}")
        self._set_status("Downloading card image database...")

        # Download in background using service
        self.image_service.download_bulk_metadata_async(
            on_success=lambda msg: wx.CallAfter(self._on_bulk_data_downloaded, msg),
            on_error=lambda msg: wx.CallAfter(self._on_bulk_data_failed, msg),
        )

    def _load_bulk_data_into_memory(self, force: bool = False) -> None:
        """Load the compact card printings index in the background."""
        self._set_status("Preparing card printings cache…")

        # Load using service
        started = self.image_service.load_printing_index_async(
            force=force,
            on_success=lambda data, stats: wx.CallAfter(self._on_bulk_data_loaded, data, stats),
            on_error=lambda msg: wx.CallAfter(self._on_bulk_data_load_failed, msg),
        )

        if not started:
            self._set_status("Ready")  # Already loading or loaded

    def _on_bulk_data_loaded(
        self, by_name: dict[str, list[dict[str, Any]]], stats: dict[str, Any]
    ) -> None:
        """Handle successful printings index load."""
        self.image_service.clear_printing_index_loading()
        self.image_service.set_bulk_data(by_name)
        # Update card inspector panel with bulk data
        self.card_inspector_panel.set_bulk_data(by_name)
        self._set_status("Ready")
        logger.info(
            "Printings index ready: {unique} names / {total} printings",
            unique=stats.get("unique_names"),
            total=stats.get("total_printings"),
        )

    def _on_bulk_data_load_failed(self, error_msg: str) -> None:
        """Handle printings index loading failure."""
        self.image_service.clear_printing_index_loading()
        self._set_status("Ready")
        logger.warning(f"Card printings index load failed: {error_msg}")

    def _on_bulk_data_downloaded(self, msg: str) -> None:
        """Handle successful bulk data download."""
        self._set_status("Card image database downloaded, indexing printings…")
        logger.info(f"Bulk data downloaded: {msg}")
        # Now rebuild the printings index
        self._load_bulk_data_into_memory(force=True)

    def _on_bulk_data_failed(self, error_msg: str) -> None:
        """Handle bulk data download failure."""
        self._set_status("Ready")
        logger.warning(f"Bulk data download failed: {error_msg}")

    def _owned_status(self, name: str, required: int) -> tuple[str, wx.Colour]:
        collection_inventory = self.collection_service.get_inventory()
        if not collection_inventory:
            return ("Owned —", SUBDUED_TEXT)
        have = collection_inventory.get(name.lower(), 0)
        if have >= required:
            return (f"Owned {have}/{required}", wx.Colour(120, 200, 120))
        if have > 0:
            return (f"Owned {have}/{required}", wx.Colour(230, 200, 90))
        return ("Owned 0", wx.Colour(230, 120, 120))

    # ------------------------------------------------------------------ Zone editing ---------------------------------------------------------
    def _handle_zone_delta(self, zone: str, name: str, delta: int) -> None:
        import math

        cards = self.zone_cards.get(zone, [])
        for entry in cards:
            if entry["name"].lower() == name.lower():
                current_qty = entry["qty"]
                # If current quantity is fractional, round it appropriately
                if isinstance(current_qty, float) and not current_qty.is_integer():
                    if delta > 0:
                        # Adding: round up to next integer, then add delta
                        current_qty = math.ceil(current_qty)
                    else:
                        # Removing: round down to previous integer, then subtract delta
                        current_qty = math.floor(current_qty)

                entry["qty"] = max(0, current_qty + delta)
                if entry["qty"] == 0:
                    cards.remove(entry)
                break
        else:
            if delta > 0:
                cards.append({"name": name, "qty": delta})
        cards.sort(key=lambda item: item["name"].lower())
        self.zone_cards[zone] = cards
        self._after_zone_change(zone)

    def _handle_zone_remove(self, zone: str, name: str) -> None:
        cards = self.zone_cards.get(zone, [])
        self.zone_cards[zone] = [entry for entry in cards if entry["name"].lower() != name.lower()]
        self._after_zone_change(zone)

    def _handle_zone_add(self, zone: str) -> None:
        if zone == "out":
            main_cards = [entry["name"] for entry in self.zone_cards.get("main", [])]
            existing = {entry["name"].lower() for entry in self.zone_cards.get("out", [])}
            candidates = [name for name in main_cards if name.lower() not in existing]
            if not candidates:
                wx.MessageBox(
                    "All mainboard cards are already in the outboard list.",
                    "Outboard",
                    wx.OK | wx.ICON_INFORMATION,
                )
                return
            dlg = wx.SingleChoiceDialog(
                self, "Select a mainboard card eligible for sideboarding.", "Outboard", candidates
            )
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            selection = dlg.GetStringSelection()
            dlg.Destroy()
            qty = next(
                (entry["qty"] for entry in self.zone_cards["main"] if entry["name"] == selection), 1
            )
            self.zone_cards.setdefault("out", []).append({"name": selection, "qty": qty})
            self.zone_cards["out"].sort(key=lambda item: item["name"].lower())
            self._after_zone_change("out")
            return

        dlg = wx.TextEntryDialog(
            self, f"Add card to {ZONE_TITLES.get(zone, zone)} (format: 'Qty Card Name')", "Add Card"
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        value = dlg.GetValue().strip()
        dlg.Destroy()
        if not value:
            return
        parts = value.split(" ", 1)
        try:
            qty = int(parts[0]) if len(parts) > 1 else 1
        except ValueError:
            qty = 1
        name = parts[1].strip() if len(parts) > 1 else value
        if not name:
            return
        self.zone_cards.setdefault(zone, []).append({"name": name, "qty": max(1, qty)})
        self.zone_cards[zone].sort(key=lambda item: item["name"].lower())
        self._after_zone_change(zone)

    def _after_zone_change(self, zone: str) -> None:
        if zone == "main":
            self.main_table.set_cards(self.zone_cards["main"])
        elif zone == "side":
            self.side_table.set_cards(self.zone_cards["side"])
        else:
            self.out_table.set_cards(self.zone_cards["out"])
            self._persist_outboard_for_current()
        deck_text = self._build_deck_text()
        self.deck_repo.set_current_deck_text(deck_text)
        self._update_stats(deck_text)
        self.copy_button.Enable(self._has_deck_loaded())
        self.save_button.Enable(self._has_deck_loaded())
        self._schedule_settings_save()

    # ------------------------------------------------------------------ Card inspector -----------------------------------------------------
    def _handle_card_focus(self, zone: str, card: dict[str, Any] | None) -> None:
        if card is None:
            if self.card_inspector_panel.active_zone == zone:
                self.card_inspector_panel.reset()
            return
        self._collapse_other_zone_tables(zone)
        # Load metadata if possible
        meta = self._get_card_metadata(card["name"])
        self.card_inspector_panel.update_card(card, zone=zone, meta=meta)

    def _collapse_other_zone_tables(self, active_zone: str) -> None:
        tables = {
            "main": self.main_table,
            "side": self.side_table,
            "out": self.out_table,
        }
        for zone, table in tables.items():
            if zone == active_zone:
                continue
            table.collapse_active()

    def _get_card_metadata(self, card_name: str) -> dict[str, Any] | None:
        """Get card metadata from the card manager if available."""
        card_manager = self.card_repo.get_card_manager()
        if not card_manager:
            return None
        return card_manager.get_card(card_name)

    # ------------------------------------------------------------------ Stats + notes --------------------------------------------------------
    def _update_stats(self, deck_text: str) -> None:
        """Update stats display using the DeckStatsPanel."""
        self.deck_stats_panel.update_stats(deck_text, self.zone_cards)

    def _load_notes_for_current(self) -> None:
        """Load notes for the current deck into the notes panel."""
        key = self._current_deck_key()
        note = self.deck_notes_store.get(key, "")
        self.deck_notes_panel.set_notes(note)

    def _save_current_notes(self) -> None:
        """Save notes from the notes panel."""
        key = self._current_deck_key()
        notes = self.deck_notes_panel.get_notes()
        self.deck_notes_store[key] = notes
        self._save_store(NOTES_STORE, self.deck_notes_store)
        self._set_status("Deck notes saved.")

    # ------------------------------------------------------------------ Guide / notes helpers ------------------------------------------------
    def _load_store(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON at {path}; ignoring store")
            return {}

    def _save_store(self, path: Path, data: dict[str, Any]) -> None:
        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Failed to write {path}: {exc}")

    # ------------------------------------------------------------------ Daily average --------------------------------------------------------
    def _build_daily_average_deck(self) -> None:
        today = time.strftime("%Y-%m-%d").lower()
        todays_decks = [
            deck
            for deck in self.deck_repo.get_decks_list()
            if today in deck.get("date", "").lower()
        ]

        if not todays_decks:
            wx.MessageBox(
                "No decks from today found for this archetype.",
                "Daily Average",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        with self._loading_lock:
            self.loading_daily_average = True
        self.daily_average_button.Disable()
        self._set_status("Building daily average deck…")
        progress_dialog = wx.ProgressDialog(
            "Daily Average",
            "Downloading decks…",
            maximum=len(todays_decks),
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME,
        )

        def worker(rows: list[dict[str, Any]]):
            buffer: dict[str, float] = {}
            for index, deck in enumerate(rows, start=1):
                download_deck(deck["number"])
                deck_content = read_curr_deck_file()
                buffer = self.deck_service.add_deck_to_buffer(buffer, deck_content)
                wx.CallAfter(progress_dialog.Update, index, f"Processed {index}/{len(rows)} decks…")
            return buffer

        def on_success(buffer: dict[str, float]):
            progress_dialog.Destroy()
            with self._loading_lock:
                self.loading_daily_average = False
            self.daily_average_button.Enable()
            deck_text = self.deck_service.render_average_deck(buffer, len(todays_decks))
            self._on_deck_content_ready(deck_text, source="average")

        def on_error(error: Exception):
            progress_dialog.Destroy()
            with self._loading_lock:
                self.loading_daily_average = False
            self.daily_average_button.Enable()
            wx.MessageBox(
                f"Failed to build daily average:\n{error}", "Daily Average", wx.OK | wx.ICON_ERROR
            )
            self._set_status(f"Daily average failed: {error}")

        _Worker(worker, todays_decks, on_success=on_success, on_error=on_error).start()

    def ensure_card_data_loaded(self) -> None:
        """Ensure card data is loaded in background if not already loading/loaded."""
        if self.card_repo.get_card_manager() or self.card_repo.is_card_data_loading():
            return
        self.card_repo.set_card_data_loading(True)
        self._set_status("Loading card database...")

        def worker():
            from utils.card_data import load_card_manager

            return load_card_manager()

        def on_success(manager: CardDataManager):
            self.card_repo.set_card_manager(manager)
            # Update panels with card manager
            self.card_inspector_panel.set_card_manager(manager)
            self.deck_stats_panel.set_card_manager(manager)
            self.card_repo.set_card_data_loading(False)
            self.card_repo.set_card_data_ready(True)
            self._set_status("Card database loaded")

        def on_error(error: Exception):
            self.card_repo.set_card_data_loading(False)
            logger.error(f"Failed to load card data: {error}")
            self._set_status(f"Card database load failed: {error}")
            wx.MessageBox(
                f"Failed to load card database:\n{error}",
                "Card Data Error",
                wx.OK | wx.ICON_ERROR,
            )

        _Worker(worker, on_success=on_success, on_error=on_error).start()

    def _on_builder_search(self) -> None:
        """Handle search button click from builder panel."""
        card_manager = self.card_repo.get_card_manager()
        if not card_manager:
            if not self.card_repo.is_card_data_loading():
                self.ensure_card_data_loaded()
            if not self.card_data_dialogs_disabled:
                wx.MessageBox(
                    "Card database is still loading. Please try again in a moment.",
                    "Card Search",
                    wx.OK | wx.ICON_INFORMATION,
                )
            return

        # Get filters from the panel
        filters = self.builder_panel.get_filters()

        # Validate mana value if provided
        mv_value_text = filters.get("mv_value", "")
        if mv_value_text:
            try:
                float(mv_value_text)
            except ValueError:
                wx.MessageBox("Mana value must be numeric.", "Card Search", wx.OK | wx.ICON_WARNING)
                return

        # Perform search using service
        results = self.search_service.search_with_builder_filters(filters, card_manager)

        # Update panel with results
        self.builder_panel.update_results(results)

    def _on_builder_clear(self) -> None:
        """Handle clear button click from builder panel."""
        self.builder_panel.clear_filters()

    def _on_builder_result_selected(self, idx: int) -> None:
        """Handle result selection from builder panel."""
        meta = self.builder_panel.get_result_at_index(idx)
        if not meta:
            return
        faux_card = {"name": meta.get("name", "Unknown"), "qty": 1}
        self.card_inspector_panel.update_card(faux_card, zone=None, meta=meta)

    # ------------------------------------------------------------------ Helpers --------------------------------------------------------------
    def _build_deck_text(self) -> str:
        if not self.zone_cards["main"] and not self.zone_cards["side"]:
            return ""
        lines: list[str] = []
        for entry in self.zone_cards["main"]:
            lines.append(f"{entry['qty']} {entry['name']}")
        if self.zone_cards["side"]:
            lines.append("")
            lines.append("Sideboard")
            for entry in self.zone_cards["side"]:
                lines.append(f"{entry['qty']} {entry['name']}")
        return "\n".join(lines).strip()

    def _current_deck_key(self) -> str:
        current_deck = self.deck_repo.get_current_deck()
        if current_deck:
            return current_deck.get("href") or current_deck.get("name", "manual").lower()
        return "manual"

    def _widget_exists(self, window: wx.Window | None) -> bool:
        if window is None:
            return False
        try:
            return bool(window.IsShown())
        except wx.PyDeadObjectError:
            return False

    def _open_child_window(
        self, attr: str, window_class: type, title: str, *args, **kwargs
    ) -> None:
        """Generic factory method for opening child windows."""
        existing = getattr(self, attr, None)
        if self._widget_exists(existing):
            existing.Raise()
            return
        try:
            window = window_class(self, *args, **kwargs)
            window.Bind(wx.EVT_CLOSE, lambda evt: self._handle_child_close(evt, attr))
            window.Show()
            setattr(self, attr, window)
        except Exception as exc:
            logger.error(f"Failed to open {title.lower()}: {exc}")
            wx.MessageBox(
                f"Unable to open {title.lower()}:\n{exc}",
                title,
                wx.OK | wx.ICON_ERROR,
            )

    def open_opponent_tracker(self) -> None:
        self._open_child_window("tracker_window", MTGOpponentDeckSpy, "Opponent Tracker")

    def open_timer_alert(self) -> None:
        self._open_child_window("timer_window", TimerAlertFrame, "Timer Alert")

    def open_match_history(self) -> None:
        self._open_child_window("history_window", MatchHistoryFrame, "Match History")

    def open_metagame_analysis(self) -> None:
        self._open_child_window("metagame_window", MetagameAnalysisFrame, "Metagame Analysis")

    def _handle_child_close(self, event: wx.CloseEvent, attr: str) -> None:
        setattr(self, attr, None)
        event.Skip()

    # ------------------------------------------------------------------ Lifecycle ------------------------------------------------------------
    def on_close(self, event: wx.CloseEvent) -> None:
        if self._save_timer and self._save_timer.IsRunning():
            self._save_timer.Stop()
        self._save_window_settings()
        for attr in ("tracker_window", "timer_window", "history_window"):
            window = getattr(self, attr)
            if self._widget_exists(window):
                window.Destroy()
                setattr(self, attr, None)
        if self.mana_keyboard_window and self.mana_keyboard_window.IsShown():
            self.mana_keyboard_window.Destroy()
            self.mana_keyboard_window = None
        event.Skip()


def launch_app() -> None:
    app = wx.App(False)
    frame = MTGDeckSelectionFrame()
    frame.Show()
    app.MainLoop()


__all__ = ["MTGDeckSelectionFrame", "launch_app"]
