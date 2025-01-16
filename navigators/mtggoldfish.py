from curl_cffi import requests
import bs4
import json
import os


def get_archetypes(mtg_format: str):
    page = requests.get(f'https://www.mtggoldfish.com/metagame/{mtg_format}/full')
    soup = bs4.BeautifulSoup(page.text, 'html.parser')
    metagame_decks = soup.select_one("#metagame-decks-container")
    archetypes: list[bs4.Tag] = metagame_decks.find_all("span", attrs={"class": "deck-price-paper"})
    archetypes = [tag for tag in archetypes if tag.find('a') and not tag.find('div')]
    return [
        {
            "name": tag.text.strip(),
            "href": tag.find('a')['href'].replace('/archetype/', '').replace('#paper', '')
         } for tag in archetypes
    ]


def get_archetype_decks(archetype: str):
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
            'number': tds[1].select_one('a').attrs.get('href').replace('/deck/', ''),
            'player': tds[2].text.strip(),
            'event': tds[3].text.strip(),
            'result': tds[4].text.strip(),
            'name': archetype,
        })
    return decks


def get_daily_decks(mtg_format: str):
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


def download_deck(deck_num: str):
    if not os.path.exists('deck_cache.json'):
        deck_cache = {}
        json.dump(deck_cache, open('deck_cache.json', 'w'))
    deck_cache = json.load(open('deck_cache.json', 'r'))
    if deck_num in deck_cache:
        with open('curr_deck.txt', 'w') as f:
            f.write(deck_cache[deck_num])
        return
    file = requests.get(f'https://www.mtggoldfish.com/deck/download/{deck_num}')
    with open('curr_deck.txt', 'wb') as f:
        f.write(file.content)
    deck_cache[deck_num] = open('curr_deck.txt').read()
    json.dump(deck_cache, open('deck_cache.json', 'w'), indent=4)


if __name__ == "__main__":
    print(get_archetypes('modern'))
    print('done')
