from pynput import mouse
from loguru import logger
from PIL import Image, ImageDraw
import pyautogui
import json
import os


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
    if os.path.exists("leaderboard_positions.json"):
        logger.debug("leaderboard_positions.json already exists, will overwrite")
        os.remove("leaderboard_positions.json")
    with open("leaderboard_positions.json", "w") as f:
        json.dump({"top": tr, "bottom": br}, f, indent=4)


def load_box_positions():
    """
    Loads OCR box position configuration for opponent tracking.
    """
    if not os.path.exists("leaderboard_positions.json"):
        logger.debug(
            "leaderboard_positions.json not found, please run configure_box_positions"
        )
        configure_box_positions()
    with open("leaderboard_positions.json", "r") as f:
        data = json.load(f)
    return data


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
