import pyautogui
from pynput import mouse
from loguru import logger
from ocr import get_words_position_on_screen
from utils import (
    focus_magic_online,
    click_and_return,
    
)
import time
from PIL import Image, ImageDraw
import json
import os
TAB_OPTIONS = {
    "home": 0,
    "collection": 1,
    "constructed": 2,
    "limited": 3,
    "store": 4,
    "trade": 5,
    "settings": 6,
}
TAB_OPTIONS.update({v: k for k, v in TAB_OPTIONS.items()})
TAB_POSITIONS = {
    "home": (132, 100),
    "collection": (451, 84),
    "constructed": (783, 84),
    "limited": (1085, 84),
    "store": (1303, 84),
    "trade": (1482, 84),
}
# If you're on Windows, specify the path to the Tesseract executable
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def click_tab(tab_name: str):
    x, y = TAB_POSITIONS[tab_name]
    click_and_return(x, y)
    logger.debug(f'clicked {x, y} will wait 1 sec for page to load')
    time.sleep(1)
    return True


def get_latest_challenge_pos():
    word_positions = get_words_position_on_screen()
    challenge_options = [word_pos for word_pos in word_positions if word_pos['word'].lower() == 'challenge']
    chal_y_min_coord = 9999
    chosen_chal = None
    for chal in challenge_options:
        if chal['position'][1] < chal_y_min_coord:
            chal_y_min_coord = chal['position'][1]
            chosen_chal = chal
    if not chosen_chal:
        logger.debug('failed to find a challenge to click')
        return False
    return chosen_chal['position']


def configure_box_positions():
    ''' this function is used to configure the box positions for the leaderboard '''
    tr = {}
    for i in range(5):
        cur = []
        logger.debug(f'[top left], [name], [top ranks], player {i + 1}')
        cur += [wait_for_click()]
        logger.debug(f'[bottom_right], [name], [top ranks], player {i + 1}')
        cur += [wait_for_click()]
        logger.debug(f'[top left], [trophies], [top ranks], player {i + 1}')
        cur += [wait_for_click()]
        logger.debug(f'[bottom_right], [trophies], [top ranks], player {i + 1}')
        cur += [wait_for_click()]
        tr[i + 1] = cur
    br = {}
    for i in range(6):
        cur = []
        logger.debug(f'[top left], [name], [bottom ranks], player {i + 1}')
        cur += [wait_for_click()]
        logger.debug(f'[bottom_right], [name], [bottom ranks], player {i + 1}')
        cur += [wait_for_click()]
        logger.debug(f'[top left], [trophies], [bottom ranks], player {i + 1}')
        cur += [wait_for_click()]
        logger.debug(f'[bottom_right], [trophies], [bottorm ranks], player {i + 1}')
        cur += [wait_for_click()]
        br[i + 1] = cur
    if os.path.exists('leaderboard_positions.json'):
        logger.debug('leaderboard_positions.json already exists, will overwrite')
        os.remove('leaderboard_positions.json')
    with open('leaderboard_positions.json', 'w') as f:
        json.dump({'top': tr, 'bottom': br}, f, indent=4)


def load_box_positions():
    if not os.path.exists('leaderboard_positions.json'):
        logger.debug('leaderboard_positions.json not found, please run configure_box_positions')
        configure_box_positions()
    with open('leaderboard_positions.json', 'r') as f:
        data = json.load(f)
    return data


def draw_lines(x, y):
    screen_width, screen_height = pyautogui.size()
    img = Image.new('RGBA', (screen_width, screen_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.line((0, y, screen_width, y), fill=(255, 0, 0, 255), width=2)
    draw.line((x, 0, x, screen_height), fill=(255, 0, 0, 255), width=2)


def wait_for_click() -> tuple:
    def on_click(x, y, button, pressed):
        draw_lines(x, y)
        if button == mouse.Button.left and pressed:
            print('{} at {}'.format('Pressed Left Click', (x, y)))
            return False
    listener = mouse.Listener(on_click=on_click)
    listener.start()
    listener.join()
    x, y = pyautogui.position()
    return (x, y)


if __name__ == '__main__':
    focus_magic_online()
    configure_box_positions()
    # logger.debug('clicking home/colletion/constructed/limited/store/trade in sequence')
    # click_tab('home')
    # time.sleep(2)
    # click_tab('collection')
    # time.sleep(2)
    # click_tab('constructed')
    # time.sleep(2)
    # click_tab('limited')
    # time.sleep(2)
    # click_tab('store')
    # time.sleep(2)
    # click_tab('trade')
    # time.sleep(2)
