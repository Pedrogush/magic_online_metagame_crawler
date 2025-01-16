

import time
import tkinter as tk
import json
import os
import pyperclip
from mtgo_navigator import wait_for_click, login
from ocr import get_word_on_box
from metagame import get_latest_deck
from loguru import logger
from mtggoldfish_navigator import (
    get_archetypes,
    get_archetype_decks,
    download_deck,
)
from manatraders_navigator import (
    Webdriver,
    login as manatraders_login,
    rent_deck,
    receive_cards,
    return_cards,
)
from mtgo_navigator import (
    register_deck,
)
# TODO: make webdriver close upon trade completed
# organize UI so that GUI buttons are divided properly per function
# hide/show buttons for rent functions when appropriate
COLOR_SCHEME = 'bisque'
CS = [COLOR_SCHEME+'1', COLOR_SCHEME+'2', COLOR_SCHEME+'3', COLOR_SCHEME+'4', COLOR_SCHEME]


def default_label(root, text=' ', color=CS[0]):
    return tk.Label(
        root,
        text=text,
        font=('calibri', 15, 'bold'),
        background=color,
        foreground='black',
        borderwidth=2,
        justify='left',
        relief='solid'
    )


def default_button(root, text, command, color=CS[0], font=('calibri', 13, 'bold')):
    return tk.Button(
        root,
        text=text,
        font=font,
        background=color,
        command=command
    )


def default_listbox(root, color=CS[0], font=('calibri', 15, 'bold')):
    return tk.Listbox(
        root,
        selectmode=tk.SINGLE,
        background=color,
        foreground='black',
        font=font
    )


def default_frame(root, name, color=CS[3]):
    frame = tk.Frame(root, relief='solid', padx=3, pady=3, background=color, borderwidth=2, border=1)
    if name:
        frame_title = tk.Label(frame, text=name, font=('calibri', 15, 'bold'), background=CS[2], foreground='black', relief='solid')
        frame_title.pack(anchor="center", expand=False, fill='both')
    return frame


def repopulate_listbox(listbox: tk.Listbox, items: list):
    for item in listbox.get(0, tk.END):
        listbox.delete(0)
    for index, item in enumerate(items):
        listbox.insert(index, item)


def format_deck(deck: dict):
    return f"{deck['date']} {deck['player']} {deck['event']} {deck['result']}"


class MTGHelperWidget:
    def __init__(self, root: tk.Tk):
        self.root: tk.Tk = root
        self.ui_make_components()
        self.load_cache()
        self.last_looked_at_ts = time.time()
        self.load_config()
        self.player_name: str = get_word_on_box((self.box), 'black')
        self.last_seen_deck = ''
        self.format = 'Modern'
        self.updating = False
        self.user_has_edited_deck = False
        self.update_deck()

    def ui_make_components(self):
        self.root.title('MTG Helper')
        # frames
        self.frame_top = default_frame(self.root, "", color='bisque4')
        self.frame_top_left = default_frame(self.frame_top, "Manatraders Card Rental Automation", color=CS[1])
        self.frame_top_right = default_frame(self.frame_top, "Opponent Deck Monitor", color=CS[1])
        self.frame_bottom = default_frame(self.root, "Configuration", color=CS[3])
        # labels
        self.opponent_name_label = default_label(self.frame_top_right)
        self.opponent_deck_label = default_label(self.frame_top_right)
        self.deck_monitor_instructions_label = default_label(self.frame_top_right)
        self.configure_box_button = default_button(self.frame_bottom, 'Configure box', self.update_box)
        self.choose_format_button = default_button(self.frame_bottom, 'Choose format', self.update_format)
        self.login_button = default_button(self.frame_bottom, 'MTGO Login', login, color=CS[2], font=('calibri', 15, 'bold'))
        self.listbox = default_listbox(self.frame_top_left, color=CS[4])
        self.listbox_scrollbar = tk.Scrollbar(self.listbox, orient="vertical")
        self.listbox_btn = default_button(self.frame_top_left, 'Select archetype', self.select_archetype)
        self.archetypes = get_archetypes('modern')
        for index, archetype in enumerate(self.archetypes):
            self.listbox.insert(index, archetype["name"])
        self.return_cards_btn = default_button(self.frame_top_left, 'Return cards', self.return_cards)
        self.textbox_title = default_label(self.frame_top_right, 'Decklist', color=CS[2])
        self.textbox = tk.Text(self.frame_top_right, font=('calibri', 15, 'bold'), background=CS[1], foreground='black')
        self.ui_pack_components()
        self.ui_bind_components()

    def textbox_on_change(self, event):
        self.last_event = event
        self.user_has_edited_deck = True

    def ui_bind_components(self):
        self.textbox.bind("<Key>", self.textbox_on_change)

    def ui_pack_components(self):
        self.opponent_name_label.pack(anchor="center", expand=False, fill='both')
        self.opponent_deck_label.pack(anchor="center", expand=False, fill='both')
        self.login_button.pack(anchor="center", fill='x', side=tk.LEFT, expand=False)
        self.choose_format_button.pack(anchor="center", fill='both', side=tk.RIGHT, expand=True)
        self.configure_box_button.pack(anchor="center", fill='both', side=tk.LEFT, expand=True)
        self.listbox.pack(anchor="center", fill='both', side=tk.BOTTOM, expand=True)
        self.listbox_btn.pack(anchor="center", fill='both', side=tk.BOTTOM, expand=False)
        self.listbox_scrollbar.pack(anchor="center", fill='y', side=tk.RIGHT)
        self.return_cards_btn.pack(anchor="center", fill='both', side=tk.BOTTOM, expand=False)
        self.textbox_title.pack(anchor="center", expand=False, fill='x')
        self.textbox.pack(anchor="center", fill='both', side=tk.BOTTOM, expand=True)
        self.frame_top.pack(anchor="center", fill='both', side=tk.TOP, expand=True)
        self.frame_top_right.pack(anchor="center", fill='both', side=tk.RIGHT, expand=True)
        self.frame_top_left.pack(anchor="center", fill='both', side=tk.LEFT, expand=True)
        self.frame_bottom.pack(anchor="center", fill='x', side=tk.BOTTOM, expand=False)

    def select_archetype(self):
        selected = self.listbox.curselection()
        logger.debug(selected)
        if not selected:
            return
        selected = selected[0]
        logger.debug(selected)
        archetype = self.archetypes[selected]["href"]
        logger.debug(archetype)
        self.decks = get_archetype_decks(archetype)
        logger.debug(self.decks)
        repopulate_listbox(self.listbox, [format_deck(deck) for deck in self.decks])
        self.listbox_btn.config(text='Select deck', command=self.select_deck)
        self.listbox.bind('<<ListboxSelect>>', self.set_textbox)

    def set_textbox(self, event):
        selected = self.listbox.curselection()
        if not selected:
            return
        selected = selected[0]
        deck = self.decks[selected]
        self.textbox.delete('1.0', tk.END)
        download_deck(deck['number'])
        self.textbox.insert('1.0', open('curr_deck.txt').read())

    def select_deck(self):
        selected = self.listbox.curselection()
        logger.debug(selected)
        if not selected:
            return
        selected = selected[0]
        logger.debug(selected)
        deck = self.decks[selected]
        logger.debug(deck)
        self.root.iconify()
        webdriver = Webdriver()
        webdriver.driver.maximize_window()
        manatraders_login(webdriver.driver, webdriver.achains)
        if self.user_has_edited_deck:
            # if the user edits the decks cards, rent the version they edited
            pyperclip.copy(self.textbox.get("1.0", tk.END))
            rent_deck(webdriver.driver, webdriver.achains)
        else:
            rent_deck(webdriver.driver, webdriver.achains, deck['number'])
        time.sleep(5)
        receive_cards(webdriver.driver)
        time.sleep(10)
        register_deck(deck['name']+deck['number'])
        self.root.deiconify()
        webdriver.driver.quit()
        repopulate_listbox(self.listbox, [archetype["name"] for archetype in self.archetypes])
        self.listbox_btn.config(text='Select archetype', command=self.select_archetype)
        self.user_has_edited_deck = False
        self.listbox.unbind('<<ListboxSelect>>')

    def return_cards(self):
        self.root.iconify()
        webdriver = Webdriver()
        webdriver.driver.maximize_window()
        manatraders_login(webdriver.driver, webdriver.achains)
        return_cards(webdriver.driver, webdriver.achains)
        self.root.deiconify()
        webdriver.driver.quit()

    def update_box(self):
        self.hide_labels()
        self.deck_monitor_instructions_label.pack(anchor="center", expand=True, fill='both', side=tk.TOP)
        self.updating = True
        logger.debug('Updating box')
        self.deck_monitor_instructions_label.config(text='Click on the top left corner of the box')
        self.deck_monitor_instructions_label.update()
        v1 = wait_for_click()
        self.deck_monitor_instructions_label.config(text='Click on the bottom right corner of the box')
        self.deck_monitor_instructions_label.update()
        v2 = wait_for_click()
        self.box = (v1[0], v1[1], v2[0], v2[1])
        self.vertices = ((v1[0], v1[1]), (v1[0], v2[1]), (v2[0], v1[1]), (v2[0], v2[1]))
        self.deck_monitor_instructions_label.config(text='Box updated, vertices are {}'.format(self.vertices))
        self.deck_monitor_instructions_label.update()
        self.save_config()
        time.sleep(1.5)
        self.deck_monitor_instructions_label.pack_forget()
        self.show_labels()
        self.updating = False

    def update_format(self):
        self.hide_labels()
        self.deck_monitor_instructions_label.pack(anchor="center", expand=True, fill='both', side=tk.TOP)
        self.updating = True
        logger.debug('Please choose the format')
        self.choose_format_button.pack_forget()
        self.configure_box_button.pack_forget()
        self.deck_monitor_instructions_label.config(text='Please choose the format')
        self.text_field = tk.Entry(self.root, font=('calibri', 24, 'bold'), background='skyblue', foreground='black')
        self.text_field.pack(anchor="center", fill='x')
        self.text_field.focus()
        self.accept_button = tk.Button(
            root,
            text='Accept',
            font=('calibri', 20, 'bold'),
            background='skyblue',
            command=lambda: self.update_format_done(self.text_field)
        )
        self.accept_button.pack(anchor="center", fill='x')

    def update_format_done(self, text_field):
        self.format = text_field.get()
        self.deck_monitor_instructions_label.config(text=f'Format updated to {self.format}')
        self.save_config()
        time.sleep(1.5)
        self.updating = False
        self.accept_button.destroy()
        self.text_field.destroy()
        self.choose_format_button.pack(anchor="center", fill='both', side=tk.RIGHT, expand=True)
        self.configure_box_button.pack(anchor="center", fill='both', side=tk.LEFT, expand=True)
        self.deck_monitor_instructions_label.pack_forget()
        self.show_labels()

    def update_deck(self):
        self.save_config()  # doing this to save the current position of the helper
        if self.updating:
            self.root.after(10000, self.update_deck)
            return
        self.player_name = get_word_on_box(self.box, 'black')
        if self.player_name in self.cache and time.time() - self.cache[self.player_name]['ts'] < 1800:
            self.last_seen_deck = self.cache[self.player_name]['deck']
            self.root.after(10000, self.update_deck)
            self.refresh_labels()
            return
        self.last_seen_deck = get_latest_deck(self.player_name, self.format)
        self.cache[self.player_name] = {'deck': self.last_seen_deck, 'ts': time.time()}
        self.save_cache()
        self.root.after(10000, self.update_deck)
        self.deck_monitor_instructions_label.pack_forget()
        self.refresh_labels()

    def refresh_labels(self):
        self.opponent_name_label.config(text=self.player_name.strip(), border=2)
        self.opponent_name_label.update()
        self.opponent_deck_label.config(text=f"LKD: {self.last_seen_deck}", border=2)
        self.opponent_deck_label.update()

    def hide_labels(self):
        self.opponent_name_label.pack_forget()
        self.opponent_deck_label.pack_forget()
        self.choose_format_button.pack_forget()
        self.configure_box_button.pack_forget()
        self.login_button.pack_forget()

    def show_labels(self):
        self.opponent_name_label.pack(anchor="center", expand=True, fill='both')
        self.opponent_deck_label.pack(anchor="center", expand=True, fill='both')
        self.choose_format_button.pack(anchor="center", fill='both', side=tk.RIGHT, expand=True)
        self.configure_box_button.pack(anchor="center", fill='both', side=tk.LEFT, expand=True)
        self.login_button.pack(anchor="center", fill='both', side=tk.BOTTOM, expand=True)

    def save_config(self):
        config = {
            'box': self.box,
            'format': self.format,
            'vertices': self.vertices,
            'screen_pos': (self.root.winfo_x(), self.root.winfo_y())
        }
        json.dump(config, open('deck_monitor_config.json', 'w'), indent=4)

    def load_config(self):
        if os.path.exists('deck_monitor_config.json'):
            config = json.load(open('deck_monitor_config.json', 'r'))
            self.box = config['box']
            self.vertices = config['vertices']
            self.format = config['format']
            self.root.geometry(f'+{config["screen_pos"][0]}+{config["screen_pos"][1]}')
            return
        self.box = (93, 320, 311, 358)  # any valid box works fine
        self.format = 'Modern'

    def save_cache(self):
        json.dump(self.cache, open('deck_monitor_cache.json', 'w'), indent=4)

    def load_cache(self):
        if os.path.exists('deck_monitor_cache.json'):
            self.cache = json.load(open('deck_monitor_cache.json', 'r'))
            return
        self.cache = {}


if __name__ == '__main__':
    root = tk.Tk()
    root.attributes('-topmost', 'true')
    monitor = MTGHelperWidget(root)
    root.mainloop()
