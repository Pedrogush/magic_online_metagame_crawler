import time
import tkinter as tk
import json
import os
from pyautogui import pixelMatchesColor
from navigators.mtgo import wait_for_click
from utils.ocr import get_word_on_box
from utils.metagame import get_latest_deck
from loguru import logger

# TODO: make webdriver close upon trade completed
# organize UI so that GUI buttons are divided properly per function
# hide/show buttons for rent functions when appropriate
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


def default_label(root, text=" ", color=CS[0]):
    return tk.Label(
        root,
        text=text,
        font=("calibri", 7, "bold"),
        background=color,
        foreground="black",
        borderwidth=2,
        justify="left",
        relief="solid",
    )


def default_button(root, text, command, color=CS[0], font=("calibri", 7, "bold")):
    return tk.Button(root, text=text, font=font, background=color, command=command)


def default_frame(root, name, color=CS[3]):
    frame = tk.Frame(
        root,
        relief="solid",
        padx=3,
        pady=3,
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
            font=("calibri", 7, "bold"),
            background=CS[2],
            foreground="black",
            relief="solid",
        )
        frame_title.pack(anchor="center", expand=False, fill="both")
    return frame, frame_title


class MTGOpponentDeckSpy:
    def __init__(self):
        self.root = tk.Tk()
        self.root.config(
            background=CS[3],
            relief="solid",
            bg=CS[2],
            highlightbackground=CS[3],
            highlightthickness=1,
            width=200,
            height=100,
        )
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", "true")
        self.ui_make_components()
        self.load_cache()
        self.label = tk.Label(self.frame_bottom, text="Click here to move", bg="bisque3")
        self.exit_button = tk.Button(self.frame_bottom, text="Exit", command=self.root.quit, bg="bisque4")
        self.exit_button.pack(anchor="center", fill="x", side=tk.BOTTOM, expand=False)
        self.label.pack(side="right", fill="both", expand=True)
        self.label.bind("<ButtonPress-1>", self.start_move)
        self.label.bind("<ButtonRelease-1>", self.stop_move)
        self.label.bind("<B1-Motion>", self.do_move)
        self.root.bind("<Enter>", self.show_bottom_frame)
        self.last_looked_at_ts = time.time()
        self.load_config()
        self.player_name: str = get_word_on_box((self.box), "black")
        self.last_seen_deck = ""
        self.updating = False
        self.update_deck()

    def hide_bottom_frame(self):
        self.frame_bottom.forget()

    def show_bottom_frame(self, event):
        self.frame_bottom.pack(anchor="center", fill="x", side=tk.BOTTOM, expand=False)

    def start_move(self, event):
        self.frame_bottom.forget()
        self.root.x = event.x
        self.root.y = event.y

    def stop_move(self, event):
        self.root.x = None
        self.root.y = None

    def do_move(self, event):
        deltax = event.x - self.root.x
        deltay = event.y - self.root.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
        self.save_config()

    def ui_make_components(self):
        self.root.title("Opponent Identifier")
        # frames
        self.frame_top, self.frame_title_top = default_frame(self.root, "Playing", color=CS[1])
        self.frame_bottom, self.frame_title_bottom = default_frame(self.root, "Configuration", color=CS[3])
        # labels
        self.opponent_deck_label = default_label(self.frame_top)
        self.deck_monitor_instructions_label = default_label(self.frame_top)
        self.configure_box_button = default_button(self.frame_bottom, "Configure box", self.update_box)
        self.format = tk.StringVar(value=FORMAT_OPTIONS[0])
        self.choose_format_frame = tk.Frame(self.frame_bottom, background=CS[2])
        self.choose_format_button = tk.OptionMenu(
            self.choose_format_frame,
            self.format,
            FORMAT_OPTIONS[0],
            *FORMAT_OPTIONS[1:],
            command=lambda x: self.save_config(),
        )
        self.choose_format_button.config(
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
        self.choose_format_button["menu"].config(
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
        self.hide_widget_button = default_button(
            self.frame_bottom,
            "Hide",
            self.hide_bottom_frame,
            color=CS[2],
            font=("calibri", 10, "bold"),
        )
        self.ui_pack_components()

    def ui_pack_components(self):
        self.opponent_deck_label.pack(anchor="center", expand=False, fill="both")
        self.choose_format_button.pack(anchor="center", fill="both", side=tk.RIGHT, expand=True)
        self.choose_format_frame.pack(anchor="center", fill="both", side=tk.RIGHT, expand=True)
        self.configure_box_button.pack(anchor="center", fill="both", side=tk.LEFT, expand=True)
        self.hide_widget_button.pack(anchor="center", fill="both", side=tk.BOTTOM, expand=True)
        self.frame_top.pack(anchor="center", fill="both", side=tk.TOP, expand=True)
        self.frame_bottom.pack(anchor="center", fill="x", side=tk.BOTTOM, expand=False)

    def update_box(self):
        self.deck_monitor_instructions_label.pack(anchor="center", expand=True, fill="both", side=tk.TOP)
        self.updating = True
        logger.debug("Updating box")
        self.deck_monitor_instructions_label.config(text="Click on the top left corner of the box")
        self.deck_monitor_instructions_label.update()
        v1 = wait_for_click()
        self.deck_monitor_instructions_label.config(text="Click on the bottom right corner of the box")
        self.deck_monitor_instructions_label.update()
        v2 = wait_for_click()
        self.box = (v1[0], v1[1], v2[0], v2[1])
        self.vertices = ((v1[0], v1[1]), (v1[0], v2[1]), (v2[0], v1[1]), (v2[0], v2[1]))
        self.deck_monitor_instructions_label.config(text="Box updated, vertices are {}".format(self.vertices))
        self.deck_monitor_instructions_label.update()
        self.save_config()
        time.sleep(1.5)
        self.deck_monitor_instructions_label.pack_forget()
        self.updating = False

    def update_deck(self):
        self.save_config()  # doing this to save the current position of the helper
        if self.updating:
            self.root.after(10000, self.update_deck)
            return
        if not self.check_black_pixels_at_corners():
            self.root.after(10000, self.update_deck)
            self.player_name = "No player detected"
            self.last_seen_deck = ""
            self.refresh_labels()
            return
        self.player_name = get_word_on_box(self.box, "black")
        if self.player_name in self.cache and time.time() - self.cache[self.player_name]["ts"] < 1800:
            self.last_seen_deck = self.cache[self.player_name]["deck"]
            self.root.after(10000, self.update_deck)
            self.refresh_labels()
            return
        self.last_seen_deck = get_latest_deck(self.player_name, self.format)
        self.cache[self.player_name] = {"deck": self.last_seen_deck, "ts": time.time()}
        self.save_cache()
        self.root.after(10000, self.update_deck)
        self.deck_monitor_instructions_label.pack_forget()
        self.refresh_labels()

    def refresh_labels(self):
        self.opponent_deck_label.config(text=f"{self.last_seen_deck}", border=2)
        self.opponent_deck_label.update()

    def save_config(self):
        config = {
            "box": self.box,
            "format": self.choose_format_button.cget("text"),
            "vertices": self.vertices,
            "screen_pos": (self.root.winfo_x(), self.root.winfo_y()),
        }
        with open("deck_monitor_config.json", "w") as f:
            json.dump(config, f, indent=4)

    def load_config(self):
        if os.path.exists("deck_monitor_config.json"):
            try:
                with open("deck_monitor_config.json", "r") as f:
                    config = json.load(f)
                self.box = config["box"]
                self.vertices = config["vertices"]
                self.format = config["format"]
                logger.debug(config["screen_pos"])
                self.root.geometry(f'+{config["screen_pos"][0]}+{config["screen_pos"][1]}')
                self.root.update()
                return
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Invalid config JSON, using defaults: {e}")
        self.box = (93, 320, 311, 358)  # any valid box works fine
        self.vertices = ((93, 320), (93, 358), (311, 320), (311, 358))
        self.format = "Modern"

    def save_cache(self):
        with open("deck_monitor_cache.json", "w") as f:
            json.dump(self.cache, f, indent=4)

    def load_cache(self):
        if os.path.exists("deck_monitor_cache.json"):
            try:
                with open("deck_monitor_cache.json", "r") as f:
                    self.cache = json.load(f)
                return
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid cache JSON, resetting: {e}")
                self.cache = {}
                self.save_cache()
                return
        self.cache = {}

    def check_black_pixels_at_corners(self):
        return all([pixelMatchesColor(v[0], v[1], (0, 0, 0)) for v in self.vertices])


if __name__ == "__main__":
    monitor = MTGOpponentDeckSpy()
    monitor.root.mainloop()
