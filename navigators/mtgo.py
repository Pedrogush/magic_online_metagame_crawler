import json
from pathlib import Path

import pyautogui
from loguru import logger
from PIL import Image, ImageDraw
from pynput import mouse

from utils.paths import LEADERBOARD_POSITIONS_FILE

LEGACY_LEADERBOARD_POSITIONS = Path("leaderboard_positions.json")


def configure_box_positions():
    """
    Configuration tool for opponent tracking widget.
    Allows user to click on screen positions to define OCR regions
    for reading opponent names and match records from MTGO leaderboard.
    """
    tr = {}
    for i in range(5):
        cur = []
        logger.debug(f"[top left], [name], [top ranks], player {i + 1}")
        cur += [wait_for_click()]
        logger.debug(f"[bottom_right], [name], [top ranks], player {i + 1}")
        cur += [wait_for_click()]
        logger.debug(f"[top left], [trophies], [top ranks], player {i + 1}")
        cur += [wait_for_click()]
        logger.debug(f"[bottom_right], [trophies], [top ranks], player {i + 1}")
        cur += [wait_for_click()]
        tr[i + 1] = cur
    br = {}
    for i in range(6):
        cur = []
        logger.debug(f"[top left], [name], [bottom ranks], player {i + 1}")
        cur += [wait_for_click()]
        logger.debug(f"[bottom_right], [name], [bottom ranks], player {i + 1}")
        cur += [wait_for_click()]
        logger.debug(f"[top left], [trophies], [bottom ranks], player {i + 1}")
        cur += [wait_for_click()]
        logger.debug(f"[bottom_right], [trophies], [bottorm ranks], player {i + 1}")
        cur += [wait_for_click()]
        br[i + 1] = cur
    if LEADERBOARD_POSITIONS_FILE.exists():
        logger.debug(f"{LEADERBOARD_POSITIONS_FILE} already exists, will overwrite")
    with LEADERBOARD_POSITIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"top": tr, "bottom": br}, f, indent=4)


def load_box_positions():
    """
    Loads OCR box position configuration for opponent tracking.
    """
    if not LEADERBOARD_POSITIONS_FILE.exists():
        logger.debug(
            f"{LEADERBOARD_POSITIONS_FILE} not found, please run configure_box_positions"
        )
        configure_box_positions()
    if LEADERBOARD_POSITIONS_FILE.exists():
        try:
            with LEADERBOARD_POSITIONS_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error(f"Failed to load leaderboard positions: {exc}")
            return {"top": {}, "bottom": {}}
    if LEGACY_LEADERBOARD_POSITIONS.exists():
        logger.warning("Loaded legacy leaderboard_positions.json from project root; migrating to config/")
        with LEGACY_LEADERBOARD_POSITIONS.open("r", encoding="utf-8") as f:
            data = json.load(f)
        try:
            with LEADERBOARD_POSITIONS_FILE.open("w", encoding="utf-8") as target:
                json.dump(data, target, indent=4)
            try:
                LEGACY_LEADERBOARD_POSITIONS.unlink()
            except OSError as exc:
                logger.debug(f"Unable to remove legacy leaderboard_positions.json: {exc}")
        except OSError as exc:
            logger.warning(f"Failed to migrate leaderboard positions file: {exc}")
        return data
    return {"top": {}, "bottom": {}}


def draw_lines(x, y):
    """
    Helper for configure_box_positions: shows visual feedback during configuration.
    """
    screen_width, screen_height = pyautogui.size()
    img = Image.new("RGBA", (screen_width, screen_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.line((0, y, screen_width, y), fill=(255, 0, 0, 255), width=2)
    draw.line((x, 0, x, screen_height), fill=(255, 0, 0, 255), width=2)


def wait_for_click() -> tuple:
    """
    Configuration helper: waits for user to click a screen position.
    Used for defining OCR regions in opponent tracking setup.
    """
    def on_click(x, y, button, pressed):
        draw_lines(x, y)
        if button == mouse.Button.left and pressed:
            print("{} at {}".format("Pressed Left Click", (x, y)))
            return False

    listener = mouse.Listener(on_click=on_click)
    listener.start()
    listener.join()
    x, y = pyautogui.position()
    return (x, y)


if __name__ == "__main__":
    # Configuration utility
    configure_box_positions()
