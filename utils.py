import pyautogui
from loguru import logger
from pyscreeze import ImageNotFoundException as e1
from pyautogui import ImageNotFoundException as e2
from PIL import Image


def focus_magic_online(width=1200, height=800):
    windows = pyautogui.getWindowsWithTitle('Magic: The Gathering Online')
    if not windows:
        logger.debug('Failed to find modo window')
        return False
    w = windows[0]
    try:
        w.activate()
    except Exception:
        # windows throws an exception if the window is already focused
        logger.debug('w.activate exception ignored')
    if w.isMinimized:
        w.restore()
    w.moveTo(0, 0)
    w.resizeTo(width, height)
    logger.debug(w)
    if w.width != width or w.height != height:
        logger.debug('Failed to resize modo window')
        logger.debug(f'current size: {w.width} {w.height}')
    return


def focus_game_window():
    w = pyautogui.getWindowsWithTitle('Magic: The Gathering Online')
    if len(w) <= 1:
        logger.debug('No modo game window')
        return False
    w = w[0]
    try:
        w.activate()
    except Exception:
        # windows throws an exception if the window is already focused
        logger.debug('w.activate exception ignored')
    w.moveTo(0, 0)
    w.resizeTo(1240, 1000)


def game_screenshot() -> Image:
    # Record the game
    ss = pyautogui.screenshot()
    return ss.crop((0, 0, 1240, 1000))


def save_game_screenshot(fname):
    ss = game_screenshot()
    ss.save(fname)
    return ss


def scroll_down_only_move(x, y):
    original_pos = pyautogui.position()
    pyautogui.moveTo(x, y)
    pyautogui.scroll(clicks=-1)
    pyautogui.moveTo(*original_pos)
    return


def scroll_up_only_move(x, y):
    original_pos = pyautogui.position()
    pyautogui.click(x, y)
    pyautogui.scroll(clicks=1)
    pyautogui.moveTo(*original_pos)
    return


def scroll_down(x, y):
    pyautogui.click(x, y)
    pyautogui.scroll(clicks=-1)
    return


def scroll_up(x, y):
    pyautogui.click(x, y)
    pyautogui.scroll(clicks=1)
    return


def click_and_return(x, y):
    original_x, original_y = pyautogui.position()
    pyautogui.click(x, y)
    pyautogui.moveTo(original_x, original_y)
    return


def locate(image_path):
    try:
        pos = pyautogui.locateOnScreen(image_path)
        return pos
    except Exception as e:
        if isinstance(e, e1) or isinstance(e, e2):
            return None
        logger.exception(e)
        return None


def locate_all(image_path):
    try:
        pos_list = list(pyautogui.locateAllOnScreen(image_path, confidence=0.9))
        return pos_list
    except Exception as e:
        if isinstance(e, e1) or isinstance(e, e2):
            return []
        logger.exception(e)
        return []


def close_game_window():
    click_and_return(1226, 11)
