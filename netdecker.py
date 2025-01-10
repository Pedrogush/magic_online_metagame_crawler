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


def mtggoldfish_download_deck(self, deck_num: str):
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
    print(mtggoldfish_get_daily_decks('modern'))
