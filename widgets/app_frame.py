import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import wx
from loguru import logger

from controllers.app_controller import get_deck_selector_controller

if TYPE_CHECKING:
    from controllers.app_controller import AppController

from utils.card_data import CardDataManager
from utils.game_constants import FORMAT_OPTIONS
from utils.mana_icon_factory import ManaIconFactory
from utils.paths import CACHE_DIR, CONFIG_FILE, DECKS_DIR
from utils.stylize import stylize_listbox, stylize_textctrl
from utils.ui_constants import (
    DARK_BG,
    DARK_PANEL,
    LIGHT_TEXT,
    SUBDUED_TEXT,
)
from utils.ui_helpers import open_child_window
from widgets.buttons.deck_action_buttons import DeckActionButtons
from widgets.buttons.toolbar_buttons import ToolbarButtons
from widgets.dialogs.image_download_dialog import show_image_download_dialog
from widgets.handlers.card_table_panel_handler import CardTablePanelHandler
from widgets.handlers.deck_selector_handlers import AppEventHandlers
from widgets.handlers.sideboard_guide_handlers import SideboardGuideHandlers
from widgets.identify_opponent import MTGOpponentDeckSpy
from widgets.mana_keyboard import ManaKeyboardFrame, open_mana_keyboard
from widgets.match_history import MatchHistoryFrame
from widgets.metagame_analysis import MetagameAnalysisFrame
from widgets.panels.card_inspector_panel import CardInspectorPanel
from widgets.panels.card_table_panel import CardTablePanel
from widgets.panels.deck_builder_panel import DeckBuilderPanel
from widgets.panels.deck_notes_panel import DeckNotesPanel
from widgets.panels.deck_research_panel import DeckResearchPanel
from widgets.panels.deck_stats_panel import DeckStatsPanel
from widgets.panels.sideboard_guide_panel import SideboardGuidePanel
from widgets.timer_alert import TimerAlertFrame

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


class AppFrame(AppEventHandlers, SideboardGuideHandlers, CardTablePanelHandler, wx.Frame):
    """wxPython-based metagame research + deck builder UI."""

    def __init__(
        self,
        controller: "AppController",
        parent: wx.Window | None = None,
    ):
        """
        Initialize the AppFrame.

        Args:
            controller: AppController instance that manages business logic and state
            parent: Optional parent window
        """
        super().__init__(parent, title="MTGO Deck Research & Builder", size=(1380, 860))

        # Store controller reference - ALL state and business logic goes through this
        self.controller: AppController = controller
        self.card_data_dialogs_disabled = False

        self.sideboard_guide_entries: list[dict[str, str]] = []
        self.sideboard_exclusions: list[str] = []
        self.active_inspector_zone: str | None = None
        self.left_stack: wx.Simplebook | None = None
        self.research_panel: DeckResearchPanel | None = None
        self.builder_panel: DeckBuilderPanel | None = None

        self._save_timer: wx.Timer | None = None
        self.mana_icons = ManaIconFactory()
        self.tracker_window: MTGOpponentDeckSpy | None = None
        self.timer_window: TimerAlertFrame | None = None
        self.history_window: MatchHistoryFrame | None = None
        self.metagame_window: MetagameAnalysisFrame | None = None
        self.mana_keyboard_window: ManaKeyboardFrame | None = None
        self.force_cache_checkbox: wx.CheckBox | None = None
        self.bulk_cache_age_spin: wx.SpinCtrl | None = None

        self._build_ui()
        self._apply_window_preferences()
        self.SetMinSize((1260, 760))
        self.Centre(wx.BOTH)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SIZE, self.on_window_change)
        self.Bind(wx.EVT_MOVE, self.on_window_change)

    # ------------------------------------------------------------------ Properties for state delegation ---------------------------------------
    @property
    def current_format(self) -> str:
        """Delegate to controller."""
        return self.controller.current_format

    @current_format.setter
    def current_format(self, value: str) -> None:
        """Delegate to controller."""
        self.controller.current_format = value

    @property
    def archetypes(self) -> list[dict[str, Any]]:
        """Delegate to controller."""
        return self.controller.archetypes

    @archetypes.setter
    def archetypes(self, value: list[dict[str, Any]]) -> None:
        """Delegate to controller."""
        self.controller.archetypes = value

    @property
    def filtered_archetypes(self) -> list[dict[str, Any]]:
        """Delegate to controller."""
        return self.controller.filtered_archetypes

    @filtered_archetypes.setter
    def filtered_archetypes(self, value: list[dict[str, Any]]) -> None:
        """Delegate to controller."""
        self.controller.filtered_archetypes = value

    @property
    def zone_cards(self) -> dict[str, list[dict[str, Any]]]:
        """Delegate to controller."""
        return self.controller.zone_cards

    @zone_cards.setter
    def zone_cards(self, value: dict[str, list[dict[str, Any]]]) -> None:
        """Delegate to controller."""
        self.controller.zone_cards = value

    @property
    def left_mode(self) -> str:
        """Delegate to controller."""
        return self.controller.left_mode

    @left_mode.setter
    def left_mode(self, value: str) -> None:
        """Delegate to controller."""
        self.controller.left_mode = value

    @property
    def loading_archetypes(self) -> bool:
        """Delegate to controller."""
        return self.controller.loading_archetypes

    @loading_archetypes.setter
    def loading_archetypes(self, value: bool) -> None:
        """Delegate to controller."""
        self.controller.loading_archetypes = value

    @property
    def loading_decks(self) -> bool:
        """Delegate to controller."""
        return self.controller.loading_decks

    @loading_decks.setter
    def loading_decks(self, value: bool) -> None:
        """Delegate to controller."""
        self.controller.loading_decks = value

    @property
    def loading_daily_average(self) -> bool:
        """Delegate to controller."""
        return self.controller.loading_daily_average

    @loading_daily_average.setter
    def loading_daily_average(self, value: bool) -> None:
        """Delegate to controller."""
        self.controller.loading_daily_average = value

    @property
    def _loading_lock(self) -> threading.Lock:
        """Delegate to controller."""
        return self.controller._loading_lock

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
            initial_format=self.controller.current_format,
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

        card_data_controls = self._build_card_data_controls(right_panel)
        right_sizer.Add(card_data_controls, 0, wx.EXPAND | wx.BOTTOM, 10)

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

    def _build_toolbar(self, parent: wx.Window) -> ToolbarButtons:
        """Build the toolbar with utility buttons."""
        return ToolbarButtons(
            parent,
            on_open_opponent_tracker=self.open_opponent_tracker,
            on_open_timer_alert=self.open_timer_alert,
            on_open_match_history=self.open_match_history,
            on_open_metagame_analysis=self.open_metagame_analysis,
            on_load_collection=lambda: self._refresh_collection_inventory(force=True),
            on_download_card_images=lambda: show_image_download_dialog(
                self, self.image_cache, self.image_downloader, self._set_status
            ),
        )

    def _build_card_data_controls(self, parent: wx.Window) -> wx.Panel:
        """Create cached-data preference controls."""
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(DARK_BG)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        panel.SetSizer(sizer)

        self.force_cache_checkbox = wx.CheckBox(panel, label="Use cached card data only")
        self.force_cache_checkbox.SetValue(self.controller.is_forcing_cached_bulk_data())
        self.force_cache_checkbox.Bind(wx.EVT_CHECKBOX, self._on_force_cached_toggle)
        sizer.Add(self.force_cache_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        age_label = wx.StaticText(panel, label="Max cache age (days):")
        age_label.SetForegroundColour(LIGHT_TEXT)
        sizer.Add(age_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        self.bulk_cache_age_spin = wx.SpinCtrl(
            panel,
            min=1,  # BULK_CACHE_MIN_AGE_DAYS
            max=365,  # BULK_CACHE_MAX_AGE_DAYS
        )
        self.bulk_cache_age_spin.SetValue(self.controller.get_bulk_cache_age_days())
        self.bulk_cache_age_spin.Bind(wx.EVT_SPINCTRL, self._on_bulk_age_changed)
        self.bulk_cache_age_spin.Bind(wx.EVT_TEXT, self._on_bulk_age_changed)
        sizer.Add(self.bulk_cache_age_spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        hint = wx.StaticText(panel, label="Higher values reduce download frequency.")
        hint.SetForegroundColour(SUBDUED_TEXT)
        sizer.Add(hint, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.AddStretchSpacer(1)
        return panel

    def _on_force_cached_toggle(self, _event: wx.CommandEvent | None) -> None:
        """Handle cached-only checkbox toggles."""
        enabled = bool(self.force_cache_checkbox and self.force_cache_checkbox.GetValue())
        self.controller.set_force_cached_bulk_data(enabled)
        self._schedule_settings_save()
        self._check_and_download_bulk_data()

    def _on_bulk_age_changed(self, event: wx.CommandEvent | None) -> None:
        """Handle changes to the cache age spinner."""
        if not self.bulk_cache_age_spin:
            return
        self.controller.set_bulk_cache_age_days(self.bulk_cache_age_spin.GetValue())
        self._schedule_settings_save()
        self._check_and_download_bulk_data()
        if event:
            event.Skip()

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
            card_manager=self.controller.card_repo.get_card_manager(),
            mana_icons=self.mana_icons,
        )
        inspector_sizer.Add(self.card_inspector_panel, 1, wx.EXPAND)

        # Keep backward compatibility references (delegate to image service via controller)
        self.image_cache = self.controller.image_service.image_cache
        self.image_downloader = self.controller.image_service.image_downloader

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
            card_manager=self.controller.card_repo.get_card_manager(),
            deck_service=self.controller.deck_service,
        )
        self.deck_tabs.AddPage(self.deck_stats_panel, "Stats")
        # Maintain compatibility with callers/tests that accessed the old label directly.
        self.stats_summary = self.deck_stats_panel.summary_label

        self.sideboard_guide_panel = SideboardGuidePanel(
            self.deck_tabs,
            on_add_entry=self._on_add_guide_entry,
            on_edit_entry=self._on_edit_guide_entry,
            on_remove_entry=self._on_remove_guide_entry,
            on_edit_exclusions=self._on_edit_exclusions,
        )
        self.deck_tabs.AddPage(self.sideboard_guide_panel, "Sideboard Guide")

        self.deck_notes_panel = DeckNotesPanel(
            self.deck_tabs,
            deck_repo=self.controller.deck_repo,
            store_service=self.controller.store_service,
            notes_store=self.controller.deck_notes_store,
            notes_store_path=self.controller.notes_store_path,
            on_status_update=self._set_status,
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
            owned_status_func = self.controller.collection_service.get_owned_status

        table = CardTablePanel(
            self.zone_notebook,
            zone,
            self.mana_icons,
            self.controller.card_repo.get_card_metadata,
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

    def _open_full_mana_keyboard(self) -> None:
        self.mana_keyboard_window = open_mana_keyboard(
            self, self.mana_icons, self.mana_keyboard_window, self._on_mana_keyboard_closed
        )

    def _restore_session_state(self) -> None:
        """Restore session state from controller."""
        state = self.controller.restore_session_state()

        # Restore left panel mode
        self._show_left_panel(state["left_mode"], force=True)

        # Restore zone cards
        if "zone_cards" in state:
            self.main_table.set_cards(self.zone_cards["main"])
            self.side_table.set_cards(self.zone_cards["side"])
            self.out_table.set_cards(self.zone_cards["out"])

        # Restore deck text
        if "deck_text" in state:
            self._update_stats(state["deck_text"])
            self.copy_button.Enable(True)
            self.save_button.Enable(True)

    def _set_status(self, message: str) -> None:
        if self.status_bar:
            self.status_bar.SetStatusText(message)
        logger.info(message)

    # ------------------------------------------------------------------ Window persistence ---------------------------------------------------
    def _save_window_settings(self) -> None:
        """Save window settings to controller."""
        pos = self.GetPosition()
        size = self.GetSize()
        self.controller.save_settings(
            window_size=(size.width, size.height), screen_pos=(pos.x, pos.y)
        )

    def _apply_window_preferences(self) -> None:
        """Apply saved window preferences from controller."""
        state = self.controller.restore_session_state()

        # Apply window size
        if "window_size" in state:
            try:
                width, height = state["window_size"]
                self.SetSize(wx.Size(int(width), int(height)))
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid saved window size")

        # Apply window position
        if "screen_pos" in state:
            try:
                x, y = state["screen_pos"]
                self.SetPosition(wx.Point(int(x), int(y)))
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid saved window position")

    def _schedule_settings_save(self) -> None:
        if self._save_timer is None:
            self._save_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._flush_pending_settings, self._save_timer)
        if self._save_timer.IsRunning():
            self._save_timer.Stop()
        self._save_timer.StartOnce(600)

    def _flush_pending_settings(self, _event: wx.TimerEvent) -> None:
        self._save_window_settings()

    # ------------------------------------------------------------------ Event handlers -------------------------------------------------------
    # Event handlers are now in AppEventHandlers mixin

    # ------------------------------------------------------------------ Data loading ---------------------------------------------------------
    def fetch_archetypes(self, force: bool = False) -> None:
        """Fetch archetypes - delegates to controller with UI callbacks."""
        # Clear UI state immediately
        self.research_panel.set_loading_state()
        self.controller.deck_repo.clear_decks_list()
        self.deck_list.Clear()
        self._clear_deck_display()
        self.daily_average_button.Disable()
        self.load_button.Disable()
        self.copy_button.Disable()
        self.save_button.Disable()

        # Delegate to controller
        self.controller.fetch_archetypes(
            on_success=lambda archetypes: wx.CallAfter(self._on_archetypes_loaded, archetypes),
            on_error=lambda error: wx.CallAfter(self._on_archetypes_error, error),
            on_status=lambda msg: wx.CallAfter(self._set_status, msg),
            force=force,
        )

    def _clear_deck_display(self) -> None:
        """Clear deck display - UI only, no business logic."""
        self.controller.deck_repo.set_current_deck(None)
        self.summary_text.ChangeValue("Select an archetype to view decks.")
        self.zone_cards = {"main": [], "side": [], "out": []}
        self.main_table.set_cards([])
        self.side_table.set_cards([])
        self.out_table.set_cards(self.zone_cards["out"])
        self.controller.deck_repo.set_current_deck_text("")
        self._update_stats("")
        self.deck_notes_panel.clear()
        self.sideboard_guide_panel.clear()
        self.card_inspector_panel.reset()

    def _populate_archetype_list(self) -> None:
        archetype_names = [item.get("name", "Unknown") for item in self.filtered_archetypes]
        self.research_panel.populate_archetypes(archetype_names)

    def _load_decks_for_archetype(self, archetype: dict[str, Any]) -> None:
        """Load decks for archetype - delegates to controller with UI callbacks."""
        name = archetype.get("name", "Unknown")

        # Update UI state immediately
        self.deck_list.Clear()
        self.deck_list.Append("Loading…")
        self.deck_list.Disable()
        self.summary_text.ChangeValue(f"{name}\n\nFetching deck results…")

        # Delegate to controller
        self.controller.load_decks_for_archetype(
            archetype=archetype,
            on_success=lambda archetype_name, decks: wx.CallAfter(
                self._on_decks_loaded, archetype_name, decks
            ),
            on_error=lambda error: wx.CallAfter(self._on_decks_error, error),
            on_status=lambda msg: wx.CallAfter(self._set_status, msg),
        )

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
        """Download and display deck - delegates to controller with UI callbacks."""
        deck_number = deck.get("number")
        if not deck_number:
            wx.MessageBox("Deck identifier missing.", "Deck Error", wx.OK | wx.ICON_ERROR)
            return

        # Update UI state immediately
        self.load_button.Disable()
        self.copy_button.Disable()
        self.save_button.Disable()

        # Delegate to controller
        self.controller.download_and_display_deck(
            deck=deck,
            on_success=lambda content: wx.CallAfter(self._on_deck_download_success, content),
            on_error=lambda error: wx.CallAfter(self._on_deck_download_error, error),
            on_status=lambda msg: wx.CallAfter(self._set_status, msg),
        )

    def _on_deck_download_success(self, content: str) -> None:
        """Handle successful deck download."""
        self._on_deck_content_ready(content, source="mtggoldfish")
        self.load_button.Enable()

    def _has_deck_loaded(self) -> bool:
        return bool(self.zone_cards["main"] or self.zone_cards["side"])

    # ------------------------------------------------------------------ Collection + card data -----------------------------------------------

    def _refresh_collection_inventory(self, force: bool = False) -> None:
        """Fetch collection from MTGO Bridge - delegates to controller."""
        self.collection_status_label.SetLabel("Fetching collection from MTGO...")

        self.controller.refresh_collection_from_bridge(
            directory=DECK_SAVE_DIR,
            on_success=lambda filepath, cards: wx.CallAfter(
                self._on_collection_fetched, filepath, cards
            ),
            on_error=lambda error_msg: wx.CallAfter(self._on_collection_fetch_failed, error_msg),
            on_status=lambda msg: wx.CallAfter(self._set_status, msg),
            force=force,
        )

    def _check_and_download_bulk_data(self) -> None:
        """Check and download bulk data - delegates to controller."""
        self.controller.check_and_download_bulk_data(
            max_age_days=self.controller.get_bulk_cache_age_days(),
            force_cached=self.controller.is_forcing_cached_bulk_data(),
            on_download_needed=lambda reason: logger.info(f"Bulk data needs update: {reason}"),
            on_download_complete=lambda msg: wx.CallAfter(self._on_bulk_data_downloaded, msg),
            on_download_failed=lambda msg: wx.CallAfter(self._on_bulk_data_failed, msg),
            on_status=lambda msg: wx.CallAfter(self._set_status, msg),
        )

    # ------------------------------------------------------------------ Zone editing ---------------------------------------------------------
    def _after_zone_change(self, zone: str) -> None:
        """Handle zone changes - update UI based on zone card data."""
        if zone == "main":
            self.main_table.set_cards(self.zone_cards["main"])
        elif zone == "side":
            self.side_table.set_cards(self.zone_cards["side"])
        else:
            self.out_table.set_cards(self.zone_cards["out"])
            self._persist_outboard_for_current()
        deck_text = self.controller.deck_service.build_deck_text_from_zones(self.zone_cards)
        self.controller.deck_repo.set_current_deck_text(deck_text)
        self._update_stats(deck_text)
        self.copy_button.Enable(self._has_deck_loaded())
        self.save_button.Enable(self._has_deck_loaded())
        self._schedule_settings_save()

    # ------------------------------------------------------------------ Card inspector -----------------------------------------------------
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

    # ------------------------------------------------------------------ Stats + notes --------------------------------------------------------
    def _update_stats(self, deck_text: str) -> None:
        """Update stats display using the DeckStatsPanel."""
        self.deck_stats_panel.update_stats(deck_text, self.zone_cards)

    # ------------------------------------------------------------------ Guide / notes helpers ------------------------------------------------
    # ------------------------------------------------------------------ Daily average --------------------------------------------------------
    def _start_daily_average_build(self) -> None:
        """Start daily average build - delegates to controller with UI callbacks."""
        # Disable button immediately
        self.daily_average_button.Disable()

        # Create progress dialog
        progress_dialog = wx.ProgressDialog(
            "Daily Average",
            "Downloading decks…",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME,
        )

        # Delegate to controller
        can_proceed, message = self.controller.build_daily_average_deck(
            on_success=lambda buffer, deck_count: wx.CallAfter(
                self._on_daily_average_success, buffer, deck_count, progress_dialog
            ),
            on_error=lambda error: wx.CallAfter(
                self._on_daily_average_error, error, progress_dialog
            ),
            on_status=lambda msg: wx.CallAfter(self._set_status, msg),
            on_progress=lambda current, total: wx.CallAfter(
                progress_dialog.Update, current, f"Processed {current}/{total} decks…"
            ),
        )

        if not can_proceed:
            progress_dialog.Close()
            self.daily_average_button.Enable()
            wx.MessageBox(message, "Daily Average", wx.OK | wx.ICON_INFORMATION)
            return

        # Update progress dialog maximum
        progress_dialog.SetRange(int(message.split()[1]))

    def _on_daily_average_success(
        self, buffer: dict[str, float], deck_count: int, progress_dialog: wx.ProgressDialog
    ) -> None:
        """Handle successful daily average build."""
        self.daily_average_button.Enable()
        deck_text = self.controller.deck_service.render_average_deck(buffer, deck_count)
        self._on_deck_content_ready(deck_text, source="average")

        try:
            progress_dialog.Update(deck_count)
            progress_dialog.Close()
        except Exception as dialog_exc:
            logger.error(f"Error closing progress dialog: {dialog_exc}")

    def _on_daily_average_error(self, error: Exception, progress_dialog: wx.ProgressDialog) -> None:
        """Handle daily average build error."""
        logger.error(f"Daily average error: {error}")
        try:
            progress_dialog.Close()
        except Exception:
            pass
        self.daily_average_button.Enable()
        wx.MessageBox(
            f"Failed to build daily average:\n{error}", "Daily Average", wx.OK | wx.ICON_ERROR
        )
        self._set_status(f"Daily average failed: {error}")

    def ensure_card_data_loaded(self) -> None:
        """Ensure card data is loaded in background if not already loading/loaded."""

        def on_success(manager: CardDataManager):
            # Update UI panels with card manager (marshalled to UI thread by controller)
            wx.CallAfter(self.card_inspector_panel.set_card_manager, manager)
            wx.CallAfter(self.deck_stats_panel.set_card_manager, manager)

        def on_error(error: Exception):
            # Show error dialog on UI thread
            wx.CallAfter(
                wx.MessageBox,
                f"Failed to load card database:\n{error}",
                "Card Data Error",
                wx.OK | wx.ICON_ERROR,
            )

        def on_status(message: str):
            # Update status bar on UI thread
            wx.CallAfter(self._set_status, message)

        # Delegate business logic to controller
        self.controller.ensure_card_data_loaded(
            on_success=on_success, on_error=on_error, on_status=on_status
        )

    # ------------------------------------------------------------------ Helpers --------------------------------------------------------------
    def open_opponent_tracker(self) -> None:
        open_child_window(
            self,
            "tracker_window",
            MTGOpponentDeckSpy,
            "Opponent Tracker",
            self._handle_child_close,
        )

    def open_timer_alert(self) -> None:
        open_child_window(
            self,
            "timer_window",
            TimerAlertFrame,
            "Timer Alert",
            self._handle_child_close,
        )

    def open_match_history(self) -> None:
        open_child_window(
            self,
            "history_window",
            MatchHistoryFrame,
            "Match History",
            self._handle_child_close,
        )

    def open_metagame_analysis(self) -> None:
        open_child_window(
            self,
            "metagame_window",
            MetagameAnalysisFrame,
            "Metagame Analysis",
            self._handle_child_close,
        )

    def _handle_child_close(self, event: wx.CloseEvent, attr: str) -> None:
        setattr(self, attr, None)
        event.Skip()

    # ------------------------------------------------------------------ Lifecycle ------------------------------------------------------------
    # Lifecycle handlers are now in AppEventHandlers mixin


def launch_app() -> None:
    """Launch the application using the controller factory pattern."""
    app = wx.App(False)
    controller = get_deck_selector_controller()
    frame = controller.create_frame()
    frame.Show()
    app.MainLoop()


__all__ = ["AppFrame", "launch_app"]
