import json
import time
import tkinter as tk
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from utils.metagame import get_latest_deck
from utils.mtgo_bridge import accept_pending_trades, get_game_state
from utils.paths import (
    CONFIG_DIR,
    DECK_MONITOR_CACHE_FILE,
    DECK_MONITOR_CONFIG_FILE,
)

COLOR_SCHEME = "bisque"
CS = [
    COLOR_SCHEME + "1",
    COLOR_SCHEME + "2",
    COLOR_SCHEME + "3",
    COLOR_SCHEME + "4",
    COLOR_SCHEME,
]

FORMAT_OPTIONS = [
    "Modern",
    "Standard",
    "Pioneer",
    "Legacy",
    "Vintage",
    "Pauper",
    "Commander",
]

LEGACY_DECK_MONITOR_CONFIG = Path("deck_monitor_config.json")
LEGACY_DECK_MONITOR_CACHE = Path("deck_monitor_cache.json")
LEGACY_DECK_MONITOR_CACHE_CONFIG = CONFIG_DIR / "deck_monitor_cache.json"


def default_label(root, text=" ", color=CS[0]):
    return tk.Label(
        root,
        text=text,
        font=("calibri", 9, "bold"),
        background=color,
        foreground="black",
        borderwidth=2,
        justify="left",
        relief="solid",
        wraplength=240,
        anchor="w",
        padx=6,
        pady=4,
    )


def default_button(root, text, command, color=CS[0], font=("calibri", 9, "bold")):
    return tk.Button(root, text=text, font=font, background=color, command=command, relief="solid", borderwidth=2)


def default_frame(root, name, color=CS[3]):
    frame = tk.Frame(
        root,
        relief="solid",
        padx=4,
        pady=4,
        background=color,
        borderwidth=2,
        highlightbackground=color,
        highlightthickness=1,
    )
    frame_title = None
    if name:
        frame_title = tk.Label(
            frame,
            text=name,
            font=("calibri", 9, "bold"),
            background=CS[2],
            foreground="black",
            relief="solid",
        )
        frame_title.pack(anchor="center", expand=False, fill="both")
    return frame, frame_title


class MTGOpponentDeckSpy:
    POLL_INTERVAL_MS = 15_000
    TRADE_INTERVAL_MS = 7_500
    CACHE_TTL = 60 * 30  # 30 minutes

    def __init__(self, master: tk.Misc | None = None):
        if master is None:
            self.root = tk.Tk()
        else:
            self.root = tk.Toplevel(master)
            self.root.transient(master)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.config(
            background=CS[3],
            relief="solid",
            highlightbackground=CS[3],
            highlightthickness=1,
            width=280,
            height=160,
        )
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.username_var = tk.StringVar()
        self.bridge_path_var = tk.StringVar()
        self.auto_accept_var = tk.BooleanVar(value=False)
        self.format = tk.StringVar(value=FORMAT_OPTIONS[0])

        self.cache: Dict[str, Dict[str, Any]] = {}
        self.last_state: dict[str, Any] | None = None
        self.player_name = ""
        self.last_seen_deck = ""
        self.last_event_description = ""
        self.updating = False

        self.ui_make_components()
        self.load_cache()
        self.load_config()

        self.update_deck()
        self.schedule_trade_poll()

    # ------------------------------------------------------------------ UI helpers
    def ui_make_components(self):
        self.frame_top, _ = default_frame(self.root, "Current Opponent", color=CS[1])
        self.frame_bottom, _ = default_frame(self.root, "Settings", color=CS[3])

        self.event_label = default_label(self.frame_top, "No event detected", color=CS[0])
        self.opponent_deck_label = default_label(self.frame_top, "No opponent detected", color=CS[0])
        self.status_label = default_label(self.frame_top, "Waiting for MTGO bridge…", color=CS[0])

        # username + format row
        row_user = tk.Frame(self.frame_bottom, background=CS[2])
        tk.Label(row_user, text="Your MTGO name:", font=("calibri", 9, "bold"), background=CS[2]).pack(
            anchor="w", side=tk.LEFT
        )
        username_entry = tk.Entry(row_user, textvariable=self.username_var, font=("calibri", 9))
        username_entry.bind("<FocusOut>", lambda *_: self.save_config())
        username_entry.pack(anchor="e", side=tk.RIGHT, fill="x", expand=True)

        row_bridge = tk.Frame(self.frame_bottom, background=CS[2])
        tk.Label(row_bridge, text="Bridge path:", font=("calibri", 9, "bold"), background=CS[2]).pack(
            anchor="w", side=tk.LEFT
        )
        bridge_entry = tk.Entry(row_bridge, textvariable=self.bridge_path_var, font=("calibri", 9))
        bridge_entry.bind("<FocusOut>", lambda *_: self.save_config())
        bridge_entry.pack(anchor="e", side=tk.RIGHT, fill="x", expand=True)

        row_format = tk.Frame(self.frame_bottom, background=CS[2])
        tk.Label(row_format, text="Format:", font=("calibri", 9, "bold"), background=CS[2]).pack(
            anchor="w", side=tk.LEFT
        )
        format_menu = tk.OptionMenu(row_format, self.format, *FORMAT_OPTIONS)
        format_menu.config(
            font=("calibri", 9, "bold"),
            background=CS[2],
            relief="solid",
            borderwidth=2,
            fg="black",
            activebackground=CS[3],
            activeforeground="black",
            highlightbackground=CS[3],
        )
        format_menu["menu"].config(font=("calibri", 9, "bold"), background=CS[2], activebackground=CS[3])

        controls_row = tk.Frame(self.frame_bottom, background=CS[2])
        self.auto_accept_checkbox = tk.Checkbutton(
            controls_row,
            text="Auto-accept trades",
            variable=self.auto_accept_var,
            font=("calibri", 9, "bold"),
            background=CS[2],
            command=self.save_config,
            selectcolor=CS[1],
        )
        self.refresh_button = default_button(
            controls_row,
            "Refresh now",
            lambda: self.update_deck(force=True),
            color=CS[2],
        )
        self.hide_widget_button = default_button(
            controls_row,
            "Hide",
            self.hide_bottom_frame,
            color=CS[2],
        )

        self.drag_handle = tk.Label(
            self.frame_bottom,
            text="Click and drag to move • Right-click to close",
            font=("calibri", 8, "bold"),
            background=CS[2],
            foreground="black",
            borderwidth=1,
            relief="solid",
        )

        # Layout
        self.event_label.pack(anchor="center", fill="both", expand=True, padx=2, pady=2)
        self.opponent_deck_label.pack(anchor="center", fill="both", expand=True, padx=2, pady=2)
        self.status_label.pack(anchor="center", fill="both", expand=True, padx=2, pady=2)

        row_user.pack(anchor="center", fill="x", expand=True, padx=2, pady=2)
        row_bridge.pack(anchor="center", fill="x", expand=True, padx=2, pady=2)
        row_format.pack(anchor="center", fill="x", expand=True, padx=2, pady=2)

        controls_row.pack(anchor="center", fill="x", expand=True, padx=2, pady=4)
        self.auto_accept_checkbox.pack(anchor="w", side=tk.LEFT)
        self.refresh_button.pack(anchor="center", side=tk.RIGHT, padx=2)
        self.hide_widget_button.pack(anchor="center", side=tk.RIGHT, padx=2)

        self.drag_handle.pack(anchor="center", fill="x", expand=False, padx=2, pady=2)

        self.frame_top.pack(anchor="center", fill="both", side=tk.TOP, expand=True)
        self.frame_bottom.pack(anchor="center", fill="x", side=tk.BOTTOM, expand=False)

        self.drag_handle.bind("<ButtonPress-1>", self.start_move)
        self.drag_handle.bind("<ButtonRelease-1>", self.stop_move)
        self.drag_handle.bind("<B1-Motion>", self.do_move)
        self.drag_handle.bind("<ButtonPress-3>", lambda _: self.close())
        self.root.bind("<Enter>", self.show_bottom_frame)

    # ------------------------------------------------------------------ Window controls
    def hide_bottom_frame(self):
        self.frame_bottom.forget()

    def show_bottom_frame(self, _):
        self.frame_bottom.pack(anchor="center", fill="x", side=tk.BOTTOM, expand=False)

    def start_move(self, event):
        self.hide_bottom_frame()
        self.root.x = event.x
        self.root.y = event.y

    def stop_move(self, _):
        self.root.x = None
        self.root.y = None
        self.save_config()

    def do_move(self, event):
        if getattr(self.root, "x", None) is None:
            return
        deltax = event.x - self.root.x
        deltay = event.y - self.root.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------ Bridge polling
    def update_deck(self, force: bool = False):
        if self.updating and not force:
            self.root.after(self.POLL_INTERVAL_MS, self.update_deck)
            return

        self.updating = True
        bridge_override = self.bridge_path_var.get().strip() or None
        username = self.username_var.get().strip() or None
        try:
            state = get_game_state(username, bridge_override)
            self.last_state = state
            self.handle_bridge_state(state, username)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to query MTGO bridge: {}", exc)
            self.status_label.config(text=f"Bridge error: {exc}")
        finally:
            self.save_config()
            self.updating = False
            self.root.after(self.POLL_INTERVAL_MS, self.update_deck)

    def handle_bridge_state(self, state: dict[str, Any], username: str | None) -> None:
        event_info = state.get("eventInfo") or {}
        match_info = state.get("match") or {}
        players = state.get("players") or []

        description = (
            event_info.get("description")
            or match_info.get("challengeText")
            or (match_info.get("id") and f"Match #{match_info['id']}")
            or "No active matches detected"
        )
        self.last_event_description = description
        self.event_label.config(text=description)

        if not players:
            self.player_name = ""
            self.last_seen_deck = ""
            self.status_label.config(text="Waiting for MTGO game to start…")
            self.refresh_labels()
            return

        self_player = next((p for p in players if p.get("isSelf")), None)
        if not self_player and username:
            self_player = next(
                (p for p in players if p.get("name", "").lower() == username.lower()),
                None,
            )
        if not self_player and len(players) >= 1 and not username:
            self_player = players[0]
            self.username_var.set(self_player.get("name", ""))

        opponents = [p for p in players if p is not self_player]
        opponent = opponents[0] if opponents else None

        if opponent is None:
            self.player_name = ""
            self.last_seen_deck = ""
            self.status_label.config(text="No opponent detected yet.")
            self.refresh_labels()
            return

        self.player_name = opponent.get("name", "Unknown opponent")
        deck = self._lookup_deck(self.player_name)
        self.last_seen_deck = deck

        self.status_label.config(
            text=f"{self.player_name} • Clock: {self._describe_clock(opponent)}"
        )
        self.refresh_labels()

    def _lookup_deck(self, opponent_name: str) -> str:
        cached = self.cache.get(opponent_name)
        now = time.time()
        if cached and now - cached.get("ts", 0) < self.CACHE_TTL:
            return cached.get("deck", "")

        deck = get_latest_deck(opponent_name, self.format)
        self.cache[opponent_name] = {"deck": deck, "ts": now}
        self.save_cache()
        return deck

    def _describe_clock(self, player: dict[str, Any]) -> str:
        seconds = int(player.get("clockSeconds") or 0)
        minutes, secs = divmod(max(0, seconds), 60)
        return f"{minutes:02d}:{secs:02d}"

    def refresh_labels(self):
        if self.player_name and self.last_seen_deck:
            self.opponent_deck_label.config(text=f"{self.player_name}: {self.last_seen_deck}")
        elif self.player_name:
            self.opponent_deck_label.config(text=f"{self.player_name}: deck not found")
        else:
            self.opponent_deck_label.config(text="Opponent not detected")
        self.opponent_deck_label.update()

    # ------------------------------------------------------------------ Trade automation
    def schedule_trade_poll(self):
        self.root.after(self.TRADE_INTERVAL_MS, self.poll_trades)

    def poll_trades(self):
        if self.auto_accept_var.get():
            bridge_override = self.bridge_path_var.get().strip() or None
            try:
                result = accept_pending_trades(bridge_override)
                if result.get("accepted"):
                    partner = result.get("partner") or "Unknown"
                    logger.info("Accepted pending trade from {}", partner)
                    self.status_label.config(text=f"Accepted trade from {partner}")
            except Exception as exc:  # noqa: BLE001
                logger.debug("Auto-accept trade failed: {}", exc)
        self.schedule_trade_poll()

    # ------------------------------------------------------------------ Persistence
    def save_config(self):
        config = {
            "format": self.format.get(),
            "screen_pos": (self.root.winfo_x(), self.root.winfo_y()),
            "mtgo_username": self.username_var.get().strip(),
            "bridge_path": self.bridge_path_var.get().strip(),
            "auto_accept_trades": self.auto_accept_var.get(),
        }
        try:
            DECK_MONITOR_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with DECK_MONITOR_CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except OSError as exc:
            logger.warning(f"Failed to write deck monitor config: {exc}")

    def load_config(self):
        source_file = DECK_MONITOR_CONFIG_FILE
        legacy_source = False
        if not source_file.exists() and LEGACY_DECK_MONITOR_CONFIG.exists():
            source_file = LEGACY_DECK_MONITOR_CONFIG
            legacy_source = True
            logger.warning("Loaded legacy deck_monitor_config.json; migrating to config/")

        if source_file.exists():
            try:
                with source_file.open("r", encoding="utf-8") as f:
                    config = json.load(f)
                fmt = config.get("format")
                if fmt in FORMAT_OPTIONS:
                    self.format.set(fmt)
                self.username_var.set(config.get("mtgo_username", ""))
                self.bridge_path_var.set(config.get("bridge_path", ""))
                self.auto_accept_var.set(config.get("auto_accept_trades", False))

                screen_pos = config.get("screen_pos")
                if screen_pos:
                    self.root.geometry(f"+{screen_pos[0]}+{screen_pos[1]}")
                self.root.update()

                if legacy_source:
                    try:
                        with DECK_MONITOR_CONFIG_FILE.open("w", encoding="utf-8") as target:
                            json.dump(config, target, indent=4)
                        if source_file != DECK_MONITOR_CONFIG_FILE:
                            source_file.unlink(missing_ok=True)
                    except OSError as exc:
                        logger.warning(f"Failed to migrate deck monitor config: {exc}")
                return
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f"Invalid config JSON, using defaults: {exc}")

    def save_cache(self):
        try:
            DECK_MONITOR_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with DECK_MONITOR_CACHE_FILE.open("w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=4)
        except OSError as exc:
            logger.warning(f"Failed to write deck monitor cache: {exc}")

    def load_cache(self):
        source_file = DECK_MONITOR_CACHE_FILE
        legacy_source = False
        if not source_file.exists() and LEGACY_DECK_MONITOR_CACHE_CONFIG.exists():
            source_file = LEGACY_DECK_MONITOR_CACHE_CONFIG
            legacy_source = True
            logger.warning("Loaded legacy deck_monitor_cache.json from config/; migrating to cache/")
        if not source_file.exists() and LEGACY_DECK_MONITOR_CACHE.exists():
            source_file = LEGACY_DECK_MONITOR_CACHE
            legacy_source = True
            logger.warning("Loaded legacy deck_monitor_cache.json from project root; migrating to cache/")

        if source_file.exists():
            try:
                with source_file.open("r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                if legacy_source:
                    try:
                        DECK_MONITOR_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                        with DECK_MONITOR_CACHE_FILE.open("w", encoding="utf-8") as target:
                            json.dump(self.cache, target, indent=4)
                        if source_file != DECK_MONITOR_CACHE_FILE:
                            source_file.unlink(missing_ok=True)
                    except OSError as exc:
                        logger.warning(f"Failed to migrate deck monitor cache: {exc}")
                return
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f"Invalid cache JSON, resetting: {exc}")
        self.cache = {}

    # ------------------------------------------------------------------ teardown
    def close(self):
        if self.root:
            self.root.destroy()


if __name__ == "__main__":
    monitor = MTGOpponentDeckSpy()
    monitor.root.mainloop()
