import time
import tkinter as tk
import json
import pyperclip
from navigators.mtgo import login
from loguru import logger
from utils.deck import deck_to_dictionary, add_dicts
from navigators.mtggoldfish import (
    get_archetypes,
    get_archetype_decks,
    download_deck,
)
from navigators.manatraders import (
    Webdriver,
    login as manatraders_login,
    rent_deck,
    receive_cards,
    return_cards,
)
from navigators.mtgo import (
    register_deck,
)

# TODO: add buttons
# return to select archetype state
# clear buffer
# clear list
# round decklist down
# round decklist up
# round decklist
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
        frame_title.pack(anchor="center", expand=False, fill="both")
    return frame


def b_frame(root, color=CS[3]):
    frame = tk.Frame(root, relief="solid", padx=3, pady=0, background=color, borderwidth=0, height=15)
    frame.pack(anchor="center", fill="y", side=tk.TOP, expand=True)
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
        self.ui_make_components()

    def ui_reset_to_archetype_selection(self):
        self.textbox.delete("1.0", tk.END)
        self.deck_buffer = {}
        self.decks_added = 0
        self.listbox_button.unbind("<<ListboxSelect>>")
        self.listbox_button.config(text="Select archetype", command=self.select_archetype)
        repopulate_listbox(self.listbox, [archetype["name"] for archetype in self.archetypes])
        self.reset_button.forget()

    def ui_make_components(self):
        self.root.title("MTG Helper")
        self.ui_create_frames()
        self.ui_create_buttons()
        self.ui_create_listbox()
        self.ui_populate_archetypes()
        self.ui_create_textbox()
        self.ui_pack_components()
        self.ui_bind_components()

    def ui_create_frames(self):
        self.F_top = frame(self.root, "", color="bisque4")
        self.F_top_left = frame(self.F_top, "Manatraders Card Rental Automation", color=CS[1])
        self.F_top_right = frame(self.F_top, "Decklist", color=CS[1])
        self.F_top_right_top = frame(self.F_top_right, "", color=CS[2])
        self.F_top_textbox = frame(self.F_top_right, "", color=CS[2])
        self.F_bottom = frame(self.root, "Configuration", color=CS[3])

    def ui_create_buttons(self):
        self.save_deck_button: tk.Button
        self.save_deck_button = button(self.F_top_right_top, "Save deck", self.save_deck_as)
        self.add_deck_to_buffer_button = button(self.F_top_right_top, "Add deck to buffer", self.add_deck_to_buffer)
        self.make_average_deck_button = button(self.F_top_right_top, "Mean of buffer", self.make_average_deck)
        self.make_daily_average_deck_button = button(self.F_top_right_top, "Day's Average", self.set_daily_average_deck)
        self.reset_button = button(self.F_top_left, "Reset", self.ui_reset_to_archetype_selection)
        self.login_button = button(self.F_bottom, "MTGO Login", login)
        self.listbox_button = button(self.F_top_left, "Select archetype", self.select_archetype)
        self.return_cards_button = button(self.F_top_left, "Return cards", self.return_cards)
        self.ui_format_menu()

    def ui_format_menu(self):
        self.choose_format_button = tk.OptionMenu(
            self.F_bottom,
            self.format,
            FORMAT_OPTIONS[0],
            *FORMAT_OPTIONS[1:],
            command=lambda x: self.choose_format_button_clicked(),
        )
        choose_format_button_config(self.choose_format_button)

    def choose_format_button_clicked(self):
        self.ui_populate_archetypes()
        self.ui_reset_to_archetype_selection()
        self.save_config()

    def ui_populate_archetypes(self):
        mtg_format = self.format.get()
        self.archetypes = get_archetypes(mtg_format)
        for index, archetype in enumerate(self.archetypes):
            self.listbox.insert(index, archetype["name"])

    def ui_create_listbox(self):
        self.listbox = tk.Listbox(
            self.F_top_left,
            selectmode=tk.SINGLE,
            background=CS[4],
            foreground="black",
            font=("calibri", 15, "bold"),
        )
        self.listbox_scrollbar = tk.Scrollbar(self.listbox, orient="vertical")

    def ui_create_textbox(self):
        self.textbox = tk.Text(
            self.F_top_textbox,
            font=("calibri", 15, "bold"),
            background=CS[1],
            foreground="black",
        )
        self.textbox_plus_buttons: list[tk.Button] = []
        self.textbox_minus_buttons: list[tk.Button] = []
        self.textbox_remove_buttons: list[tk.Button] = []

    def save_deck_as(self):
        logger.debug(self.currently_selected_deck)
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

    def ui_pack_components(self):
        self.login_button.pack(anchor="center", fill="x", side=tk.LEFT, expand=False)
        self.choose_format_button.pack(anchor="center", fill="both", side=tk.RIGHT, expand=False)
        self.listbox.pack(anchor="center", fill="both", side=tk.BOTTOM, expand=True)
        self.listbox_button.pack(anchor="center", fill="both", side=tk.BOTTOM, expand=False)
        self.listbox_scrollbar.pack(anchor="center", fill="y", side=tk.RIGHT)
        self.return_cards_button.pack(anchor="center", fill="both", side=tk.BOTTOM, expand=False)
        self.save_deck_button.pack(anchor="center", fill="both", side=tk.LEFT, expand=False)
        self.add_deck_to_buffer_button.pack(anchor="center", fill="both", side=tk.LEFT, expand=False)
        self.make_average_deck_button.pack(anchor="center", fill="both", side=tk.LEFT, expand=False)
        self.textbox.pack(anchor="center", fill="both", side=tk.LEFT, expand=True)
        self.F_top.pack(anchor="center", fill="both", side=tk.TOP, expand=True)
        self.F_top_right.pack(anchor="center", fill="both", side=tk.RIGHT, expand=True)
        self.F_top_right_top.pack(anchor="center", fill="both", side=tk.TOP, expand=False)
        self.F_top_left.pack(anchor="center", fill="both", side=tk.LEFT, expand=True)
        self.F_bottom.pack(anchor="center", fill="x", side=tk.BOTTOM, expand=False)
        self.F_top_textbox.pack(anchor="center", fill="both", side=tk.RIGHT, expand=False)

    def select_archetype(self):
        selected = self.listbox.curselection()
        if not selected:
            return
        selected = selected[0]
        archetype = self.archetypes[selected]["href"]
        self.decks = get_archetype_decks(archetype)
        repopulate_listbox(self.listbox, [format_deck_name(deck) for deck in self.decks])
        self.listbox_button.config(text="Select deck", command=self.select_deck)
        self.listbox.bind("<<ListboxSelect>>", self.set_textbox)
        self.reset_button.pack(anchor="center", fill="both", side=tk.BOTTOM, expand=False)
        self.make_daily_average_deck_button.pack(anchor="center", fill="both", side=tk.BOTTOM, expand=False)

    def set_daily_average_deck(self):
        today = time.strftime("%Y-%m-%d")
        decks_from_today = [d for d in self.decks if today.lower() in d["date"]]
        self.deck_buffer = {}
        self.decks_added = 0
        for deck in decks_from_today:
            download_deck(deck["number"])
            deck_str = open("curr_deck.txt").read()
            self.deck_buffer = add_dicts(self.deck_buffer, deck_to_dictionary(deck_str))
            self.decks_added += 1
        self.make_average_deck()

    def set_textbox(self, event):
        selected = self.listbox.curselection()
        if not selected:
            return
        selected = selected[0]
        self.currently_selected_deck = self.decks[selected]
        deck = self.decks[selected]
        self.textbox.delete("1.0", tk.END)
        download_deck(deck["number"])
        self.textbox.insert("1.0", open("curr_deck.txt").read())
        lines = self.textbox.get("1.0", tk.END).split("\n")        
        self.set_textbox_buttons(lines)

    def set_textbox_buttons(self, lines):
        accum_padding = 0
        self.q_btn_frames = []
        for line in lines:
            FONT = ("verdana", 7)
            if not line.strip():
                empty_frame = b_frame(self.F_top_textbox, color=CS[2])
                empty_frame.pack(anchor="center", fill="both", side=tk.TOP, expand=False)
                self.q_btn_frames.append(empty_frame)
                continue
            qtn_btns_frame = b_frame(self.F_top_textbox, color=CS[2])
            self.q_btn_frames.append(qtn_btns_frame)
            plus_btn = b_button(qtn_btns_frame, "+", lambda line=line: self.increment_card(line), font=FONT)
            minus_btn = b_button(qtn_btns_frame, "-", lambda line=line: self.decrement_card(line), font=FONT)
            remove_btn = b_button(qtn_btns_frame, "X", lambda line=line: self.remove_card(line), font=FONT)
            plus_btn.pack(anchor="center", fill="x", side=tk.LEFT, expand=False)
            minus_btn.pack(anchor="center", fill="x", side=tk.LEFT, expand=False)
            remove_btn.pack(anchor="center", fill="x", side=tk.LEFT, expand=False)
            if accum_padding < 8:
                qtn_btns_frame.pack(anchor="center", fill="both", side=tk.TOP, expand=False, ipady=2)
                accum_padding += 2
                continue
            qtn_btns_frame.pack(anchor="center", fill="both", side=tk.TOP, expand=False, ipady=0)
            accum_padding = 0

    def increment_card(self, line):
        card = ' '.join(line.split(" ")[1:])
        lines = self.textbox.get("1.0", tk.END).split("\n")
        index = [lines.index(card_description) for card_description in lines if card in card_description][0]
        for curr_line in lines:
            if card not in curr_line:
                continue
            amount = int(float(curr_line.split(" ")[0]))
            amount += 1
            line = f"{str(amount)} {''.join(card)}"
        lines[index] = line
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert("1.0", "\n".join(lines))

    def decrement_card(self, line):
        card = ' '.join(line.split(" ")[1:])
        lines = self.textbox.get("1.0", tk.END).split("\n")
        index = [lines.index(card_description) for card_description in lines if card in card_description][0]
        for curr_line in lines:
            if card not in curr_line:
                continue
            amount = int(float(curr_line.split(" ")[0]))
            amount -= 1
            line = f"{str(amount)} {''.join(card)}"
        lines[index] = line
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert("1.0", "\n".join(lines))

    def remove_card(self, line):
        card = ' '.join(line.split(" ")[1:])
        lines = self.textbox.get("1.0", tk.END).split("\n")
        index = [lines.index(card_description) for card_description in lines if card in card_description][0]
        lines.pop(index)
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert("1.0", "\n".join(lines))
        self.q_btn_frames[index].pack_forget()
        self.q_btn_frames.pop(index)

    def select_deck(self):
        selected = self.listbox.curselection()
        logger.debug(selected)
        if not selected:
            return
        selected = selected[0]
        logger.debug(selected)
        self.currently_selected_deck = self.decks[selected]
        logger.debug(self.currently_selected_deck)
        self.root.iconify()
        webdriver = Webdriver()
        webdriver.driver.maximize_window()
        manatraders_login(webdriver.driver, webdriver.achains)
        if self.user_has_edited_deck:
            # if the user edits the decks cards, rent the version they edited
            pyperclip.copy(self.textbox.get("1.0", tk.END))
            rent_deck(webdriver.driver, webdriver.achains)
        else:
            rent_deck(
                webdriver.driver,
                webdriver.achains,
                self.currently_selected_deck["number"],
            )
        time.sleep(5)
        receive_cards(webdriver.driver)
        time.sleep(10)
        register_deck(self.currently_selected_deck["name"] + self.currently_selected_deck["number"])
        self.root.deiconify()
        webdriver.driver.quit()
        repopulate_listbox(self.listbox, [archetype["name"] for archetype in self.archetypes])
        self.listbox_button.config(text="Select archetype", command=self.select_archetype)
        self.user_has_edited_deck = False
        self.listbox.unbind("<<ListboxSelect>>")

    def return_cards(self):
        self.root.iconify()
        webdriver = Webdriver()
        webdriver.driver.maximize_window()
        manatraders_login(webdriver.driver, webdriver.achains)
        return_cards(webdriver.driver, webdriver.achains)
        self.root.deiconify()
        webdriver.driver.quit()

    def hide_labels(self):
        self.choose_format_button.pack_forget()
        self.login_button.pack_forget()

    def show_labels(self):
        self.choose_format_button.pack(anchor="center", fill="both", side=tk.RIGHT, expand=True)
        self.login_button.pack(anchor="center", fill="both", side=tk.BOTTOM, expand=True)

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
