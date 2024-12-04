

import pyautogui
import time
from ocr import get_word_on_box
from metagame import get_latest_deck
from loguru import logger

NAME_POS = (93, 320, 311, 358)


def monitor_deck():
    cache = {}
    last_looked_at_ts = time.time()
    while True:
        time.sleep(2)
        player_name = ''
        v1, v2, v3, v4 = NAME_POS
        b1 = pyautogui.pixelMatchesColor(v1, v2, (0, 0, 0))
        b2 = pyautogui.pixelMatchesColor(v1, v4, (0, 0, 0))
        b3 = pyautogui.pixelMatchesColor(v3, v2, (0, 0, 0))
        b4 = pyautogui.pixelMatchesColor(v3, v4, (0, 0, 0))
        if b1 and b2 and b3 and b4:
            player_name = get_word_on_box(NAME_POS, 'black')
        if not player_name:
            if time.time() - last_looked_at_ts > 5:
                logger.debug('No player name in screen')
            continue
        last_looked_at_ts = time.time()
        if player_name not in cache:
            latest_deck = get_latest_deck(player_name, 'Modern')
            ts = time.time()
            cache[player_name] = {'deck': latest_deck, 'ts': ts}
        elif time.time() - cache[player_name]['ts'] > 1800:
            latest_deck = get_latest_deck(player_name, 'Modern')
            ts = time.time()
            cache[player_name] = {'deck': latest_deck, 'ts': ts}
        elif time.time() - cache[player_name]['ts'] < 120:
            logger.warning(f'Player {player_name} last seen piloting: {cache[player_name]["deck"]}')
            continue
        logger.warning(f'Player {player_name} last seen piloting: {cache[player_name]["deck"]}')


if __name__ == '__main__':
    monitor_deck()
