import time
import tkinter as tk
from tkinter import ttk
import json
import threading
from loguru import logger
from utils.deck import deck_to_dictionary, add_dicts
from navigators.mtggoldfish import (
    get_archetypes,
    get_archetype_stats,
    get_archetype_decks,
    download_deck,
)

# TODO: add some deck managing stuff (save decks, access list of saved decks, auto-save, etc)

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
CONFIG = json.load(open("config.json"))


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


def b_button(root, text, command, color=CS[0], font=("calibri", 13, "bold")):
    return tk.Button(root, text=text, font=font, background=color, command=command, height=1)


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


def b_frame(root, color=CS[3]):
    frame = tk.Frame(root, relief="solid", padx=3, pady=0, background=color, borderwidth=0, height=15)
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
        self.last_looked_at_ts = time.time()
        self.last_seen_deck = ""
        self.updating = False
        self.user_has_edited_deck = False
        self.currently_selected_deck = {}
        self.deck_buffer: dict = {}
        self.decks_added = 0
        self.archetypes = []
        self.archetype_stats = {}
        self.loading = False
        self.loading_daily_average = False  # Prevent simultaneous daily average loads
        self.ui_make_components()
        # Load archetypes asynchronously after window is shown
        self.root.after(100, self.lazy_load_archetypes)

    def ui_reset_to_archetype_selection(self):
        self.textbox.delete("1.0", tk.END)
        self.deck_buffer = {}
        self.decks_added = 0
        self.listbox_button.unbind("<<ListboxSelect>>")
        self.listbox_button.config(text="Select archetype", command=self.select_archetype)
        repopulate_listbox(self.listbox, [archetype["name"] for archetype in self.archetypes])
        if hasattr(self, "reset_button"):
            self.reset_button.grid_forget()

    def ui_make_components(self):
        self.root.title("MTG Deck Research Browser")
        self.ui_create()
        # Don't populate yet - will be done lazily
        self.ui_bind_components()

    def ui_create(self):
        self.F_top = frame(self.root, "", color="bisque4")
        self.F_top.grid(column=0, row=0, sticky="nsew")
        self.F_top_left = frame(self.F_top, "Deck Browser", color=CS[1])
        self.F_top_left.rowconfigure(3, weight=1)
        self.F_top_left.grid(column=0, row=1, sticky="nsew")
        self.F_top_right = frame(self.F_top, "Decklist", color=CS[1])
        self.F_top_right.grid(column=1, row=1, sticky="nsew")
        self.F_top_right_top = frame(self.F_top_right, "", color=CS[2])
        self.F_top_right_top.grid(column=0, row=1, sticky="nsew")
        self.F_top_textbox = frame(self.F_top_right, "", color=CS[2])
        self.F_top_textbox.grid(column=0, row=2, sticky="nsew")
        self.F_top_textbox.rowconfigure(0, weight=1)
        self.F_bottom = frame(self.root, "Configuration", color=CS[3])
        self.F_bottom.grid(column=0, row=2, sticky="nsew")

        self.save_deck_button = button(self.F_top_right_top, "Save deck", self.save_deck_as)
        self.save_deck_button.grid(column=0, row=0, sticky="nsew")
        self.add_deck_to_buffer_button = button(self.F_top_right_top, "Add deck to buffer", self.add_deck_to_buffer)
        self.add_deck_to_buffer_button.grid(column=1, row=0, sticky="nsew")
        self.make_average_deck_button = button(self.F_top_right_top, "Mean of buffer", self.make_average_deck)
        self.make_average_deck_button.grid(column=2, row=0, sticky="nsew")
        self.listbox_button = button(self.F_top_left, "Select archetype", self.select_archetype)
        self.listbox_button.grid(column=0, row=1, sticky="nsew")
        self.listbox = tk.Listbox(
            self.F_top_left,
            selectmode=tk.SINGLE,
            background=CS[4],
            foreground="black",
            font=("calibri", 15, "bold"),
        )
        self.listbox.grid(column=0, row=3, sticky="nsew")
        self.listbox_scrollbar = tk.Scrollbar(self.F_top_left, orient="vertical")
        self.listbox_scrollbar.grid(column=1, row=3, sticky="nsew")
        self.listbox.config(yscrollcommand=self.listbox_scrollbar.set)
        self.listbox_scrollbar.config(command=self.listbox.yview)
        self.textbox = tk.Text(
            self.F_top_textbox,
            font=("calibri", 15, "bold"),
            background=CS[1],
            foreground="black",
        )
        self.textbox.grid(column=0, row=0, sticky="nsew")
        self.choose_format_button = tk.OptionMenu(
            self.F_bottom,
            self.format,
            FORMAT_OPTIONS[0],
            *FORMAT_OPTIONS[1:],
            command=lambda x: self.choose_format_button_clicked(),
        )
        self.choose_format_button.grid(column=0, row=0, sticky="nsew")
        choose_format_button_config(self.choose_format_button)

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
            try:
                mtg_format = self.format.get()
                logger.info(f"Loading archetypes for {mtg_format}...")

                # Fetch data (this is the slow part)
                archetypes = get_archetypes(mtg_format)
                archetype_stats = get_archetype_stats(mtg_format)

                # Update UI on main thread
                self.root.after(0, lambda: self.on_archetypes_loaded(archetypes, archetype_stats))
            except Exception as e:
                logger.error(f"Failed to load archetypes: {e}")
                self.root.after(0, lambda: self.on_archetypes_error(str(e)))

        # Start background thread
        thread = threading.Thread(target=load_in_background, daemon=True)
        thread.start()

    def on_archetypes_loaded(self, archetypes, archetype_stats):
        """Called on main thread when archetypes are loaded"""
        self.archetypes = archetypes
        self.archetype_stats = archetype_stats
        self.loading = False

        # Update listbox
        self.listbox.delete(0, tk.END)
        for index, archetype in enumerate(self.archetypes):
            self.listbox.insert(index, archetype["name"])

        self.listbox_button.config(state="normal")
        logger.info(f"Loaded {len(self.archetypes)} archetypes")

    def on_archetypes_error(self, error_msg):
        """Called on main thread if loading fails"""
        self.loading = False
        self.listbox.delete(0, tk.END)
        self.listbox.insert(0, f"❌ Error: {error_msg[:50]}")
        self.listbox.insert(1, "Click 'Select archetype' to retry")
        self.listbox_button.config(state="normal")

    def save_deck_as(self):
        logger.debug(self.currently_selected_deck)
        if not self.currently_selected_deck:
            date = time.strftime("%Y-%m-%d-%H-%M-%S")
            deck_name = f"edited_deck_{date}.txt"
        else:
            deck_name = f"{format_deck_name(self.currently_selected_deck)}.txt"
        with open(CONFIG["deck_selector_save_path"] + deck_name, "w") as f:
            f.write(self.textbox.get("1.0", tk.END))

    def add_deck_to_buffer(self):
        self.deck_buffer = add_dicts(self.deck_buffer, deck_to_dictionary(self.textbox.get("1.0", tk.END)))
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
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert("1.0", deck_string)
        lines = self.textbox.get("1.0", tk.END).split("\n")
        self.set_textbox_buttons(lines)
        self.decks_added = 0
        self.deck_buffer = {}

    def textbox_on_change(self, event):
        self.last_event = event
        self.user_has_edited_deck = True

    def ui_bind_components(self):
        self.textbox.bind("<Key>", self.textbox_on_change)

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
        self.make_daily_average_deck_button.grid(column=3, row=0, sticky="nsew")
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
            self.textbox.delete("1.0", tk.END)
            self.textbox.insert("1.0", "No decks from today found in this archetype")
            return

        # Show loading in textbox
        self.loading_daily_average = True
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert("1.0", f"⏳ Loading {len(decks_from_today)} decks from today...\n")
        self.make_daily_average_deck_button.config(state="disabled")
        logger.info(f"Starting to load {len(decks_from_today)} decks for daily average")

        def update_progress(current, total):
            """Thread-safe progress update"""
            def _update():
                self.textbox.delete("1.0", tk.END)
                self.textbox.insert("1.0", f"⏳ Loading deck {current}/{total}...\n")
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
                        with open("curr_deck.txt", "r", encoding="utf-8") as f:
                            deck_str = f.read()
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
                    self.textbox.delete("1.0", tk.END)
                    self.textbox.insert("1.0", f"❌ Error loading decks:\n{str(e)}")
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
            self.textbox.delete("1.0", tk.END)
            self.textbox.insert("1.0", f"❌ Error creating average:\n{str(e)}")
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
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert("1.0", "⏳ Loading deck...")
        logger.debug(f"Loading deck: {deck['number']}")

        def load_deck_in_background():
            try:
                download_deck(deck["number"])

                # Read with proper file handling
                try:
                    with open("curr_deck.txt", "r", encoding="utf-8") as f:
                        deck_content = f.read()
                except Exception as file_error:
                    logger.error(f"Failed to read deck file: {file_error}")
                    raise

                logger.debug(f"Successfully loaded deck: {deck['number']}")
                self.root.after(0, lambda: self.on_deck_content_loaded(deck_content))

            except Exception as e:
                logger.error(f"Failed to load deck: {e}", exc_info=True)
                def _error():
                    self.textbox.delete("1.0", tk.END)
                    self.textbox.insert("1.0", f"❌ Error loading deck:\n{str(e)}")
                self.root.after(0, _error)

        thread = threading.Thread(target=load_deck_in_background, daemon=True)
        thread.start()

    def on_deck_content_loaded(self, deck_content):
        """Called when deck content is downloaded"""
        try:
            self.textbox.delete("1.0", tk.END)
            self.textbox.insert("1.0", deck_content)
            lines = self.textbox.get("1.0", tk.END).split("\n")
            self.set_textbox_buttons(lines)
        except Exception as e:
            logger.error(f"Error displaying deck: {e}")
            self.textbox.delete("1.0", tk.END)
            self.textbox.insert("1.0", f"❌ Error displaying deck:\n{str(e)}")

    def set_textbox_buttons(self, lines):
        self.q_btn_frames = []
        sideboard_index = lines.index("")
        is_sideboard = False
        self.textbox.delete("1.0", tk.END)
        for i, line in enumerate(lines):
            FONT = ("verdana", 7)
            if not line.strip():
                empty_frame = b_frame(self.F_top_textbox, color=CS[2])
                self.textbox.window_create(f'{i+1}.0', window=empty_frame)
                self.textbox.insert(tk.END, "\n")
                self.q_btn_frames.append(empty_frame)
                continue
            if i > sideboard_index:
                is_sideboard = True
            F_edit_deck = self.create_F_edit_deck(line, is_sideboard)
            self.q_btn_frames.append(F_edit_deck)
            self.textbox.insert(tk.END, line)
            self.textbox.window_create(f'{i+1}.0', window=F_edit_deck)
            self.textbox.insert(tk.END, "\n")

    def set_textbox_scrollbar(self):
        self.textbox_scrollbar = tk.Scrollbar(self.F_top_textbox, orient="vertical")
        self.textbox_scrollbar.config(command=self.textbox.yview)

    def increment_card(self, line, is_sideboard=False):
        card = " ".join(line.split(" ")[1:])
        lines = self.textbox.get("1.0", tk.END).split("\n")
        logger.debug(lines)
        num_occurrences = len([card_description for card_description in lines if card in card_description])
        if num_occurrences == 0:
            logger.debug(f"{card} not found in decklist")
            return
        index = [lines.index(card_description) for card_description in lines if card in card_description][0]
        if num_occurrences == 2:
            index = [lines.index(lin) for lin in lines if card in lin][is_sideboard]
        curr_line = lines[index]
        amount = int(float(curr_line.split(" ")[0]))
        amount += 1
        line = f"{str(amount)} {''.join(card)}"
        lines[index] = line
        self.textbox.replace(f"{index + 1}.0", f"{index + 1}.end", line)
        F_edit_deck = self.create_F_edit_deck(line, is_sideboard)
        self.q_btn_frames.append(F_edit_deck)
        self.textbox.window_create(f"{index + 1}.0", window=F_edit_deck)

    def decrement_card(self, line, is_sideboard=False):
        card = " ".join(line.split(" ")[1:])
        lines = self.textbox.get("1.0", tk.END).split("\n")
        logger.debug(lines)
        num_occurrences = len([card_description for card_description in lines if card in card_description])
        if num_occurrences == 0:
            logger.debug(f"{card} not found in decklist")
            return
        index = [lines.index(card_description) for card_description in lines if card in card_description][0]
        if num_occurrences == 2:
            index = [lines.index(lin) for lin in lines if card in lin][is_sideboard]
        curr_line = lines[index]
        amount = int(float(curr_line.split(" ")[0]))
        amount -= 1
        line = f"{str(amount)} {''.join(card)}"
        lines[index] = line
        self.textbox.replace(f"{index + 1}.0", f"{index + 1}.end", line)
        F_edit_deck = self.create_F_edit_deck(line, is_sideboard)
        self.q_btn_frames.append(F_edit_deck)
        self.textbox.window_create(f"{index + 1}.0", window=F_edit_deck)

    def create_F_edit_deck(self, line, is_sideboard):
        F_edit_deck = b_frame(self.F_top_textbox, color=CS[2])
        self.q_btn_frames.append(F_edit_deck)
        FONT = ("verdana", 9, "bold")
        plus_btn = b_button(F_edit_deck, "+", lambda line=line: self.increment_card(line, is_sideboard), font=FONT)
        minus_btn = b_button(F_edit_deck, "-", lambda line=line: self.decrement_card(line, is_sideboard), font=FONT)
        remove_btn = b_button(F_edit_deck, "X", lambda line=line: self.remove_card(line, is_sideboard), font=FONT)
        plus_btn.grid(column=1, row=0)
        minus_btn.grid(column=2, row=0)
        remove_btn.grid(column=3, row=0)
        return F_edit_deck

    def remove_card(self, line, is_sideboard):
        card = " ".join(line.split(" ")[1:])
        lines = self.textbox.get("1.0", tk.END).split("\n")
        num_occurrences = len([card_description for card_description in lines if card in card_description])
        index = [lines.index(card_description) for card_description in lines if card in card_description][0]
        if num_occurrences == 2:
            index = [lines.index(lin) for lin in lines if card in lin][is_sideboard]
        self.textbox.replace(f"{index + 1}.0", f"{index + 2}.0", '')

    def select_deck(self):
        # Simply displays the selected deck without any automation
        selected = self.listbox.curselection()
        logger.debug(selected)
        if not selected:
            return
        selected = selected[0]
        logger.debug(selected)
        self.currently_selected_deck = self.decks[selected]
        logger.debug(self.currently_selected_deck)

    def save_config(self):
        config = {
            "format": self.format.get(),
            "screen_pos": (self.root.winfo_x(), self.root.winfo_y()),
        }
        json.dump(config, open("deck_monitor_config.json", "w"), indent=4)


if __name__ == "__main__":
    root = tk.Tk()
    root.attributes("-topmost", "true")
    monitor = MTGDeckSelectionWidget(root)
    root.mainloop()
