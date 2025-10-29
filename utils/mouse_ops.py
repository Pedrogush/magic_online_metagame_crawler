import pyautogui
from loguru import logger
from PIL import Image


def focus_magic_online(width=1200, height=800):
    """
    Read-only window management: focuses and resizes MTGO window.
    Used by opponent tracking widget for proper OCR positioning.
    """
    windows = pyautogui.getWindowsWithTitle("Magic: The Gathering Online")
    if not windows:
        logger.debug("Failed to find modo window")
        return False
    w = windows[0]
    try:
        w.activate()
    except Exception:
        # windows throws an exception if the window is already focused
        logger.debug("w.activate exception ignored")
    if w.isMinimized:
        w.restore()
    w.moveTo(0, 0)
    w.resizeTo(width, height)
    logger.debug(w)
    if w.width != width or w.height != height:
        logger.debug("Failed to resize modo window")
        logger.debug(f"current size: {w.width} {w.height}")
    return


def focus_game_window():
    """
    Read-only window management: focuses game window for screenshot capture.
    """
    w = pyautogui.getWindowsWithTitle("Magic: The Gathering Online")
    if len(w) <= 1:
        logger.debug("No modo game window")
        return False
    w = w[0]
    try:
        w.activate()
    except Exception:
        # windows throws an exception if the window is already focused
        logger.debug("w.activate exception ignored")
    w.moveTo(0, 0)
    w.resizeTo(1240, 1000)


def game_screenshot() -> Image:
    """
    Read-only: captures screenshot of game window for analysis.
    """
    ss = pyautogui.screenshot()
    return ss.crop((0, 0, 1240, 1000))


def save_game_screenshot(fname):
    """
    Read-only: saves game screenshot to file.
    """
    ss = game_screenshot()
    ss.save(fname)
    return ss
