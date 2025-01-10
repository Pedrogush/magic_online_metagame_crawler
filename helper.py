

import time
import tkinter as tk
import json
import os
from modo_navigator import wait_for_click, login
from ocr import get_word_on_box
from metagame import get_latest_deck
from loguru import logger


def default_label(root):
    return tk.Label(
        root,
        font=('calibri', 15, 'bold'),
        background='purple',
        foreground='white',
        borderwidth=2,
        justify='left',
        relief='solid'
    )


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
        self.update_deck()

    def ui_make_components(self):
        self.root.title('MTG Helper')
        self.player_label = default_label(self.root)
        self.deck_label = default_label(self.root)
        self.instructions_label = default_label(self.root)
        self.configure_box_button = tk.Button(
            self.root,
            text='Configure box',
            font=('calibri', 13, 'bold'),
            background='purple',
            command=self.update_box
        )
        self.choose_format_button = tk.Button(
            self.root,
            text='Choose format',
            font=('calibri', 13, 'bold'),
            background='purple',
            command=self.update_format
        )
        self.login_button = tk.Button(
            self.root,
            text='Login',
            font=('calibri', 13, 'bold'),
            background='green',
            command=login
        )
        self.ui_pack_components()

    def ui_pack_components(self):
        self.player_label.pack(anchor="center", expand=True, fill='both')
        self.deck_label.pack(anchor="center", expand=True, fill='both')
        self.choose_format_button.pack(anchor="center", fill='both', side=tk.RIGHT, expand=True)
        self.configure_box_button.pack(anchor="center", fill='both', side=tk.LEFT, expand=True)
        self.login_button.pack(anchor="center", fill='both', side=tk.BOTTOM, expand=True)

    def update_box(self):
        self.hide_labels()
        self.instructions_label.pack(anchor="center", expand=True, fill='both', side=tk.TOP)
        self.updating = True
        logger.debug('Updating box')
        self.instructions_label.config(text='Click on the top left corner of the box')
        self.instructions_label.update()
        v1 = wait_for_click()
        self.instructions_label.config(text='Click on the bottom right corner of the box')
        self.instructions_label.update()
        v2 = wait_for_click()
        self.box = (v1[0], v1[1], v2[0], v2[1])
        self.vertices = ((v1[0], v1[1]), (v1[0], v2[1]), (v2[0], v1[1]), (v2[0], v2[1]))
        self.instructions_label.config(text='Box updated, vertices are {}'.format(self.vertices))
        self.instructions_label.update()
        self.save_config()
        time.sleep(1.5)
        self.instructions_label.pack_forget()
        self.show_labels()
        self.updating = False

    def update_format(self):
        self.hide_labels()
        self.instructions_label.pack(anchor="center", expand=True, fill='both', side=tk.TOP)
        self.updating = True
        logger.debug('Please choose the format')
        self.choose_format_button.pack_forget()
        self.configure_box_button.pack_forget()
        self.instructions_label.config(text='Please choose the format')
        self.text_field = tk.Entry(self.root, font=('calibri', 24, 'bold'), background='purple', foreground='white')
        self.text_field.pack(anchor="center", fill='x')
        self.text_field.focus()
        self.accept_button = tk.Button(
            root,
            text='Accept',
            font=('calibri', 20, 'bold'),
            background='purple',
            command=lambda: self.update_format_done(self.text_field)
        )
        self.accept_button.pack(anchor="center", fill='x')

    def update_format_done(self, text_field):
        self.format = text_field.get()
        self.instructions_label.config(text=f'Format updated to {self.format}')
        self.save_config()
        time.sleep(1.5)
        self.updating = False
        self.accept_button.destroy()
        self.text_field.destroy()
        self.choose_format_button.pack(anchor="center", fill='both', side=tk.RIGHT, expand=True)
        self.configure_box_button.pack(anchor="center", fill='both', side=tk.LEFT, expand=True)
        self.instructions_label.pack_forget()
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
        self.instructions_label.pack_forget()
        self.refresh_labels()

    def refresh_labels(self):
        self.player_label.config(text=self.player_name.strip(), border=2)
        self.player_label.update()
        self.deck_label.config(text=f"LKD: {self.last_seen_deck}", border=2)
        self.deck_label.update()

    def hide_labels(self):
        self.player_label.pack_forget()
        self.deck_label.pack_forget()
        self.choose_format_button.pack_forget()
        self.configure_box_button.pack_forget()
        self.login_button.pack_forget()

    def show_labels(self):
        self.player_label.pack(anchor="center", expand=True, fill='both')
        self.deck_label.pack(anchor="center", expand=True, fill='both')
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
