import json
import bs4
import time
from curl_cffi import requests
from selenium import webdriver
from selenium.webdriver.common.by import By


def mtggoldfish_get_archetypes(mtg_format: str):
    page = requests.get(f'https://www.mtggoldfish.com/metagame/{mtg_format}/full')
    soup = bs4.BeautifulSoup(page.text, 'html.parser')
    metagame_decks = soup.select_one("#metagame-decks-container")
    archetypes: list[bs4.Tag] = metagame_decks.find_all("span", attrs={"class": "deck-price-paper"})
    archetypes = [tag for tag in archetypes if tag.find('a') and not tag.find('div')]
    return [
        {tag.text.strip(): tag.find('a')['href'].replace('/archetype/', '').replace('#paper', '')} for tag in archetypes
    ]


def mtggoldfish_get_archetype_decks(archetype: str):
    page = requests.get(f'https://www.mtggoldfish.com/archetype/{archetype}/decks')
    soup = bs4.BeautifulSoup(page.text, 'html.parser')
    table = soup.select_one("table.table-striped")
    trs: list[bs4.Tag] = table.find_all('tr')
    trs = trs[1:]
    decks = []
    for tr in trs:
        tds: list[bs4.Tag] = tr.find_all('td')
        decks.append({
            'date': tds[0].text.strip(),
            'player': tds[2].text.strip(),
            'event': tds[3].text.strip(),
            'result': tds[4].text.strip(),
        })
    return decks


def mtggoldfish_get_daily_decks(mtg_format: str):
    page = requests.get(f'https://www.mtggoldfish.com/metagame/{mtg_format}')
    soup = bs4.BeautifulSoup(page.text, 'html.parser')
    table_container = soup.select_one("div.similar-events-container")
    h4s: list[bs4.Tag] = table_container.find_all('h4')
    decks = {}
    for h4 in h4s:
        date = h4.find('nobr').text.strip().replace('on ', '')
        tournament_type = h4.find('a').text.strip()
        has_placement = 'challenge' in tournament_type.lower()
        if date not in decks:
            decks[date] = []
        tbody: bs4.Tag = h4.find_next_sibling()
        cells = tbody.select("tr.striped")
        for cell in cells:
            deck_name = cell.select_one('td.column-deck').select_one('span.deck-price-paper').text.strip()
            deck_number = (
                cell
                .select_one('td.column-deck')
                .select_one('a')['href']
                .replace('#online', '')
                .replace('/deck/', '')
            )
            player_name = cell.select_one('td.column-player').text.strip()
            placement = None
            if has_placement:
                placement = cell.select_one('td.column-place').text.strip()
            decks[date].append(
                {
                    'deck_name': deck_name,
                    'player_name': player_name,
                    'tournament_type': tournament_type,
                    'deck_number': deck_number,
                    'placement': placement
                }
            )
    return decks


def mtggoldfish_download_deck(deck_num: str):
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

    def manatraders_rent_deck(self, deck_num: str):
        # mtggoldfish_download_deck(self, deck_num)
        self.driver.get("https://www.manatraders.com/webshop")
        upload_btn = self.driver.find_elements(by=By.CLASS_NAME, value='btn-link')[5]
        self.achains.move_to_element(upload_btn).click().perform()
        # upload_input = open('curr_deck.txt', 'rb')
        upload_input = '1 Lightning Bolt'
        text_area = self.driver.find_element(by=By.ID, value='text')
        time.sleep(1.5)
        self.achains.move_to_element(text_area).click().send_keys(upload_input).perform()
        # working up to here

        submit_btn = self.driver.find_element(by=By.CSS_SELECTOR, value='[type="submit"]')
        self.achains.move_to_element(submit_btn).click().click().perform()
        time.sleep(5)
        rent_button = self.driver.find_elements(by=By.CLASS_NAME, value='btn-primary-blue')[1]
        self.achains.move_to_element(rent_button).click().perform()
        time.sleep(1.5)
        confirm_rent_button = self.driver.find_elements(by=By.CLASS_NAME, value='btn-primary-blue')[2]
        self.achains.move_to_element(confirm_rent_button).click().perform()


if __name__ == '__main__':
    nd = Netdecker()
    nd.driver.maximize_window()
    nd.manatraders_login()
    nd.manatraders_rent_deck('1234567')
    # print(mtggoldfish_get_archetypes('modern'))
    # print(mtggoldfish_get_archetype_decks('modern-song-of-creation'))
