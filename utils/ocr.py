import pytesseract
import pyautogui
from PIL import Image
from loguru import logger

SCALING_FACTOR = 1


def set_dpi(image, dpi):
    pil_image = image
    width, height = pil_image.size
    new_size = (width * dpi // 96, height * dpi // 96)
    resized_image = pil_image.resize(new_size)
    return resized_image


def preprocess_image(img: Image.Image, color):
    if color == "white":
        img = filter_image_255(img)
    if color == "black":
        img = filter_image_0(img)
    return img


def detect_word(image, color) -> str:
    image = preprocess_image(image, color)
    image.save("filtered.png")
    config = "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_ --psm 6"
    word = pytesseract.image_to_string(image, config=config)
    return word


def get_words_position_on_screen() -> list[dict]:
    logger.debug("getting position of words on the screen")
    screenshot = pyautogui.screenshot()
    word_positions = detect_word(screenshot)
    return word_positions


def get_box(box) -> Image.Image:
    box = [int(b * SCALING_FACTOR) for b in box]
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.crop(box)
    return screenshot


def get_word_on_box(box, color) -> str:
    box = [int(b * SCALING_FACTOR) for b in box]
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.crop(box)
    screenshot = screenshot.resize((screenshot.width * 2, screenshot.height * 2))
    # debug save a the screenshot
    screenshot.save("box.png")
    image = filter_image_only_accept_white(screenshot)
    image.save("filtered_only_white.png")
    config = "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_ --psm 6"
    word = pytesseract.image_to_string(image, config=config)
    return word


def get_trade_request_on_box(box) -> str:
    box = [int(b * SCALING_FACTOR) for b in box]
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.crop(box)
    screenshot = filter_image_trade_request(screenshot)
    screenshot.save("trade_request.png")
    config = "-c tessedit_char_whitelist=TradeRequest --psm 7"
    word = pytesseract.image_to_string(screenshot, config=config)
    return word


def get_matchups_on_box(box) -> list[dict]:
    box = [int(b * SCALING_FACTOR) for b in box]
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.crop(box)
    config = "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_/:-()"
    word = pytesseract.image_to_data(
        screenshot, config=config, output_type=pytesseract.Output.DICT
    )
    return word


def get_matchup_on_box(box) -> str:
    box = [int(b * SCALING_FACTOR) for b in box]
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.crop(box)
    config = "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_/:-()# --psm 6"
    word: str = pytesseract.image_to_string(screenshot, config=config)
    return word.strip("\n")


def get_game_description_on_box(box) -> str:
    box = [int(b * SCALING_FACTOR) for b in box]
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.crop(box)
    screenshot = screenshot.resize((screenshot.width * 2, screenshot.height * 2))
    config = "-c tessedit_char_whitelist=Game123"
    word: str = pytesseract.image_to_string(screenshot, config=config)
    return word.strip("\n")


def get_game_number_on_box(box) -> str:
    box = [int(b * SCALING_FACTOR) for b in box]
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.crop(box)
    config = "-c tessedit_char_whitelist=#0123456789 --psm 7"
    screenshot = screenshot.resize((screenshot.width * 3, screenshot.height * 3))
    word: str = pytesseract.image_to_string(screenshot, config=config)
    return word.strip("\n")


def get_game_ended_on_box(box) -> bool:
    box = [int(b * SCALING_FACTOR) for b in box]
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.crop(box)
    word: str = pytesseract.image_to_string(screenshot)
    return "the game has ended" in word.lower()


def filter_image_255(image: Image.Image) -> Image.Image:
    """Filter image by only keeping the brightest pixels"""
    resized_im = image.resize(size=(image.width * 3, image.height * 3))
    data = resized_im.getdata()
    mod_data = []
    for d in data:
        if all([i > 225 for i in d]):
            mod_data.append((0, 0, 0))
        else:
            mod_data.append((255, 255, 255))
    resized_im.putdata(mod_data)
    filtered_im = resized_im.resize(size=(image.width * 2, image.height * 2))
    return filtered_im


def filter_image_0(image: Image.Image) -> Image.Image:
    """Filter image by only keeping the darkest"""
    resized_im = image.resize(size=(image.width, image.height))
    data = resized_im.getdata()
    mod_data = []
    for d in data:
        if all([i < 115 for i in d]):
            mod_data.append((0, 0, 0))
        else:
            mod_data.append((255, 255, 255))
    resized_im.putdata(mod_data)
    filtered_im = resized_im.resize(size=(image.width, image.height))
    return filtered_im


def filter_image_only_accept_white(image: Image.Image) -> Image.Image:
    """Filter image by only keeping the brightest pixels"""
    data = image.getdata()
    mod_data = []
    for d in data:
        if all([i <= 140 for i in d]):
            mod_data.append((0, 0, 0))
        else:
            mod_data.append(d)
    image.putdata(mod_data)
    return image


def filter_image_trade_request(image: Image.Image) -> Image.Image:
    """Filter image by only keeping the brightest pixels"""
    data = image.getdata()
    mod_data = []
    for d in data:
        if all([i <= 240 for i in d]):
            mod_data.append((0, 0, 0))
        else:
            mod_data.append(d)
    image.putdata(mod_data)
    return image


def test():
    import pprint

    pos = get_words_position_on_screen()
    logger.debug(pos)
    pprint.pprint([p for p in pos if p["word"]])


if __name__ == "__main__":
    test()
