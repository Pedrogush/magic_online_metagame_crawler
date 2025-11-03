import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, simpledialog
import json
import threading
from pathlib import Path
from loguru import logger
from utils.deck import deck_to_dictionary, add_dicts, analyze_deck
from utils.dbq import (
    save_deck_to_db,
    get_saved_decks,
    delete_saved_deck,
)
from utils import mtgo_bridge
from navigators.mtggoldfish import (
    get_archetypes,
    get_archetype_stats,
    get_archetype_decks,
    download_deck,
)
from widgets.identify_opponent import MTGOpponentDeckSpy
from widgets.metagame_view import MetagameStatsView
from widgets.timer_alert import TimerAlertWindow
from widgets.match_history import MatchHistoryWindow
from utils.paths import (
    CONFIG_FILE,
    DECK_SELECTOR_SETTINGS_FILE,
    CURR_DECK_FILE,
    DECKS_DIR,
)

CARD_SEARCH_PANEL_WIDTH = 420
CARD_SEARCH_LISTBOX_WIDTH = 34
DECK_GRID_COLUMNS = 4

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
COLOR_SCHEME = "bisque"
CS = [
    COLOR_SCHEME + "1",
    COLOR_SCHEME + "2",
    COLOR_SCHEME + "3",
    COLOR_SCHEME + "4",
    COLOR_SCHEME,
]
LEGACY_CONFIG_FILE = Path("config.json")
CONFIG = {}
if CONFIG_FILE.exists():
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as _cfg_file:
            CONFIG = json.load(_cfg_file)
    except json.JSONDecodeError as exc:
        logger.warning(f"Invalid {CONFIG_FILE} ({exc}); using default deck save path")
        CONFIG = {}
elif LEGACY_CONFIG_FILE.exists():
    try:
        with LEGACY_CONFIG_FILE.open("r", encoding="utf-8") as _cfg_file:
            CONFIG = json.load(_cfg_file)
        logger.warning("Loaded legacy config.json from project root; migrating to config/ directory")
        try:
            with CONFIG_FILE.open("w", encoding="utf-8") as fh:
                json.dump(CONFIG, fh, indent=4)
        except OSError as exc:
            logger.warning(f"Failed to write migrated config.json: {exc}")
    except json.JSONDecodeError as exc:
        logger.warning(f"Invalid legacy config.json ({exc}); using default deck save path")
        CONFIG = {}
else:
    logger.warning(f"{CONFIG_FILE} not found; using default deck save path")

default_deck_dir = Path(CONFIG.get("deck_selector_save_path") or DECKS_DIR)
DECK_SAVE_DIR = default_deck_dir.expanduser()
try:
    DECK_SAVE_DIR.mkdir(parents=True, exist_ok=True)
except OSError as exc:
    logger.warning(f"Unable to create deck save directory '{DECK_SAVE_DIR}': {exc}")
CONFIG.setdefault("deck_selector_save_path", str(DECK_SAVE_DIR))

CARD_SEARCH_FORMATS = [
    "Any",
    "standard",
    "pioneer",
    "modern",
    "legacy",
    "vintage",
    "commander",
    "pauper",
    "historic",
    "explorer",
    "alchemy",
    "brawl",
]

CARD_TYPE_FILTERS = [
    "Any",
    "creature",
    "planeswalker",
    "instant",
    "sorcery",
    "artifact",
    "enchantment",
    "battle",
    "land",
]

LEGACY_CURR_DECK_CACHE = Path("cache") / "curr_deck.txt"
LEGACY_CURR_DECK_ROOT = Path("curr_deck.txt")


def label(root, text=" ", color=CS[0]):
    return tk.Label(
        root,
        text=text,
        font=("calibri", 15, "bold"),
        background=color,
        foreground="black",
        borderwidth=2,
        justify="left",
        relief="solid",
    )


def button(root, text, command, color=CS[0], font=("calibri", 13, "bold")):
    return tk.Button(root, text=text, font=font, background=color, command=command)


def b_button(root, text, command, color=CS[1], font=("calibri", 13, "bold"), width=0, height=1):
    kwargs = {"text": text, "font": font, "background": color, "command": command, "height": height}
    if width:
        kwargs["width"] = width
    return tk.Button(root, **kwargs)


def listbox(root, color=CS[0], font=("calibri", 15, "bold")):
    return tk.Listbox(root, selectmode=tk.SINGLE, background=color, foreground="black", font=font)


def frame(root, name, color=CS[3]):
    frame = tk.Frame(root, relief="solid", padx=3, pady=3, background=color, borderwidth=2, border=1)
    if name:
        frame_title = tk.Label(
            frame,
            text=name,
            font=("calibri", 15, "bold"),
            background=CS[2],
            foreground="black",
            relief="solid",
        )
        frame_title.grid(column=0, row=0, sticky="nsew")
    return frame


def b_frame(root, color=CS[1]):
    frame = tk.Frame(root, relief="flat", padx=3, pady=0, background=color, borderwidth=0, height=15)
    return frame


def choose_format_button_config(button):
    button.config(
        font=("calibri", 10, "bold"),
        background=CS[2],
        relief="solid",
        borderwidth=2,
        fg="black",
        disabledforeground=CS[3],
        activebackground=CS[3],
        activeforeground="black",
        highlightbackground=CS[3],
    )
    button["menu"].config(
        font=("calibri", 10, "bold"),
        background=CS[2],
        activebackground=CS[2],
        disabledforeground=CS[3],
        foreground="black",
        activeforeground="black",
        selectcolor="black",
        borderwidth=2,
        relief="solid",
    )


def repopulate_listbox(listbox: tk.Listbox, items: list):
    for item in listbox.get(0, tk.END):
        listbox.delete(0)
    for index, item in enumerate(items):
        listbox.insert(index, item)


def format_deck_name(deck: dict):
    return f"{deck['date']} {deck['player']} {deck['event']} {deck['result']}"


class MTGDeckSelectionWidget:

    def __init__(self, root: tk.Tk):
        self.root: tk.Tk = root
        self.format = tk.StringVar(value="Modern")
        self.window_settings = self._load_window_settings()
        size_settings = self._normalize_window_size(self.window_settings.get("window_size"))
        position_settings = self._normalize_window_position(self.window_settings.get("screen_pos"))
        self.window_size = size_settings
        self.window_position = position_settings
        saved_format = self.window_settings.get("format")
        if saved_format and saved_format in FORMAT_OPTIONS:
            self.format.set(saved_format)
        self.last_looked_at_ts = time.time()
        self.last_seen_deck = ""
        self.updating = False
        self.user_has_edited_deck = False
        self.currently_selected_deck = {}
        self.deck_buffer: dict = {}
        self.decks_added = 0
        self.archetypes = []
        self.archetype_stats = {}
        self.saved_decks = []  # For database saved decks
        self.current_mode = "browse"  # "browse", "saved", or "builder"
        self.loading = False
        self.loading_daily_average = False  # Prevent simultaneous daily average loads
        self.card_manager = None
        self.card_data_ready = False
        self.card_data_loading = False
        self.card_search_results = []
        self.builder_deck = {"main": {}, "side": {}}
        self.saved_decks_popup = None
        self.saved_decks_popup_listbox = None
        self.saved_decks_popup_status = None
        self.saved_decks_popup_data = []
        self.deck_save_dir = DECK_SAVE_DIR
        self.opponent_tracker_window = None
        self.timer_alert_window = None
        self.match_history_window = None
        self.sdk_status_var = tk.StringVar(value="MTGOSDK: checking…")
        self.ui_make_components()
        self._apply_window_preferences()
        self.root.bind("<Configure>", self.on_window_configure)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Load archetypes asynchronously after window is shown
        self.root.after(100, self.lazy_load_archetypes)
        self._schedule_runtime_status_check(initial=True)

    def ui_reset_to_archetype_selection(self):
        self.clear_deck_textboxes()
        self.deck_buffer = {}
        self.decks_added = 0
        self.listbox.unbind("<<ListboxSelect>>")
        self.listbox_button.config(text="Select archetype", command=self.select_archetype, state="normal")

        # Check if archetypes are loaded
        if self.archetypes:
            repopulate_listbox(self.listbox, [archetype["name"] for archetype in self.archetypes])
        else:
            # Archetypes not loaded yet, trigger loading
            self.listbox.delete(0, tk.END)
            self.listbox.insert(0, "⏳ Loading archetypes...")
            self.lazy_load_archetypes()

        if hasattr(self, "reset_button"):
            self.reset_button.grid_forget()
        if getattr(self, "delete_deck_button", None):
            self.delete_deck_button.grid_forget()
            self.delete_deck_button = None
        if hasattr(self, "make_daily_average_deck_button"):
            self.make_daily_average_deck_button.grid_forget()

    def ui_make_components(self):
        self.root.title("MTG Deck Research Browser")
        self.root.resizable(True, True)
        self.ui_create()
        # Don't populate yet - will be done lazily
        self.ui_bind_components()

    def ui_create(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.F_top = frame(self.root, "", color="bisque4")
        self.F_top.grid(column=0, row=0, sticky="nsew")
        self.F_top.grid_columnconfigure(0, weight=0)
        self.F_top.grid_columnconfigure(1, weight=1)
        self.F_top.grid_rowconfigure(1, weight=1)
        self.F_top_left = frame(self.F_top, "Deck Browser", color=CS[1])
        self.F_top_left.columnconfigure(0, weight=1)
        self.F_top_left.columnconfigure(1, weight=0)
        self.F_top_left.rowconfigure(5, weight=1)
        self.F_top_left.grid(column=0, row=1, sticky="nsew")
        self.F_top_right = frame(self.F_top, "Decklist", color=CS[1])
        self.F_top_right.grid(column=1, row=1, sticky="nsew")
        self.F_top_right.grid_columnconfigure(0, weight=1)
        self.F_top_right.rowconfigure(3, weight=1)
        self.F_top_right_top = frame(self.F_top_right, "", color=CS[2])
        self.F_top_right_top.grid(column=0, row=1, sticky="nsew")

        # Add statistics panel
        self.F_stats = frame(self.F_top_right, "Deck Statistics", color=CS[2])
        self.F_stats.grid(column=0, row=0, sticky="nsew")
        self.stats_label = label(self.F_stats, "", color=CS[2])
        self.stats_label.config(font=("calibri", 12), justify="left", anchor="w")
        self.stats_label.grid(column=0, row=0, sticky="nsew", padx=5, pady=5)
        self.F_stats.grid_remove()  # Hidden by default

        self.card_detail_frame = frame(self.F_top_right, "Card Details", color=CS[2])
        self.card_detail_frame.grid(column=0, row=2, sticky="nsew")
        self.card_detail_frame.grid_remove()
        self.card_detail_frame.rowconfigure(0, weight=1)
        self.card_detail_frame.columnconfigure(0, weight=1)
        self.card_detail_text = tk.Text(self.card_detail_frame, height=8, wrap="word", background=CS[2], foreground="black", font=("calibri", 11))
        self.card_detail_text.grid(column=0, row=0, sticky="nsew", padx=4, pady=4)
        self.card_detail_text.config(state="disabled")
        self.card_add_buttons = tk.Frame(self.card_detail_frame, background=CS[2], pady=4)
        self.card_add_buttons.grid(column=0, row=1, sticky="ew")
        self.builder_add_main_button = tk.Button(self.card_add_buttons, text="Add to Mainboard", command=lambda: self.builder_add_card("main"), state="disabled")
        self.builder_add_main_button.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.builder_add_side_button = tk.Button(self.card_add_buttons, text="Add to Sideboard", command=lambda: self.builder_add_card("side"), state="disabled")
        self.builder_add_side_button.pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.F_tab = ttk.Notebook(self.F_top_right)
        self.F_tab.grid(column=0, row=3, sticky="nsew")
        deck_tab = tk.Frame(self.F_tab, background=CS[2])
        deck_tab.grid_columnconfigure(0, weight=1)
        deck_tab.grid_rowconfigure(0, weight=1)
        self.F_tab.add(deck_tab, text="Deck Builder")
        self.metagame_view = MetagameStatsView(self.F_tab)
        self.F_tab.add(self.metagame_view, text="Metagame")

        self.F_top_textbox = frame(deck_tab, "", color=CS[2])
        self.F_top_textbox.grid(column=0, row=0, sticky="nsew")
        self.F_top_textbox.rowconfigure(0, weight=1)
        self.F_top_textbox.rowconfigure(1, weight=1)

        self.bottom_toolbar = tk.Frame(self.root, background=CS[3], padx=8, pady=6, relief="solid", borderwidth=1)
        self.bottom_toolbar.grid(column=0, row=2, sticky="ew")
        self.bottom_toolbar.columnconfigure(0, weight=0)
        self.bottom_toolbar.columnconfigure(1, weight=1)
        self.bottom_toolbar.columnconfigure(2, weight=0)
        self.bottom_toolbar.columnconfigure(3, weight=0)
        self.bottom_toolbar.columnconfigure(4, weight=0)
        self.bottom_toolbar.columnconfigure(5, weight=0)
        self.bottom_toolbar.columnconfigure(6, weight=0)
        self.bottom_toolbar.columnconfigure(4, weight=0)

        self.save_deck_button = button(self.F_top_right_top, "Save deck", self.save_deck_as)
        self.save_deck_button.grid(column=0, row=0, sticky="nsew")
        self.add_deck_to_buffer_button = button(self.F_top_right_top, "Add deck to buffer", self.add_deck_to_buffer)
        self.add_deck_to_buffer_button.grid(column=1, row=0, sticky="nsew")
        self.make_average_deck_button = button(self.F_top_right_top, "Mean of buffer", self.make_average_deck)
        self.make_average_deck_button.grid(column=2, row=0, sticky="nsew")
        self.copy_deck_button = button(self.F_top_right_top, "Copy to Clipboard", self.copy_deck_to_clipboard, color=CS[0])
        self.copy_deck_button.grid(column=3, row=0, sticky="nsew")

        # Add visualize button (initially hidden, shown in saved decks mode)
        self.visualize_button = button(self.F_top_right_top, "📊 Show Stats", self.toggle_statistics_panel, color=CS[1])
        self.visualize_button.grid(column=5, row=0, sticky="nsew")
        self.visualize_button.grid_remove()  # Hidden initially
        self.load_saved_into_builder_button = button(self.F_top_right_top, "Load Saved ➜ Builder", self.load_selected_saved_into_builder, color=CS[1])
        self.load_saved_into_builder_button.grid(column=6, row=0, sticky="nsew")
        self.load_saved_into_builder_button.grid_remove()

        # Mode toggle buttons
        self.browse_mode_button = button(self.F_top_left, "Browse MTGGoldfish", self.switch_to_browse_mode, color=CS[2])
        self.browse_mode_button.grid(column=0, row=1, sticky="nsew")
        self.saved_decks_button = button(self.F_top_left, "Saved Decks", self.switch_to_saved_mode, color=CS[0])
        self.saved_decks_button.grid(column=0, row=2, sticky="nsew")
        self.builder_mode_button = button(self.F_top_left, "Deck Builder", self.switch_to_builder_mode, color=CS[0])
        self.builder_mode_button.grid(column=0, row=3, sticky="nsew")

        self.listbox_button = button(self.F_top_left, "Select archetype", self.select_archetype)
        self.listbox_button.grid(column=0, row=4, sticky="nsew")

        self.builder_controls_frame = tk.Frame(self.F_top_left, background=CS[2], padx=4, pady=4, relief="solid", borderwidth=1)
        self.builder_controls_frame.grid(column=0, row=4, sticky="nsew")
        self.builder_controls_frame.grid_remove()
        self.card_search_var = tk.StringVar()
        self.card_search_entry = tk.Entry(self.builder_controls_frame, textvariable=self.card_search_var, font=("calibri", 12))
        self.card_search_entry.grid(column=0, row=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.card_search_entry.bind("<Return>", lambda _: self.perform_card_search())
        self.card_format_var = tk.StringVar(value=CARD_SEARCH_FORMATS[0])
        self.card_type_var = tk.StringVar(value=CARD_TYPE_FILTERS[0])
        self.card_format_menu = ttk.Combobox(self.builder_controls_frame, textvariable=self.card_format_var, values=CARD_SEARCH_FORMATS, state="readonly")
        self.card_format_menu.grid(column=0, row=1, sticky="ew", padx=(0, 2))
        self.card_type_menu = ttk.Combobox(self.builder_controls_frame, textvariable=self.card_type_var, values=CARD_TYPE_FILTERS, state="readonly")
        self.card_type_menu.grid(column=1, row=1, sticky="ew", padx=(2, 0))
        self.card_search_button = tk.Button(self.builder_controls_frame, text="Search", command=self.perform_card_search)
        self.card_search_button.grid(column=0, row=2, columnspan=2, sticky="ew", pady=(4, 0))
        self.open_saved_decks_button = tk.Button(self.builder_controls_frame, text="Open Saved Decks", command=self.open_saved_decks_dialog)
        self.open_saved_decks_button.grid(column=0, row=3, columnspan=2, sticky="ew", pady=(4, 0))
        self.builder_status_var = tk.StringVar(value="")
        self.card_status_label = tk.Label(self.builder_controls_frame, textvariable=self.builder_status_var, anchor="w", background=CS[2], fg="#555")
        self.card_status_label.grid(column=0, row=4, columnspan=2, sticky="ew", pady=(4, 0))
        self.builder_controls_frame.columnconfigure(0, weight=1)
        self.builder_controls_frame.columnconfigure(1, weight=1)
        self.listbox = tk.Listbox(
            self.F_top_left,
            selectmode=tk.SINGLE,
            background=CS[4],
            foreground="black",
            font=("calibri", 15, "bold"),
            justify="left",
            activestyle="none",
        )
        self.listbox.grid(column=0, row=5, sticky="nsew")
        self.listbox_scrollbar = tk.Scrollbar(self.F_top_left, orient="vertical")
        self.listbox_scrollbar.grid(column=1, row=5, sticky="nsew")
        self.listbox.config(yscrollcommand=self.listbox_scrollbar.set)
        self.listbox_scrollbar.config(command=self.listbox.yview)

        self.listbox_font = tkfont.Font(root=self.root, font=self.listbox.cget("font"))
        self.deck_row_font = tkfont.Font(root=self.root, family="calibri", size=15, weight="bold")
        self._search_width_set = False
        self.row_button_width = self._compute_row_button_width()

        self.F_top_textbox.columnconfigure(0, weight=1)
        self.F_top_textbox.rowconfigure(0, weight=1)
        self.F_top_textbox.rowconfigure(1, weight=1)

        self.main_deck_container = frame(self.F_top_textbox, "Mainboard", color=CS[2])
        self.main_deck_container.grid(column=0, row=0, sticky="nsew", padx=4, pady=(4, 2))
        self.main_deck_container.columnconfigure(0, weight=1)
        self.main_deck_container.rowconfigure(1, weight=1)

        self.side_deck_container = frame(self.F_top_textbox, "Sideboard", color=CS[2])
        self.side_deck_container.grid(column=0, row=1, sticky="nsew", padx=4, pady=(2, 4))
        self.side_deck_container.columnconfigure(0, weight=1)
        self.side_deck_container.rowconfigure(1, weight=1)
        self.zone_views = {}
        self.zone_lines = {"main": [], "side": []}
        self.q_btn_frames = {"main": [], "side": []}
        self._init_zone_view(self.main_deck_container, "main")
        self._init_zone_view(self.side_deck_container, "side")

        tk.Label(
            self.bottom_toolbar,
            text="Format:",
            background=CS[3],
            font=("calibri", 12, "bold"),
        ).grid(column=0, row=0, sticky="w")
        self.choose_format_button = tk.OptionMenu(
            self.bottom_toolbar,
            self.format,
            FORMAT_OPTIONS[0],
            *FORMAT_OPTIONS[1:],
            command=lambda x: self.choose_format_button_clicked(),
        )
        self.choose_format_button.grid(column=1, row=0, sticky="w")
        choose_format_button_config(self.choose_format_button)

        opp_btn = tk.Button(
            self.bottom_toolbar,
            text="Launch Opponent Tracker",
            command=self.launch_opponent_tracker,
            background=CS[2],
        )
        opp_btn.grid(column=2, row=0, sticky="ew", padx=(12, 6))

        timer_btn = tk.Button(
            self.bottom_toolbar,
            text="Open Timer Alert",
            command=self.open_timer_alert,
            background=CS[2],
        )
        timer_btn.grid(column=3, row=0, sticky="ew")

        match_btn = tk.Button(
            self.bottom_toolbar,
            text="Match History",
            command=self.open_match_history,
            background=CS[2],
        )
        match_btn.grid(column=4, row=0, sticky="ew", padx=(6, 0))

        collection_btn = tk.Button(
            self.bottom_toolbar,
            text="Export Collection",
            command=self.export_collection_snapshot,
            background=CS[2],
        )
        collection_btn.grid(column=5, row=0, sticky="ew", padx=(6, 0))

        status_label = tk.Label(self.bottom_toolbar, textvariable=self.sdk_status_var, background=CS[3], font=("calibri", 9, "italic"))
        status_label.grid(column=6, row=0, sticky="e", padx=(10, 0))
        self.set_mode_button_states("browse")

    def _schedule_runtime_status_check(self, initial: bool = False):
        def worker():
            if initial:
                ready, error = mtgo_bridge.ensure_runtime_ready()
            else:
                ready, error = mtgo_bridge.runtime_status()

            def update():
                if ready:
                    self.sdk_status_var.set("MTGOSDK: ready")
                else:
                    message = error or "loading"
                    self.sdk_status_var.set(f"MTGOSDK: {message}")
                interval = 60000 if ready else 5000
                self.root.after(interval, lambda: self._schedule_runtime_status_check(initial=False))

            self.root.after(0, update)

        threading.Thread(target=worker, daemon=True).start()
        if initial:
            threading.Thread(target=lambda: mtgo_bridge.ensure_runtime_ready(), daemon=True).start()

    def _init_zone_view(self, container, zone):
        canvas = tk.Canvas(
            container,
            background=CS[1],
            highlightthickness=0,
            bd=0,
        )
        canvas.grid(column=0, row=1, sticky="nsew")
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.grid(column=1, row=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        inner = tk.Frame(canvas, background=CS[1])
        inner.grid_columnconfigure(0, weight=1)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _sync_scrollregion(_event, c=canvas):
            c.configure(scrollregion=c.bbox("all"))

        def _sync_width(event, c=canvas, wid=window_id, z=zone):
            c.itemconfigure(wid, width=event.width)
            self._request_zone_relayout(z)

        inner.bind("<Configure>", _sync_scrollregion)
        canvas.bind("<Configure>", _sync_width)

        self.zone_lines.setdefault(zone, [])
        self.q_btn_frames.setdefault(zone, [])
        self.zone_views[zone] = {
            "canvas": canvas,
            "frame": inner,
            "scrollbar": scrollbar,
            "window_id": window_id,
            "rows": [],
            "columns": 0,
            "pending_layout": False,
        }

    def _compute_row_button_width(self):
        temp = tk.Frame(self.root)
        widths = []
        sample_buttons = []
        for symbol in ("+", "-", "X"):
            btn = b_button(temp, symbol, lambda: None, color=CS[2], font=("verdana", 9, "bold"), width=2)
            btn.pack(side="left", padx=1)
            sample_buttons.append(btn)
        temp.update_idletasks()
        for btn in sample_buttons:
            widths.append(btn.winfo_reqwidth())
            btn.destroy()
        temp.destroy()
        button_spacing = 6  # approximate total horizontal padding between buttons
        label_padding = 12  # left/right padding before label text
        return sum(widths) + button_spacing + label_padding

    def choose_format_button_clicked(self):
        self.lazy_load_archetypes()
        self.ui_reset_to_archetype_selection()
        self.save_config()

    def lazy_load_archetypes(self):
        """Load archetypes in background thread to avoid blocking UI"""
        if self.loading:
            logger.debug("Already loading archetypes, skipping")
            return

        self.loading = True
        self.listbox.delete(0, tk.END)
        self.listbox.insert(0, "⏳ Loading archetypes...")
        self.listbox_button.config(state="disabled")

        def load_in_background():
            mtg_format = self.format.get()
            attempts = 3
            delay = 2
            last_error_message = ""

            for attempt in range(1, attempts + 1):
                try:
                    logger.info(f"Loading archetypes for {mtg_format} (attempt {attempt}/{attempts})...")
                    archetypes = get_archetypes(mtg_format)
                    archetype_stats = get_archetype_stats(mtg_format)
                    self.root.after(0, lambda data=archetypes, stats=archetype_stats: self.on_archetypes_loaded(data, stats))
                    return
                except Exception as exc:  # Retry on all exceptions
                    last_error_message = str(exc)
                    logger.error(f"Failed to load archetypes (attempt {attempt}/{attempts}): {exc}")
                    if attempt < attempts:
                        retry_msg = f"Network error, retrying ({attempt}/{attempts})..."
                        self.root.after(0, lambda msg=retry_msg: self._update_archetype_retry_status(msg))
                        time.sleep(delay)
                        delay = min(delay * 2, 10)
                    else:
                        break

            self.root.after(0, lambda msg=last_error_message: self.on_archetypes_error(msg))

        # Start background thread
        thread = threading.Thread(target=load_in_background, daemon=True)
        thread.start()

    def on_archetypes_loaded(self, archetypes, archetype_stats):
        """Called on main thread when archetypes are loaded"""
        self.archetypes = archetypes
        self.archetype_stats = archetype_stats
        self.loading = False

        # Only update if we're still in browse mode
        if self.current_mode == "browse":
            # Update listbox
            self.listbox.delete(0, tk.END)
            for index, archetype in enumerate(self.archetypes):
                self.listbox.insert(index, archetype["name"])

            self.listbox_button.config(text="Select archetype", command=self.select_archetype, state="normal")

        logger.info(f"Loaded {len(self.archetypes)} archetypes")

    def on_archetypes_error(self, error_msg):
        """Called on main thread if loading fails"""
        self.loading = False

        # Only update if we're still in browse mode
        if self.current_mode == "browse":
            self.listbox.delete(0, tk.END)
            self.listbox.insert(0, f"❌ Error: {error_msg[:50]}")
            self.listbox.insert(1, "Click 'Select archetype' to retry")
            self.listbox_button.config(text="Select archetype", command=self.select_archetype, state="normal")

        self.builder_status_var.set("Failed to load archetypes. Check your connection and retry.")

    def _update_archetype_retry_status(self, message):
        if self.current_mode != "browse":
            return
        self.listbox.delete(0, tk.END)
        self.listbox.insert(0, message)
        self.listbox.insert(1, "")

    def save_deck_as(self):
        """Save deck to both database and file"""
        logger.debug(self.currently_selected_deck)

        # Get deck content
        deck_content = self.get_deck_text().strip()
        if not deck_content:
            messagebox.showwarning("Empty Deck", "Cannot save an empty deck")
            return

        # Determine deck name and metadata
        if not self.currently_selected_deck:
            date = time.strftime("%Y-%m-%d-%H-%M-%S")
            default_name = f"edited_deck_{date}"
            deck_name = simpledialog.askstring("Save Deck", "Enter deck name:", initialvalue=default_name)
            if not deck_name:
                return  # User cancelled

            metadata = {"date": date}
            source = "manual"
            archetype_name = None
            player_name = None
        else:
            # Saving a deck from MTGGoldfish
            deck_name = format_deck_name(self.currently_selected_deck)
            archetype_name = self.currently_selected_deck.get("name")
            player_name = self.currently_selected_deck.get("player")
            source = "mtggoldfish"
            metadata = {
                "date": self.currently_selected_deck.get("date"),
                "event": self.currently_selected_deck.get("event"),
                "result": self.currently_selected_deck.get("result"),
                "deck_number": self.currently_selected_deck.get("number"),
            }

        try:
            # Save to database
            deck_id = save_deck_to_db(
                deck_name=deck_name,
                deck_content=deck_content,
                format_type=self.format.get(),
                archetype=archetype_name,
                player=player_name,
                source=source,
                metadata=metadata
            )

            # Also save to file (backup/export)
            safe_name = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in deck_name).strip()
            if not safe_name:
                safe_name = "saved_deck"
            file_name = f"{safe_name}.txt"
            save_dir = self.deck_save_dir
            try:
                save_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.warning(f"Failed to create deck save directory '{save_dir}': {exc}")
            file_path = save_dir / file_name
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(deck_content)

            messagebox.showinfo("Deck Saved", f"Deck saved successfully!\nDatabase ID: {deck_id}\nFile: {file_name}")
            logger.info(f"Deck saved: {deck_name} (ID: {deck_id})")

        except Exception as e:
            logger.error(f"Failed to save deck: {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Failed to save deck:\n{str(e)}")

    def copy_deck_to_clipboard(self):
        deck_content = self.get_deck_text().strip()
        if not deck_content:
            messagebox.showinfo("Copy Deck", "Deck is empty.")
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(deck_content)
            messagebox.showinfo("Copy Deck", "Deck copied to clipboard.")
        except Exception as exc:
            logger.error(f"Failed to copy deck to clipboard: {exc}")
            messagebox.showerror("Copy Deck", f"Failed to copy deck:\n{exc}")

    def add_deck_to_buffer(self):
        self.deck_buffer = add_dicts(self.deck_buffer, deck_to_dictionary(self.get_deck_text()))
        self.decks_added += 1

    def make_average_deck(self):
        deck_string = ""
        added_sideboard_blank_line = False
        sorted_cards = sorted(self.deck_buffer.items(), key=lambda x: "Sideboard" in x[0])
        for card in sorted_cards:
            if "Sideboard" in card[0] and not added_sideboard_blank_line:
                deck_string += "\n"
                added_sideboard_blank_line = True
            card_average = float(card[1]) / self.decks_added
            if card_average.is_integer():
                deck_string += f"{int(card_average)} {card[0].replace('Sideboard ', '')}\n"
                continue
            deck_string += f'{float(card[1])/self.decks_added:.2f} {card[0].replace("Sideboard ", "")}\n'
        self.load_deck_text(deck_string)
        self.decks_added = 0
        self.deck_buffer = {}
        if self.current_mode == "builder":
            self.builder_sync_from_text(deck_string)

    def ui_bind_components(self):
        return

    def select_archetype(self):
        # If still loading or error, retry loading
        if self.loading or not self.archetypes:
            self.lazy_load_archetypes()
            return

        selected = self.listbox.curselection()
        if not selected:
            return
        selected = selected[0]
        archetype = self.archetypes[selected]["href"]

        # Show loading message while fetching decks
        self.listbox.delete(0, tk.END)
        self.listbox.insert(0, "⏳ Loading decks...")
        self.listbox_button.config(state="disabled")

        def load_decks_in_background():
            try:
                decks = get_archetype_decks(archetype)
                self.root.after(0, lambda: self.on_decks_loaded(decks))
            except Exception as e:
                logger.error(f"Failed to load decks: {e}")
                self.root.after(0, lambda: self.on_decks_error(str(e)))

        thread = threading.Thread(target=load_decks_in_background, daemon=True)
        thread.start()

    def on_decks_loaded(self, decks):
        """Called when decks are loaded"""
        self.decks = decks
        repopulate_listbox(self.listbox, [format_deck_name(deck) for deck in self.decks])
        self.listbox_button.config(text="Select deck", command=self.select_deck, state="normal")
        self.listbox.bind("<<ListboxSelect>>", self.set_textbox)
        self.reset_button = button(self.F_top_left, "Reset", self.ui_reset_to_archetype_selection)
        self.reset_button.grid(column=0, row=0, sticky="nsew")
        self.make_daily_average_deck_button = button(self.F_top_right_top, "Day's Average", self.set_daily_average_deck)
        self.make_daily_average_deck_button.grid(column=4, row=0, sticky="nsew")
        logger.info(f"Loaded {len(decks)} decks")

    def on_decks_error(self, error_msg):
        """Called if deck loading fails"""
        self.listbox.delete(0, tk.END)
        self.listbox.insert(0, f"❌ Error loading decks: {error_msg[:40]}")
        self.listbox_button.config(state="normal")

    def set_daily_average_deck(self):
        # Prevent multiple simultaneous loads
        if self.loading_daily_average:
            logger.warning("Daily average already loading, ignoring click")
            return

        today = time.strftime("%Y-%m-%d")
        decks_from_today = [d for d in self.decks if today.lower() in d["date"]]

        if not decks_from_today:
            logger.info("No decks from today found")
            self.display_deck_message("No decks from today found in this archetype")
            return

        # Show loading in textbox
        self.loading_daily_average = True
        self.display_deck_message(f"⏳ Loading {len(decks_from_today)} decks from today...\n")
        self.make_daily_average_deck_button.config(state="disabled")
        logger.info(f"Starting to load {len(decks_from_today)} decks for daily average")

        def update_progress(current, total):
            """Thread-safe progress update"""
            def _update():
                self.display_deck_message(f"⏳ Loading deck {current}/{total}...\n")
            self.root.after(0, _update)

        def load_daily_average_in_background():
            try:
                deck_buffer = {}
                decks_added = 0

                for idx, deck in enumerate(decks_from_today, 1):
                    logger.debug(f"Downloading deck {idx}/{len(decks_from_today)}: {deck['number']}")

                    # Update progress before downloading
                    update_progress(idx, len(decks_from_today))

                    # Download deck
                    download_deck(deck["number"])

                    # Read deck content with proper file handling
                    try:
                        deck_str = self._read_curr_deck_file()
                    except Exception as file_error:
                        logger.error(f"Failed to read deck file: {file_error}")
                        raise

                    # Parse and add to buffer
                    deck_buffer = add_dicts(deck_buffer, deck_to_dictionary(deck_str))
                    decks_added += 1
                    logger.debug(f"Successfully processed deck {idx}/{len(decks_from_today)}")

                logger.info(f"Completed loading {decks_added} decks")
                self.root.after(0, lambda: self.on_daily_average_loaded(deck_buffer, decks_added))

            except Exception as e:
                logger.error(f"Failed to load daily average: {e}", exc_info=True)
                def _error():
                    self.display_deck_message(f"❌ Error loading decks:\n{str(e)}")
                    self.make_daily_average_deck_button.config(state="normal")
                    self.loading_daily_average = False
                self.root.after(0, _error)

        thread = threading.Thread(target=load_daily_average_in_background, daemon=True)
        thread.start()

    def on_daily_average_loaded(self, deck_buffer, decks_added):
        """Called when daily average is computed"""
        try:
            self.deck_buffer = deck_buffer
            self.decks_added = decks_added
            self.make_average_deck()
            logger.info("Daily average deck created successfully")
        except Exception as e:
            logger.error(f"Error creating average deck: {e}")
            self.display_deck_message(f"❌ Error creating average:\n{str(e)}")
        finally:
            self.make_daily_average_deck_button.config(state="normal")
            self.loading_daily_average = False

    def set_textbox(self, event):
        selected = self.listbox.curselection()
        if not selected:
            return
        selected = selected[0]
        self.currently_selected_deck = self.decks[selected]
        deck = self.decks[selected]

        # Show loading message
        self.display_deck_message("⏳ Loading deck...")
        logger.debug(f"Loading deck: {deck['number']}")

        def load_deck_in_background():
            try:
                download_deck(deck["number"])

                # Read with proper file handling
                try:
                    deck_content = self._read_curr_deck_file()
                except Exception as file_error:
                    logger.error(f"Failed to read deck file: {file_error}")
                    raise

                logger.debug(f"Successfully loaded deck: {deck['number']}")
                self.root.after(0, lambda: self.on_deck_content_loaded(deck_content))

            except Exception as e:
                logger.error(f"Failed to load deck: {e}", exc_info=True)
                def _error():
                    self.display_deck_message(f"❌ Error loading deck:\n{str(e)}")
                self.root.after(0, _error)

        thread = threading.Thread(target=load_deck_in_background, daemon=True)
        thread.start()

    def on_deck_content_loaded(self, deck_content):
        """Called when deck content is downloaded"""
        try:
            self.load_deck_text(deck_content)
            if self.current_mode == "builder":
                self.builder_sync_from_text(deck_content)
        except Exception as e:
            logger.error(f"Error displaying deck: {e}")
            self.display_deck_message(f"❌ Error displaying deck:\n{str(e)}")

    def clear_deck_textboxes(self):
        for zone in self.zone_views:
            self._clear_zone_view(zone)
            self.zone_lines[zone] = []
            self.q_btn_frames.setdefault(zone, [])
            self.q_btn_frames[zone] = []

    def split_deck_text(self, deck_text):
        main_lines = []
        side_lines = []
        is_side = False
        for raw_line in deck_text.splitlines():
            line = raw_line.strip()
            if not line:
                if main_lines or side_lines:
                    is_side = True
                continue
            if line.lower().startswith("sideboard"):
                is_side = True
                continue
            target = side_lines if is_side else main_lines
            target.append(line)
        return main_lines, side_lines

    def _clear_zone_view(self, zone):
        view = self.zone_views.get(zone)
        if not view:
            return
        for child in view["frame"].winfo_children():
            child.destroy()
        view["rows"] = []
        view["canvas"].yview_moveto(0)
        view["frame"].update_idletasks()
        bbox = view["canvas"].bbox("all")
        if bbox:
            view["canvas"].configure(scrollregion=bbox)
        else:
            view["canvas"].configure(scrollregion=(0, 0, 0, 0))
        for col in range(view.get("columns", 0)):
            view["frame"].grid_columnconfigure(col, weight=0, minsize=0)
        view["columns"] = 0
        view["pending_layout"] = False

    def _layout_zone_rows(self, zone, frames=None):
        view = self.zone_views.get(zone)
        if not view:
            return
        frames = frames if frames is not None else view.get("rows", [])
        if not frames:
            return

        for col in range(view.get("columns", 0)):
            view["frame"].grid_columnconfigure(col, weight=0, minsize=0)
        view["columns"] = 0

        if view.get("rows"):
            for frame in frames:
                if hasattr(frame, "grid_forget"):
                    frame.grid_forget()

        if not frames:
            return

        if self.zone_lines.get(zone):
            columns = min(DECK_GRID_COLUMNS, len(frames))
            if columns <= 0:
                columns = 1
        else:
            columns = 1

        for col in range(columns):
            view["frame"].grid_columnconfigure(col, weight=1, uniform=f"{zone}_cols")

        view["columns"] = columns

        for index, frame in enumerate(frames):
            column = index % columns
            row = index // columns
            frame.grid(column=column, row=row, sticky="ew", padx=2, pady=(0, 1))

        view["frame"].update_idletasks()
        bbox = view["canvas"].bbox("all")
        if bbox:
            view["canvas"].configure(scrollregion=bbox)
        else:
            view["canvas"].configure(scrollregion=(0, 0, 0, 0))

        per_column_width = max(120, (view["frame"].winfo_width() // max(1, columns)) - self.row_button_width)
        for frame in frames:
            if isinstance(frame, tk.Label):
                frame.configure(wraplength=per_column_width + self.row_button_width)
            else:
                label = getattr(frame, "card_label", None)
                if label:
                    label.configure(wraplength=per_column_width)

    def _request_zone_relayout(self, zone):
        view = self.zone_views.get(zone)
        if not view or not view.get("rows"):
            return
        if view.get("pending_layout"):
            return
        view["pending_layout"] = True

        def _do_relayout(z=zone):
            self._relayout_zone(z)

        self.root.after_idle(_do_relayout)

    def _relayout_zone(self, zone):
        view = self.zone_views.get(zone)
        if not view:
            return
        view["pending_layout"] = False
        if not view.get("rows"):
            return
        self._layout_zone_rows(zone)

    def _configure_card_search_panel(self, manager):
        if getattr(self, "_search_width_set", False):
            return
        cards = getattr(manager, "_cards", None)
        if not cards:
            return

        width_chars = CARD_SEARCH_LISTBOX_WIDTH
        self.listbox.config(width=width_chars)

        self.builder_controls_frame.update_idletasks()
        controls_width = self.builder_controls_frame.winfo_reqwidth()
        screen_width = self.root.winfo_screenwidth() or 1920
        panel_width = max(controls_width + 20, min(CARD_SEARCH_PANEL_WIDTH, int(screen_width * 0.35)))

        self.F_top_left.grid_propagate(False)
        self.F_top_left.configure(width=panel_width)
        self.F_top_left.update_idletasks()
        self.F_top.grid_columnconfigure(0, minsize=panel_width)
        self._search_width_set = True

    @staticmethod
    def _widget_exists(widget):
        try:
            return bool(widget) and widget.winfo_exists()
        except Exception:
            return False

    def launch_opponent_tracker(self):
        existing = getattr(self.opponent_tracker_window, "root", None) if self.opponent_tracker_window else None
        if self._widget_exists(existing):
            existing.deiconify()
            existing.lift()
            return
        try:
            self.opponent_tracker_window = MTGOpponentDeckSpy(master=self.root)
            self.opponent_tracker_window.root.bind("<Destroy>", self._on_tracker_closed)
        except Exception as exc:
            logger.error(f"Failed to launch opponent tracker: {exc}")
            messagebox.showerror("Opponent Tracker", f"Unable to launch opponent tracker:\n{exc}")

    def open_timer_alert(self):
        window = getattr(self.timer_alert_window, "window", None) if self.timer_alert_window else None
        if self._widget_exists(window):
            window.deiconify()
            window.lift()
            return
        try:
            self.timer_alert_window = TimerAlertWindow(self.root)
            self.timer_alert_window.window.bind("<Destroy>", self._on_timer_closed)
        except Exception as exc:
            logger.error(f"Failed to open timer alert: {exc}")
            messagebox.showerror("Timer Alert", f"Unable to open timer alert:\n{exc}")

    def _on_tracker_closed(self, _event=None):
        self.opponent_tracker_window = None

    def _on_timer_closed(self, _event=None):
        self.timer_alert_window = None

    def export_collection_snapshot(self):
        logger.debug("Collection export requested")
        ready, error = mtgo_bridge.runtime_status()
        if not ready:
            logger.debug("MTGOSDK runtime not ready: %s", error)
            messagebox.showwarning("Collection Export", f"MTGOSDK runtime unavailable: {error or 'still loading'}")
            return

        def worker():
            logger.debug("Collection export worker started")
            self.root.after(0, lambda: self.sdk_status_var.set("MTGOSDK: exporting collection…"))
            ready, error = mtgo_bridge.ensure_runtime_ready()
            if not ready:
                logger.debug("Runtime became unavailable during export: %s", error)
                self.root.after(0, lambda: (self.sdk_status_var.set("MTGOSDK: unavailable"), messagebox.showerror("Collection Export", f"MTGOSDK runtime unavailable: {error or 'see logs'}")))
                return
            try:
                logger.debug("Fetching Full Trade List binder from MTGOSDK")
                binder = mtgo_bridge.get_binder_by_name("Full Trade List")
            except Exception as exc:
                logger.exception("Failed to fetch collection binder", exc_info=True)
                self.root.after(0, lambda: (self.sdk_status_var.set("MTGOSDK: ready"), messagebox.showerror("Collection Export", f"Failed to fetch collection: {exc}")))
                return
            if not binder:
                logger.debug("Full Trade List Binder not found in snapshot")
                names = mtgo_bridge.get_available_binder_names()
                message = "Full Trade List binder not found. Available: {}".format(', '.join(filter(None, names)) or '<none>')
                self.root.after(0, lambda: (self.sdk_status_var.set("MTGOSDK: ready"), messagebox.showinfo("Collection Export", message)))
                return
            export_data = {
                "name": binder.get("name"),
                "itemCount": binder.get("itemCount"),
                "exportedAt": __import__('datetime').datetime.now().isoformat(),
                "cards": binder.get("cards", []),
            }
            export_dir = self.deck_save_dir
            export_dir.mkdir(parents=True, exist_ok=True)
            timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = export_dir / f"collection_full_trade_{timestamp}.json"
            try:
                export_path.write_text(json.dumps(export_data, indent=2, ensure_ascii=False), encoding="utf-8")
                logger.debug("Collection written to %s", export_path)
            except OSError as exc:
                logger.exception("Failed to write collection export", exc_info=True)
                self.root.after(0, lambda: (self.sdk_status_var.set("MTGOSDK: ready"), messagebox.showerror("Collection Export", f"Failed to write file: {exc}")))
                return
            self.root.after(0, lambda: (self.sdk_status_var.set("MTGOSDK: ready"), messagebox.showinfo("Collection Export", f"Collection saved to {export_path}")))
        threading.Thread(target=worker, daemon=True).start()

    def open_match_history(self):
        window = getattr(self.match_history_window, "window", None) if self.match_history_window else None
        if window is not None and window.winfo_exists():
            window.lift()
            return
        try:
            self.match_history_window = MatchHistoryWindow(self.root)
            self.match_history_window.window.bind("<Destroy>", self._on_match_history_closed)
        except Exception as exc:
            logger.error("Failed to open match history: {}", exc)
            messagebox.showerror("Match History", f"Unable to open match history:\n{exc}")

    def _on_match_history_closed(self, _event=None):
        self.match_history_window = None

    def render_deck_zone(self, zone, lines):
        view = self.zone_views.get(zone)
        if not view:
            return

        self._clear_zone_view(zone)
        self.q_btn_frames.setdefault(zone, [])
        self.q_btn_frames[zone] = []
        self.zone_lines[zone] = list(lines)

        if not lines:
            placeholder = tk.Label(view["frame"], text="", background=CS[1])
            placeholder.card_line = ""
            view["rows"] = [placeholder]
            self._layout_zone_rows(zone, view["rows"])
            return

        frames = []
        for line in lines:
            frame = self.create_F_edit_deck(view["frame"], line, zone)
            frames.append(frame)
            self.q_btn_frames[zone].append(frame)

        view["rows"] = frames
        self._layout_zone_rows(zone, frames)
        self._request_zone_relayout(zone)

    def get_zone_lines(self, zone):
        return list(self.zone_lines.get(zone, []))

    def get_deck_text(self):
        main_lines = self.get_zone_lines("main")
        side_lines = self.get_zone_lines("side")
        parts = main_lines.copy()
        if side_lines:
            parts.append("")
            parts.append("Sideboard")
            parts.extend(side_lines)
        return "\n".join(parts)

    def load_deck_text(self, deck_text):
        main_lines, side_lines = self.split_deck_text(deck_text)
        self.render_deck_zone("main", main_lines)
        self.render_deck_zone("side", side_lines)

    def display_deck_message(self, message):
        for zone in self.zone_views:
            self._clear_zone_view(zone)
            self.zone_lines[zone] = []
            self.q_btn_frames.setdefault(zone, [])
            self.q_btn_frames[zone] = []
        view = self.zone_views.get("main")
        if not view:
            return
        label = tk.Label(
            view["frame"],
            text=message,
            font=self.deck_row_font,
            background=CS[1],
            anchor="nw",
            justify="left",
            wraplength=view["canvas"].winfo_width() or 400,
        )
        label.card_line = message or ""
        view["rows"] = [label]
        self._layout_zone_rows("main", view["rows"])

    def _split_card_line(self, line):
        parts = line.strip().split(" ", 1)
        if len(parts) != 2:
            return 0, ""
        try:
            count = int(float(parts[0]))
        except ValueError:
            count = 0
        return count, parts[1].strip()

    def _find_line_index(self, lines, target):
        for idx, value in enumerate(lines):
            if value.strip() == target.strip():
                return idx
        return None

    def _is_descendant(self, widget, ancestor):
        current = widget
        while current:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _zone_for_widget(self, widget):
        for zone, view in self.zone_views.items():
            if widget is view["canvas"] or self._is_descendant(widget, view["frame"]):
                return zone
        return None

    def _apply_zone_lines(self, zone, lines):
        self.render_deck_zone(zone, lines)
        deck_text = self.get_deck_text()
        self.builder_sync_from_text(deck_text)


    def increment_card(self, zone, line):
        lines = self.get_zone_lines(zone)
        idx = self._find_line_index(lines, line)
        if idx is None:
            logger.debug(f"{line} not found in {zone} decklist")
            return
        count, card_name = self._split_card_line(lines[idx])
        count += 1
        lines[idx] = f"{count} {card_name}"
        self._apply_zone_lines(zone, lines)

    def decrement_card(self, zone, line):
        lines = self.get_zone_lines(zone)
        idx = self._find_line_index(lines, line)
        if idx is None:
            logger.debug(f"{line} not found in {zone} decklist")
            return
        count, card_name = self._split_card_line(lines[idx])
        if count <= 1:
            lines.pop(idx)
        else:
            lines[idx] = f"{count - 1} {card_name}"
        self._apply_zone_lines(zone, lines)

    def create_F_edit_deck(self, parent, line, zone):
        frame = b_frame(parent, color=CS[1])
        frame.configure(borderwidth=0, highlightthickness=0)
        frame.grid_columnconfigure(3, weight=1)
        frame.bind("<Button-1>", lambda _event, z=zone, l=line: self.on_deck_row_click(z, l))
        FONT = ("verdana", 9, "bold")
        plus_btn = b_button(frame, "+", lambda l=line, z=zone: self.increment_card(z, l), font=FONT, color=CS[2], width=2)
        minus_btn = b_button(frame, "-", lambda l=line, z=zone: self.decrement_card(z, l), font=FONT, color=CS[2], width=2)
        remove_btn = b_button(frame, "X", lambda l=line, z=zone: self.remove_card(z, l), font=FONT, color=CS[2], width=2)
        plus_btn.grid(column=0, row=0, padx=(0, 2), sticky="w")
        minus_btn.grid(column=1, row=0, padx=(0, 2), sticky="w")
        remove_btn.grid(column=2, row=0, padx=(0, 4), sticky="w")
        label = tk.Label(frame, text=line, font=self.deck_row_font, background=CS[1], anchor="w")
        label.grid(column=3, row=0, sticky="w", padx=(4, 0))
        label.bind("<Button-1>", lambda _event, z=zone, l=line: self.on_deck_row_click(z, l))
        frame.card_line = line
        frame.card_label = label
        return frame

    def on_deck_row_click(self, zone, line):
        if self.current_mode != "builder":
            return
        if not self.card_manager:
            if not self.card_data_loading:
                self.ensure_card_data_loaded()
            return
        card_name = self.extract_card_name_from_line(line)
        if not card_name:
            return
        card = self.card_manager.get_card(card_name)
        if not card:
            self.builder_status_var.set(f"No card data for '{card_name}'")
            return
        self.display_card_detail(card)
        self.builder_add_main_button.config(state="disabled")
        self.builder_add_side_button.config(state="disabled")

    def remove_card(self, zone, line):
        lines = self.get_zone_lines(zone)
        idx = self._find_line_index(lines, line)
        if idx is None:
            return
        lines.pop(idx)
        self._apply_zone_lines(zone, lines)

    def select_deck(self):
        # Simply displays the selected deck without any automation
        selected = self.listbox.curselection()
        logger.debug(selected)
        if not selected:
            return
        selected = selected[0]
        logger.debug(selected)
        self.currently_selected_deck = self.decks[selected]

    def set_mode_button_states(self, active_mode: str):
        buttons = {
            "browse": self.browse_mode_button,
            "saved": self.saved_decks_button,
            "builder": self.builder_mode_button,
        }
        for mode, btn in buttons.items():
            btn.config(background=CS[2] if mode == active_mode else CS[0])

    def disable_builder_ui(self):
        self.builder_controls_frame.grid_remove()
        if not self.listbox_button.winfo_ismapped():
            self.listbox_button.grid()
        self.card_detail_frame.grid_remove()
        self.builder_add_main_button.config(state="disabled")
        self.builder_add_side_button.config(state="disabled")
        self.builder_status_var.set("")
        self.listbox.unbind("<<ListboxSelect>>")

    def enable_builder_ui(self):
        if self.listbox_button.winfo_ismapped():
            self.listbox_button.grid_remove()
        self.builder_controls_frame.grid()
        self.card_detail_frame.grid()
        self.builder_add_main_button.config(state="disabled")
        self.builder_add_side_button.config(state="disabled")
        self.listbox.bind("<<ListboxSelect>>", self.on_card_result_selected)

    def ensure_card_data_loaded(self):
        if self.card_data_ready or self.card_data_loading:
            return
        self.card_data_loading = True
        self.builder_status_var.set("Loading card database...")

        def worker():
            try:
                from utils.card_data import CardDataManager

                manager = CardDataManager()
                manager.ensure_latest()
                formats = manager.available_formats()
                self.root.after(0, lambda: self.on_card_data_ready(manager, formats))
            except Exception as exc:
                logger.warning(f"Card data preload failed: {exc}")
                self.root.after(0, lambda: self.on_card_data_failed(exc))

        threading.Thread(target=worker, daemon=True).start()

    def on_card_data_ready(self, manager, formats):
        self.card_manager = manager
        self.card_data_ready = True
        self.card_data_loading = False
        available_formats = ["Any"] + sorted({fmt.lower() for fmt in formats}) if formats else CARD_SEARCH_FORMATS
        self.card_format_menu.configure(values=available_formats)
        if self.card_format_var.get() not in available_formats:
            self.card_format_var.set("Any")
        self.card_search_button.config(state="normal")
        self.card_search_entry.config(state="normal")
        self.open_saved_decks_button.config(state="normal")
        self.builder_status_var.set("Card data ready. Type to search.")
        self._configure_card_search_panel(manager)

    def on_card_data_failed(self, error):
        self.card_data_loading = False
        self.card_manager = None
        self.builder_status_var.set(f"Card data unavailable: {error}")
        self.card_data_ready = False
        self.card_search_button.config(state="disabled")
        self.card_search_entry.config(state="disabled")

    def switch_to_builder_mode(self):
        """Switch to deck builder mode"""
        self.current_mode = "builder"
        self.set_mode_button_states("builder")
        self.disable_builder_ui()  # Reset bindings, then enable builder UI
        self.enable_builder_ui()
        self.load_saved_into_builder_button.grid(column=6, row=0, sticky="nsew")
        self.load_saved_into_builder_button.config(state="normal")
        self.hide_deck_statistics()
        if hasattr(self, "visualize_button"):
            self.visualize_button.grid_remove()
        if hasattr(self, "reset_button"):
            self.reset_button.grid_forget()
        if getattr(self, "delete_deck_button", None):
            self.delete_deck_button.grid_forget()
            self.delete_deck_button = None
        if hasattr(self, "make_daily_average_deck_button"):
            self.make_daily_average_deck_button.grid_forget()

        existing = self.get_deck_text()
        self.builder_sync_from_text(existing)
        self.builder_render_deck()
        self.card_search_results = []
        self.listbox.delete(0, tk.END)
        self.builder_status_var.set("Loading card database...")
        if self.card_data_ready:
            self.card_search_button.config(state="normal")
            self.card_search_entry.config(state="normal")
        else:
            self.card_search_button.config(state="disabled")
            self.card_search_entry.config(state="disabled")
        self.open_saved_decks_button.config(state="normal")
        self.card_detail_text.config(state="normal")
        self.card_detail_text.delete("1.0", tk.END)
        self.card_detail_text.config(state="disabled")
        self.ensure_card_data_loaded()

    def perform_card_search(self):
        if self.current_mode != "builder":
            return
        if not self.card_data_ready:
            if not self.card_data_loading:
                self.ensure_card_data_loaded()
            self.builder_status_var.set("Card data still loading...")
            return
        query = self.card_search_var.get()
        fmt = self.card_format_var.get()
        type_filter = self.card_type_var.get()
        fmt_value = None if fmt == "Any" else fmt.lower()
        type_value = None if type_filter == "Any" else type_filter.lower()
        self.listbox.delete(0, tk.END)
        try:
            matches = self.card_manager.search_cards(query=query, format_filter=fmt_value, type_filter=type_value)
            self.card_search_results = matches
            for card in matches:
                cost = card.get("mana_cost") or ""
                display = f"{card['name']} {cost}".strip()
                self.listbox.insert(tk.END, display)
            if matches:
                self.builder_status_var.set(f"Found {len(matches)} cards.")
            else:
                self.builder_status_var.set("No matches found.")
        except Exception as exc:
            logger.exception("Card search failed")
            self.builder_status_var.set(f"Search failed: {exc}")

    def on_card_result_selected(self, event=None):
        if self.current_mode != "builder":
            return
        selection = self.listbox.curselection()
        if not selection:
            self.builder_add_main_button.config(state="disabled")
            self.builder_add_side_button.config(state="disabled")
            return
        card = self.card_search_results[selection[0]]
        self.display_card_detail(card)
        self.builder_add_main_button.config(state="normal")
        self.builder_add_side_button.config(state="normal")

    def display_card_detail(self, card):
        mana_value = card.get('mana_value')
        if isinstance(mana_value, float) and mana_value.is_integer():
            mana_value_display = int(mana_value)
        else:
            mana_value_display = mana_value if mana_value is not None else '-'
        details = [
            card["name"],
            f"Mana Cost: {card.get('mana_cost') or '-'}",
            f"Mana Value: {mana_value_display}",
            f"Type: {card.get('type_line') or '-'}",
        ]
        identity = "".join(card.get("color_identity") or [])
        if identity:
            details.append(f"Color Identity: {identity}")
        text = card.get("oracle_text") or ""
        if text:
            details.append("")
            details.append(text)
        legal = sorted(fmt for fmt, state in (card.get("legalities") or {}).items() if state == "Legal")
        if legal:
            details.append("")
            details.append("Legal in: " + ", ".join(legal))
        self.card_detail_text.config(state="normal")
        self.card_detail_text.delete("1.0", tk.END)
        self.card_detail_text.insert("1.0", "\n".join(details))
        self.card_detail_text.config(state="disabled")

    def builder_add_card(self, zone: str):
        if self.current_mode != "builder":
            return
        selection = self.listbox.curselection()
        if not selection:
            return
        card = self.card_search_results[selection[0]]
        name = card["name"]
        zone_dict = self.builder_deck[zone]
        zone_dict[name] = zone_dict.get(name, 0) + 1
        self.builder_render_deck()

    def builder_render_deck(self):
        main_lines = [f"{self.builder_deck['main'][name]} {name}" for name in sorted(self.builder_deck['main'])]
        side_lines = [f"{self.builder_deck['side'][name]} {name}" for name in sorted(self.builder_deck['side'])]
        self.render_deck_zone("main", main_lines)
        self.render_deck_zone("side", side_lines)
        self.builder_update_status_counts()

    def builder_sync_from_text(self, content: str | None = None):
        deck_text = (content if content is not None else self.get_deck_text()).strip()
        if not deck_text:
            self.builder_deck = {"main": {}, "side": {}}
            self.builder_render_deck()
            self.builder_update_status_counts()
            return
        deck_dict = deck_to_dictionary(deck_text)
        main = {}
        side = {}
        for card_name, count in deck_dict.items():
            if card_name.startswith("Sideboard "):
                side[card_name.replace("Sideboard ", "")] = count
            else:
                main[card_name] = count
        self.builder_deck = {"main": main, "side": side}
        if content is None:
            self.builder_render_deck()
        self.builder_update_status_counts()

    def builder_update_status_counts(self):
        main_total = sum(self.builder_deck["main"].values())
        side_total = sum(self.builder_deck["side"].values())
        if self.current_mode == "builder":
            self.builder_status_var.set(f"Deck size: {main_total} main / {side_total} side")

    def _read_curr_deck_file(self) -> str:
        candidates = [CURR_DECK_FILE, LEGACY_CURR_DECK_CACHE, LEGACY_CURR_DECK_ROOT]
        for candidate in candidates:
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as fh:
                    contents = fh.read()
                if candidate != CURR_DECK_FILE:
                    try:
                        CURR_DECK_FILE.parent.mkdir(parents=True, exist_ok=True)
                        with CURR_DECK_FILE.open("w", encoding="utf-8") as target:
                            target.write(contents)
                        try:
                            candidate.unlink()
                        except OSError:
                            logger.debug(f"Unable to remove legacy deck file {candidate}")
                    except OSError as exc:
                        logger.debug(f"Failed to migrate curr_deck.txt from {candidate}: {exc}")
                return contents
        raise FileNotFoundError("Current deck file not found")

    def open_saved_decks_dialog(self):
        """Open a modal list of saved decks for loading into the builder."""
        if self.saved_decks_popup and self.saved_decks_popup.winfo_exists():
            self.saved_decks_popup.lift()
            return

        self.saved_decks_popup = tk.Toplevel(self.root)
        self.saved_decks_popup.title("Load Saved Deck")
        self.saved_decks_popup.geometry("420x360")
        self.saved_decks_popup.transient(self.root)
        self.saved_decks_popup.grab_set()

        container = tk.Frame(self.saved_decks_popup, padx=8, pady=8)
        container.pack(fill="both", expand=True)
        tk.Label(container, text=f"Saved decks ({self.format.get()}):", font=("calibri", 12, "bold")).pack(anchor="w")

        list_frame = tk.Frame(container)
        list_frame.pack(fill="both", expand=True, pady=6)
        listbox = tk.Listbox(list_frame, font=("calibri", 11), height=12)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)
        status = tk.Label(container, text="Loading saved decks...", anchor="w")
        status.pack(fill="x", pady=(4, 0))
        button_bar = tk.Frame(container)
        button_bar.pack(fill="x", pady=(8, 0))
        load_btn = tk.Button(button_bar, text="Load Selected Deck", command=lambda: self.load_saved_deck_from_popup())
        load_btn.pack(side="left", expand=True, fill="x")
        cancel_btn = tk.Button(button_bar, text="Cancel", command=self.close_saved_decks_dialog)
        cancel_btn.pack(side="right", expand=True, fill="x", padx=(8, 0))

        self.saved_decks_popup_listbox = listbox
        self.saved_decks_popup_status = status
        self.saved_decks_popup_data = []
        self.saved_decks_popup.protocol("WM_DELETE_WINDOW", self.close_saved_decks_dialog)
        self.populate_saved_decks_dialog()

    def close_saved_decks_dialog(self):
        if self.saved_decks_popup and self.saved_decks_popup.winfo_exists():
            self.saved_decks_popup.grab_release()
            self.saved_decks_popup.destroy()
        self.saved_decks_popup = None
        self.saved_decks_popup_listbox = None
        self.saved_decks_popup_status = None
        self.saved_decks_popup_data = []

    def populate_saved_decks_dialog(self):
        if not self.saved_decks_popup or not self.saved_decks_popup.winfo_exists():
            return
        self.saved_decks_popup_listbox.delete(0, tk.END)
        self.saved_decks_popup_status.config(text="Loading saved decks...")

        def load():
            try:
                decks = get_saved_decks(format_type=self.format.get())
            except Exception as exc:
                self.root.after(0, lambda: self.saved_decks_popup_status.config(text=f"Error: {exc}"))
                return

            def finish():
                if not (self.saved_decks_popup and self.saved_decks_popup.winfo_exists()):
                    return
                self.saved_decks_popup_data = decks
                self.saved_decks_popup_listbox.delete(0, tk.END)
                if not decks:
                    self.saved_decks_popup_listbox.insert(tk.END, "No saved decks found")
                    self.saved_decks_popup_status.config(text="No saved decks available.")
                    return
                for deck in decks:
                    display = deck.get("name", "Unnamed deck")
                    if deck.get("date_saved"):
                        display = f"[{deck['date_saved'].strftime('%Y-%m-%d')}] {display}"
                    self.saved_decks_popup_listbox.insert(tk.END, display)
                self.saved_decks_popup_status.config(text=f"{len(decks)} decks loaded.")

            self.root.after(0, finish)

        threading.Thread(target=load, daemon=True).start()

    def load_saved_deck_from_popup(self):
        if not (self.saved_decks_popup and self.saved_decks_popup_listbox):
            return
        selection = self.saved_decks_popup_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a deck to load.")
            return
        if not self.saved_decks_popup_data:
            messagebox.showwarning("Unavailable", "Deck data not available.")
            return
        deck_doc = self.saved_decks_popup_data[selection[0]]
        self.apply_saved_deck_to_builder(deck_doc)
        self.close_saved_decks_dialog()

    def apply_saved_deck_to_builder(self, deck_doc: dict):
        deck_content = deck_doc.get("content", "")
        if not deck_content:
            messagebox.showwarning("Empty Deck", "Selected deck has no content.")
            return
        self.load_deck_text(deck_content)
        if self.current_mode != "builder":
            self.switch_to_builder_mode()
        else:
            self.builder_sync_from_text(deck_content)
            self.builder_render_deck()
        deck_name = deck_doc.get("name", "Saved Deck")
        self.builder_status_var.set(f"Loaded saved deck: {deck_name}")

    def load_selected_saved_into_builder(self):
        if self.current_mode != "saved":
            self.open_saved_decks_dialog()
            return
        if not self.saved_decks:
            messagebox.showwarning("No Decks", "No saved decks available.")
            return
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a deck to load.")
            return
        deck_doc = self.saved_decks[selection[0]]
        self.apply_saved_deck_to_builder(deck_doc)

    def extract_card_name_from_line(self, line: str) -> str | None:
        line = (line or "").strip()
        if not line or line.lower() == "sideboard":
            return None
        parts = line.split(" ", 1)
        if len(parts) < 2:
            return None
        try:
            float(parts[0])
        except ValueError:
            return None
        card_name = parts[1].strip()
        if card_name.lower().startswith("sideboard "):
            card_name = card_name[len("sideboard "):].strip()
        return card_name or None

    def switch_to_browse_mode(self):
        """Switch to MTGGoldfish browsing mode"""
        self.current_mode = "browse"
        self.set_mode_button_states("browse")
        self.disable_builder_ui()
        self.load_saved_into_builder_button.grid_remove()
        self.close_saved_decks_dialog()
        if getattr(self, "delete_deck_button", None):
            self.delete_deck_button.grid_forget()
            self.delete_deck_button = None
        self.hide_deck_statistics()  # Hide stats when switching to browse mode
        if hasattr(self, 'visualize_button'):
            self.visualize_button.grid_remove()  # Hide visualize button in browse mode
        self.listbox_button.config(text="Select archetype", command=self.select_archetype, state="normal")
        self.ui_reset_to_archetype_selection()

    def switch_to_saved_mode(self):
        """Switch to saved decks mode"""
        self.current_mode = "saved"
        self.set_mode_button_states("saved")
        self.disable_builder_ui()
        self.load_saved_into_builder_button.grid(column=6, row=0, sticky="nsew")
        self.load_saved_into_builder_button.config(state="disabled")
        self.close_saved_decks_dialog()
        if getattr(self, "delete_deck_button", None):
            self.delete_deck_button.grid_forget()
            self.delete_deck_button = None

        # Clean up browse mode UI elements
        self.clear_deck_textboxes()
        self.display_deck_message("Select a saved deck from the list")
        if hasattr(self, "reset_button"):
            self.reset_button.grid_forget()
        if hasattr(self, "make_daily_average_deck_button"):
            self.make_daily_average_deck_button.grid_forget()

        # Unbind any browse mode listbox events
        self.listbox.unbind("<<ListboxSelect>>")

        self.load_saved_decks_list()

    def load_saved_decks_list(self):
        """Load saved decks from database"""
        self.clear_deck_textboxes()
        self.listbox.delete(0, tk.END)
        self.listbox.insert(0, "⏳ Loading saved decks...")
        self.listbox_button.config(state="disabled")
        self.saved_decks = []

        # Remove any existing reset button
        if hasattr(self, "reset_button"):
            self.reset_button.grid_forget()
        if getattr(self, "delete_deck_button", None):
            self.delete_deck_button.grid_forget()
            self.delete_deck_button = None

        def load_in_background():
            try:
                # Get decks from database, filtered by format
                decks = get_saved_decks(format_type=self.format.get())
                self.root.after(0, lambda: self.on_saved_decks_loaded(decks))
            except Exception as e:
                logger.error(f"Failed to load saved decks: {e}", exc_info=True)
                self.root.after(0, lambda: self.on_saved_decks_error(str(e)))

        thread = threading.Thread(target=load_in_background, daemon=True)
        thread.start()

    def on_saved_decks_loaded(self, decks):
        """Called when saved decks are loaded from database"""
        self.saved_decks = decks
        self.listbox.delete(0, tk.END)

        if not decks:
            self.listbox.insert(0, "No saved decks found")
            self.listbox.insert(1, f"Format: {self.format.get()}")
            self.listbox_button.config(text="Load Deck", command=self.load_selected_saved_deck, state="disabled")
            self.load_saved_into_builder_button.config(state="disabled")
            self.delete_deck_button = None
            self.display_deck_message("No saved decks available")
            return

        # Format deck names for display with more info
        for deck in decks:
            # Create a more detailed display
            display_name = f"{deck['name']}"

            # Add date if available
            if deck.get('date_saved'):
                date_str = deck['date_saved'].strftime('%m/%d')
                display_name = f"[{date_str}] {display_name}"

            self.listbox.insert(tk.END, display_name)

        self.listbox_button.config(text="Load Deck", command=self.load_selected_saved_deck, state="normal")
        self.listbox.bind("<<ListboxSelect>>", self.display_saved_deck)
        self.load_saved_into_builder_button.config(state="normal")

        # Add delete button
        self.delete_deck_button = button(self.F_top_left, "❌ Delete Deck", self.delete_selected_saved_deck, color="red")
        self.delete_deck_button.grid(column=0, row=0, sticky="nsew")

        # Show visualize button in saved decks mode
        if hasattr(self, 'visualize_button'):
            self.visualize_button.grid()

        logger.info(f"Loaded {len(decks)} saved decks")

    def on_saved_decks_error(self, error_msg):
        """Called if loading saved decks fails"""
        self.listbox.delete(0, tk.END)
        self.listbox.insert(0, f"❌ Error: {error_msg[:50]}")
        self.listbox.insert(1, "Click 'Saved Decks' to retry")
        self.listbox_button.config(state="normal")
        self.load_saved_into_builder_button.config(state="disabled")
        self.saved_decks = []
        if getattr(self, "delete_deck_button", None):
            self.delete_deck_button.grid_forget()
            self.delete_deck_button = None
        self.display_deck_message(f"❌ Error loading decks:\n{error_msg}")

    def display_saved_deck(self, event):
        """Display selected saved deck in textbox"""
        selected = self.listbox.curselection()
        if not selected:
            return
        selected = selected[0]

        deck_doc = self.saved_decks[selected]
        deck_content = deck_doc.get('content', '')
        self.load_deck_text(deck_content)

        # Show deck statistics
        self.update_deck_statistics(deck_content, deck_doc)

        # Show deck info in log
        info_lines = []
        if deck_doc.get('archetype'):
            info_lines.append(f"Archetype: {deck_doc['archetype']}")
        if deck_doc.get('player'):
            info_lines.append(f"Player: {deck_doc['player']}")
        if deck_doc.get('source'):
            info_lines.append(f"Source: {deck_doc['source']}")
        if deck_doc.get('date_saved'):
            info_lines.append(f"Saved: {deck_doc['date_saved'].strftime('%Y-%m-%d %H:%M')}")

        if info_lines:
            logger.info(" | ".join(info_lines))

    def update_deck_statistics(self, deck_content: str, deck_doc: dict = None):
        """Update the statistics panel with deck metadata"""
        try:
            # Build statistics text - metadata only
            stats_text = ""

            # Deck metadata
            if deck_doc:
                if deck_doc.get('archetype'):
                    stats_text += f"📦 Archetype: {deck_doc['archetype']}\n"
                if deck_doc.get('player'):
                    stats_text += f"👤 Player: {deck_doc['player']}\n"
                if deck_doc.get('format'):
                    stats_text += f"🎯 Format: {deck_doc['format']}\n"
                if deck_doc.get('source'):
                    stats_text += f"📍 Source: {deck_doc['source'].title()}\n"
                if deck_doc.get('date_saved'):
                    stats_text += f"💾 Saved: {deck_doc['date_saved'].strftime('%Y-%m-%d %H:%M')}\n"

                # Add metadata if available
                metadata = deck_doc.get('metadata', {})
                if metadata.get('event'):
                    stats_text += f"🏆 Event: {metadata['event']}\n"
                if metadata.get('result'):
                    stats_text += f"🎖️ Result: {metadata['result']}\n"

            if stats_text:
                self.stats_label.config(text=stats_text)
                self.F_stats.grid()  # Show the stats panel
            else:
                self.F_stats.grid_remove()  # Hide if no metadata

        except Exception as e:
            logger.error(f"Failed to display deck metadata: {e}")
            self.F_stats.grid_remove()  # Hide stats panel on error

    def hide_deck_statistics(self):
        """Hide the statistics panel"""
        self.F_stats.grid_remove()
        if hasattr(self, 'visualize_button'):
            self.visualize_button.config(text="📊 Show Stats")

    def toggle_statistics_panel(self):
        """Toggle the visibility of the statistics panel"""
        if self.F_stats.winfo_viewable():
            self.F_stats.grid_remove()
            self.visualize_button.config(text="📊 Show Stats")
        else:
            # Re-analyze current deck if available
            deck_content = self.get_deck_text().strip()
            if deck_content:
                # Get current deck doc if in saved mode
                deck_doc = None
                if self.current_mode == "saved" and self.saved_decks:
                    selected = self.listbox.curselection()
                    if selected:
                        deck_doc = self.saved_decks[selected[0]]

                self.update_deck_statistics(deck_content, deck_doc)
                self.visualize_button.config(text="📊 Hide Stats")
            else:
                messagebox.showinfo("No Deck", "Please select a deck to view statistics")

    def _load_window_settings(self) -> dict:
        if not DECK_SELECTOR_SETTINGS_FILE.exists():
            return {}
        try:
            with DECK_SELECTOR_SETTINGS_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to read deck selector settings: {exc}")
        return {}

    def _normalize_window_size(self, size_data):
        if isinstance(size_data, dict):
            try:
                width = int(size_data.get("width"))
                height = int(size_data.get("height"))
            except (TypeError, ValueError):
                return None
            if width > 0 and height > 0:
                return {"width": width, "height": height}
        return None

    def _normalize_window_position(self, position_data):
        if isinstance(position_data, (list, tuple)) and len(position_data) == 2:
            try:
                x = int(position_data[0])
                y = int(position_data[1])
            except (TypeError, ValueError):
                return None
            return (x, y)
        return None

    def _apply_window_preferences(self):
        geometry = ""
        if self.window_size:
            width = self.window_size.get("width")
            height = self.window_size.get("height")
            if width and height:
                geometry = f"{width}x{height}"
        if self.window_position:
            x, y = self.window_position
            if geometry:
                geometry = f"{geometry}+{x}+{y}"
            else:
                geometry = f"+{x}+{y}"
        if geometry:
            try:
                self.root.geometry(geometry)
            except tk.TclError as exc:
                logger.debug(f"Unable to apply saved geometry '{geometry}': {exc}")

    def on_window_configure(self, event):
        if event.widget is not self.root:
            return
        if getattr(self.root, "state", lambda: "normal")() == "iconic":
            return
        if event.width <= 1 or event.height <= 1:
            return
        self.window_size = {"width": int(event.width), "height": int(event.height)}
        self.window_position = (int(self.root.winfo_x()), int(self.root.winfo_y()))

    def on_close(self):
        try:
            if self.timer_alert_window:
                window = getattr(self.timer_alert_window, "window", None)
                if self._widget_exists(window):
                    try:
                        self.timer_alert_window.close()
                    except Exception:
                        window.destroy()
                self.timer_alert_window = None
            if self.match_history_window:
                window = getattr(self.match_history_window, "window", None)
                if self._widget_exists(window):
                    try:
                        self.match_history_window.close()
                    except Exception:
                        window.destroy()
                self.match_history_window = None
            if self.opponent_tracker_window:
                tracker_root = getattr(self.opponent_tracker_window, "root", None)
                if self._widget_exists(tracker_root):
                    tracker_root.destroy()
                self.opponent_tracker_window = None
            self.save_config()
        finally:
            self.root.destroy()

    def load_selected_saved_deck(self):
        """Load the selected saved deck (same as display, but explicit action)"""
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a deck to load")
            return

        selected = selected[0]
        deck_doc = self.saved_decks[selected]
        deck_content = deck_doc.get("content", "")
        if not deck_content:
            messagebox.showwarning("Empty Deck", "Selected deck has no content.")
            self.display_deck_message("Selected saved deck is empty.")
            return

        self.currently_selected_deck = deck_doc
        self.load_deck_text(deck_content)
        self.update_deck_statistics(deck_content, deck_doc)

        if self.current_mode == "builder":
            self.builder_sync_from_text(deck_content)
            self.builder_render_deck()
            deck_name = deck_doc.get("name", "Saved Deck")
            self.builder_status_var.set(f"Loaded saved deck: {deck_name}")

        logger.info(f"Loaded saved deck: {deck_doc.get('name', 'Unnamed Deck')}")

    def delete_selected_saved_deck(self):
        """Delete the selected saved deck"""
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a deck to delete")
            return

        selected = selected[0]
        deck_doc = self.saved_decks[selected]

        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete:\n{deck_doc['name']}?\n\nThis cannot be undone."
        )

        if not confirm:
            return

        try:
            delete_saved_deck(deck_doc['_id'])
            messagebox.showinfo("Deck Deleted", f"Deleted: {deck_doc['name']}")
            # Reload the list
            self.load_saved_decks_list()
        except Exception as e:
            logger.error(f"Failed to delete deck: {e}", exc_info=True)
            messagebox.showerror("Delete Error", f"Failed to delete deck:\n{str(e)}")

    def save_config(self):
        current_settings = dict(self.window_settings)
        position = self.window_position or (self.root.winfo_x(), self.root.winfo_y())
        size = self.window_size or {
            "width": max(int(self.root.winfo_width()), 1),
            "height": max(int(self.root.winfo_height()), 1),
        }
        try:
            screen_pos = [int(position[0]), int(position[1])]
        except Exception:
            screen_pos = [self.root.winfo_x(), self.root.winfo_y()]
        normalized_size = {
            "width": max(int(size.get("width", self.root.winfo_width())), 1),
            "height": max(int(size.get("height", self.root.winfo_height())), 1),
        }
        current_settings.update(
            {
                "format": self.format.get(),
                "screen_pos": screen_pos,
                "window_size": normalized_size,
            }
        )
        try:
            with DECK_SELECTOR_SETTINGS_FILE.open("w", encoding="utf-8") as fh:
                json.dump(current_settings, fh, indent=4)
            self.window_settings = current_settings
        except OSError as exc:
            logger.warning(f"Failed to write deck selector settings: {exc}")


if __name__ == "__main__":
    root = tk.Tk()
    root.attributes("-topmost", "true")
    monitor = MTGDeckSelectionWidget(root)
    root.mainloop()
