import json
import bs4
from curl_cffi import requests
from selenium import webdriver
from selenium.webdriver.common.by import By


def mtggoldfish_get_archetypes(mtg_format: str):
    page = requests.get('https://www.mtggoldfish.com/metagame/modern/full')
    soup = bs4.BeautifulSoup(page.text, 'html.parser')
    metagame_decks = soup.select_one("#metagame-decks-container")
    archetypes: list[bs4.Tag] = metagame_decks.find_all("span", attrs={"class": "deck-price-paper"})
    archetypes = [tag for tag in archetypes if tag.find('a') and not tag.find('div')]
    return set(tag.text.strip() for tag in archetypes)


def mtggoldfish_get_deck(self, deck_num: str):
    file = requests.get(f'https://www.mtggoldfish.com/deck/download/{deck_num}')
    with open('curr_deck.txt', 'wb') as f:
        f.write(file.content)


class Netdecker:
    def __init__(self):
        self.driver: webdriver.Chrome = webdriver.Chrome()
        self.driver.implicitly_wait(10)
        self.achains = webdriver.ActionChains(self.driver)
        self.config = json.load(open('config.json', 'r'))

    def manatraders_login(self):
        self.driver.get("https://www.manatraders.com/users/sign_in")
        email_box = self.driver.find_element(by=By.ID, value='user_email')
        self.achains.move_to_element(email_box).click().send_keys(self.config['manatraders_login']).perform()
        password_box = self.driver.find_element(by=By.ID, value='user_password')
        self.achains.move_to_element(password_box).click().send_keys(self.config['manatraders_pass']).perform()
        login_box = self.driver.find_element(by=By.NAME, value='commit')
        self.achains.move_to_element(login_box).click().perform()



if __name__ == '__main__':
    # nd = Netdecker()
    # nd.driver.maximize_window()
    print(mtggoldfish_get_archetypes('modern'))
