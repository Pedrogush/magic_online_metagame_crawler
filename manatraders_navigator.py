import time
import json
import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from loguru import logger
from mtggoldfish_navigator import download_deck
from mtgo_navigator import (
    focus_magic_online,
    wait_for_trade,
    accept_trade,
    drag_and_drop_cards_from_trade,
    submit_trade,
    confirm_trade,
)
config = json.load(open('config.json', 'r'))


def wait_for_upload_menu_fade_in(driver: webdriver.Chrome):
    start_time = time.time()
    modal_upload_menu = driver.find_element(by=By.ID, value="import-modal")
    style = modal_upload_menu.get_attribute('style')
    while not style or 'display: none' in style and time.time() - start_time < 15:
        style = modal_upload_menu.get_attribute('style')
    if time.time() - start_time >= 15:
        return False
    return True


def wait_for_rent_return_menu_fade_in(driver: webdriver.Chrome):
    start_time = time.time()
    rental_menu = driver.find_element(by=By.ID, value='rent-return-info')
    style = rental_menu.get_attribute('style')
    while not style or 'display: none' in style and time.time() - start_time < 15:
        style = rental_menu.get_attribute('style')
    if time.time() - start_time >= 15:
        return False
    return True


def wait_for_upload_menu_fade_out(driver: webdriver.Chrome):
    start_time = time.time()
    modal_upload_menu = driver.find_element(by=By.ID, value="import-modal")
    style = modal_upload_menu.get_attribute('style')
    while 'display: none' not in style and time.time() - start_time < 15:
        style = modal_upload_menu.get_attribute('style')
    if time.time() - start_time >= 15:
        return False
    return True


def wait_for_rent_button_enabled(driver: webdriver.Chrome):
    start_time = time.time()
    rent_button = driver.find_element(by=By.CLASS_NAME, value='checkout-get')
    while not rent_button.is_enabled() and time.time() - start_time < 15:
        rent_button = driver.find_element(by=By.CLASS_NAME, value='checkout-get')
        rent_button.get_attribute('disabled')
        time.sleep(0.5)
    if time.time() - start_time >= 15:
        logger.debug("rent button enabled timed out")
        return False
    return True


def wait_for_confirm_rent_dialog(driver: webdriver.Chrome):
    start_time = time.time()
    confirm_rent_dialog = driver.find_element(by=By.ID, value='insert-username-for-rent-modal')
    style = confirm_rent_dialog.get_attribute('style')
    while not style or 'display: none' in style and time.time() - start_time < 15:
        style = confirm_rent_dialog.get_attribute('style')
    if time.time() - start_time >= 15:
        logger.debug("confirm rent dialog timed out")
        return False
    return True


def find_submit_decklist_button(driver: webdriver.Chrome):
    import_modal = driver.find_element(by=By.ID, value='import-modal')
    import_by_text = import_modal.find_element(by=By.ID, value='import-by-text')
    modal_footer = import_by_text.find_element(by=By.CLASS_NAME, value='modal-footer')
    return modal_footer.find_element(by=By.CLASS_NAME, value='btn-primary')


def wait_for_bot_to_load_cards(driver: webdriver.Chrome):
    logger.debug("waiting for bot to load cards")
    start_time = time.time()
    bot_loading = driver.find_element(by=By.XPATH, value='//*[@id="page-wrapper"]/div[1]/div[1]/div[1]/div[1]/form/button') # noqa
    enabled = bot_loading.is_enabled()
    while not enabled and time.time() - start_time < 125:
        enabled = bot_loading.is_enabled()
    if time.time() - start_time >= 125:
        logger.debug("bot loading timed out")
        return False
    return True


def wait_for_bot_to_be_ready_to_request_cards(driver: webdriver.Chrome):
    start_time = time.time()
    bot_ready = driver.find_element(by=By.XPATH, value='//*[@id="page-wrapper"]/div[3]/div/div/div[1]/form/button')
    enabled = bot_ready.is_enabled()
    while not enabled and time.time() - start_time < 125:
        enabled = bot_ready.is_enabled()
    if time.time() - start_time >= 125:
        logger.debug("bot ready timed out")
        return False
    return True


def login(driver: webdriver.Chrome, achains: webdriver.ActionChains):
    driver.get("https://www.manatraders.com/users/sign_in")
    email_box = driver.find_element(by=By.ID, value='user_email')
    achains.move_to_element(email_box).click().send_keys(config['manatraders_login']).perform()
    password_box = driver.find_element(by=By.ID, value='user_password')
    achains.move_to_element(password_box).click().send_keys(config['manatraders_pass']).perform()
    login_box = driver.find_element(by=By.NAME, value='commit')
    achains.move_to_element(login_box).click().perform()


def rent_deck(driver: webdriver.Chrome, achains: webdriver.ActionChains, deck_num: str):
    download_deck(deck_num)
    driver.get("https://www.manatraders.com/webshop")
    upload_btn = driver.find_element(by=By.XPATH, value='//*[@id="page-wrapper"]/div[2]/div/div[2]/div[4]/button[2]') # noqa
    achains.move_to_element(upload_btn).click().perform()
    pyperclip.copy(open('curr_deck.txt').read())
    wait_for_upload_menu_fade_in(driver)
    text_area = driver.find_element(by=By.XPATH, value='//*[@id="text"]')
    achains.move_to_element(text_area).click().click().key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform() # noqa
    submit_btn = find_submit_decklist_button(driver)
    achains.move_to_element(submit_btn).click().click().perform()
    wait_for_upload_menu_fade_out(driver)
    wait_for_rent_button_enabled(driver)
    rent_button = driver.find_element(by=By.XPATH, value='//*[@id="page-wrapper"]/div[2]/div/div[2]/div[2]/div/button') # noqa
    achains.move_to_element(rent_button).click().click().perform()
    wait_for_confirm_rent_dialog(driver)
    time.sleep(2)
    confirm_rent_button = driver.find_element(by=By.XPATH, value='//*[@id="insert-username-for-rent-modal"]/div/div/div[3]/button[2]') # noqa
    achains.move_to_element(confirm_rent_button).click().click().perform()


def receive_cards(driver):
    logger.debug("receiving cards")
    wait_for_bot_to_load_cards(driver)
    focus_magic_online()
    wait_for_trade()
    accept_trade()
    time.sleep(5)
    drag_and_drop_cards_from_trade()
    time.sleep(5)
    submit_trade()
    time.sleep(5)
    confirm_trade()


def return_cards(driver: webdriver.Chrome, action_chains: webdriver.ActionChains):
    driver.get("https://www.manatraders.com/dashboard")
    return_rental_button = driver.find_element(by=By.XPATH, value='//*[@id="page-wrapper"]/div[2]/div[2]/div[2]/div/div/div/div[2]/div[1]/button') # noqa
    action_chains.move_to_element(return_rental_button).click().click().perform()
    wait_for_rent_return_menu_fade_in(driver)
    return_cards_btn = driver.find_element(by=By.CSS_SELECTOR, value='input[value="Return cards"]')
    return_cards_btn.submit()
    wait_for_bot_to_be_ready_to_request_cards(driver)
    focus_magic_online()
    wait_for_trade()
    accept_trade()
    submit_trade()
    confirm_trade()


class Webdriver:
    def __init__(self):
        self.options = Options()
        self.options.add_experimental_option("detach", True)
        self.driver: webdriver.Chrome = webdriver.Chrome(self.options)
        self.driver.implicitly_wait(10)
        self.achains = webdriver.ActionChains(self.driver)
        self.config = json.load(open('config.json', 'r'))


if __name__ == '__main__':
    nd = Webdriver()
    nd.driver.maximize_window()
    login(nd.driver, nd.achains)
    rent_deck(nd.driver, nd.achains, '6866938')
    time.sleep(5)
    receive_cards(nd.driver)
    # return_cards(nd.driver, nd.achains)

    # time.sleep(5)
    # wait_for_trade()
    # focus_magic_online()
    # print(mtggoldfish_get_archetypes('modern'))
    # print(mtggoldfish_get_archetype_decks('modern-song-of-creation'))
