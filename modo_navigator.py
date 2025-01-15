import pyautogui
from pynput import mouse
from loguru import logger
from ocr import (
    get_word_on_box,
    get_words_position_on_screen,
    get_trade_request_on_box
)
from utils import (
    focus_magic_online,
    click_and_return,
    drag_and_drop_all,
)
import time
from PIL import Image, ImageDraw
import json
import os
CONFIG = json.load(open('config.json', 'r'))
# If you're on Windows, specify the path to the Tesseract executable
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def login():
    focus_magic_online()
    click_and_return(*CONFIG["login_name_pos"])
    time.sleep(0.01)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.01)
    pyautogui.write(CONFIG["login_name"])
    time.sleep(0.01)
    click_and_return(*CONFIG["login_pass_pos"])
    time.sleep(0.01)
    pyautogui.write(CONFIG["login_pass"])
    time.sleep(0.01)
    click_and_return(*CONFIG["login_button_pos"])


def navigate_to(tab_name: str, left_hand_field: str = ''):
    """ navigate to the desired tab """
    """ tab_name in [home, collection, constructed, limited, store, trade, configuration]"""
    focus_magic_online()
    click_and_return(*CONFIG["tabs"][tab_name])
    if tab_name == 'constructed':
        click_and_return(*CONFIG["left_hand_tabs_constructed"][left_hand_field])
    if tab_name == 'limited':
        click_and_return(*CONFIG["left_hand_tabs_limited"][left_hand_field])


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


def accept_trade():
    logger.debug('accepting trade')
    focus_magic_online()
    click_and_return(*CONFIG["trade_request"]["full_trade_list"])
    click_and_return(*CONFIG["trade_request"]["ok"])
    logger.debug('trade accepted')
    time.sleep(20)


def submit_trade():
    logger.debug('submitting trade')
    click_and_return(*CONFIG["trade_request"]["submit"])


def wait_for_trade():
    logger.debug('waiting for trade request')
    start = time.time()
    focus_magic_online()
    word = get_trade_request_on_box(CONFIG["trade_request"]["trade_request_box"])
    logger.debug(word)
    while 'traderequest' not in word.lower() and time.time() - start < 125:
        word = get_trade_request_on_box(CONFIG["trade_request"]["trade_request_box"])
        logger.debug(word)
        time.sleep(1)
    if time.time() - start >= 125:
        logger.debug('trade request not found')
        return False
    return True


def confirm_trade():
    logger.debug('confirming trade')
    click_and_return(*CONFIG["trade_request"]["confirm"])


def drag_and_drop_cards_from_trade():
    logger.debug('dragging and dropping cards from trade')
    drag_and_drop_all(*CONFIG["trade_request"]["drag_from"], *CONFIG["trade_request"]["drag_to"])


if __name__ == '__main__':
    # focus_magic_online()
    # configure_box_positions()
    # login()
    # logger.debug('clicking home/colletion/constructed/limited/store/trade in sequence')
    # accept_trade()
    # time.sleep(10)
    drag_and_drop_cards_from_trade()
    # time.sleep(0.5)
    # submit_trade()
