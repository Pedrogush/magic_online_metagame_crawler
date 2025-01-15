from ocr import get_word_on_box, get_box
from loguru import logger
from utils import focus_magic_online, scroll_down, scroll_up
from mtgo_navigator import (

    load_box_positions
)
from curl_cffi import requests
import bs4
import time
from dbq import get_db
CHALLENGE_LOOKUP_OPTIONS = (
    'Modern',
    'Pionneer',
    'Legacy',
    'Duel Commander',
    'Vintage',
    'Limited'
)
GOLDFISH = 'https://www.mtggoldfish.com/player/'

BOX_POSITIONS = load_box_positions()


def debug_look_at_boxes():
    import os
    focus_magic_online()
    time.sleep(1)
    t = 0
    for b in BOX_POSITIONS['top'].values():
        b1 = (*b[0], *b[1])
        b2 = (*b[2], *b[3])
        ss = get_box(b1)
        ss.save('box'+str(t)+'.png')
        t += 1
        ss = get_box(b2)
        ss.save('box'+str(t)+'.png')
        t += 1
    for b in BOX_POSITIONS['bottom'].values():
        b1 = (*b[0], *b[1])
        b2 = (*b[2], *b[3])
        ss = get_box(b1)
        ss.save('box'+str(t)+'.png')
        t += 1
        ss = get_box(b2)
        ss.save('box'+str(t)+'.png')
        t += 1
    input('press enter to remove png files')
    for i in range(t):
        os.remove('box'+str(i)+'.png')
    return


def get_player_trophy_count(boxes, color):
    ''' pass color of text we are looking for on the box '''
    box1 = (*boxes[0], *boxes[1])
    logger.debug(box1)
    box2 = (*boxes[2], *boxes[3])
    logger.debug(box2)
    player_name = get_word_on_box(box1, color=color)
    trophies = get_word_on_box(box2, color=color)
    logger.debug(player_name)
    logger.debug(trophies)
    if not player_name or not trophies:
        return None
    player_name: str = player_name.strip('\n')
    return {player_name: int(trophies)}


def get_latest_deck(player: str, option: str):
    if not player:
        return 'No player name'
    logger.debug(player)
    player = player.strip()
    res = requests.get(GOLDFISH+player, impersonate='chrome')
    soup = bs4.BeautifulSoup(res.text, 'html.parser')
    table = soup.find('table')
    if not table and player[0] == '0':
        logger.debug('ocr possibly mistook the letter O for a zero')
        player = 'O' + player[1:]
        logger.debug(player)
        res = requests.get(GOLDFISH+player)
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        table = soup.find('table')
    if not table:
        return 'Unknown'
    entries = table.find_all('tr')
    for entry in entries:
        tds = entry.find_all('td')
        if not tds:
            continue
        if len(tds) != 8:
            continue
        entry_format: str = tds[2].text
        if entry_format.lower().strip() == option.lower():
            logger.debug(f'{player} last 5-0 seen playing {tds[3].text}, in {tds[0].text}')
            return tds[3].text

    return 'Unknown'


def get_metagame_trophy_share_from_leaderboard(leaderboard: dict):
    metagame = {}
    for player, trophy_count in leaderboard.items():
        deck = get_latest_deck(player, 'Modern')
        if 'not found' in deck:
            if 'Other' not in metagame:
                metagame['Other'] = trophy_count
            else:
                metagame['Other'] += trophy_count
        if deck not in metagame:
            metagame[deck] = trophy_count
        else:
            metagame[deck] += trophy_count
    return metagame


def get_top_leaderboard():
    leaderboard = {}
    for b in BOX_POSITIONS['top'].values():
        leaderboard.update(get_player_trophy_count(b, 'white'))
    return leaderboard


def get_bottom_leaderboard(count=999):
    leaderboard = {}
    scrolls = 0
    while True:
        new_player_found = False
        trophy_counts = [get_player_trophy_count(b, 'black') for b in BOX_POSITIONS['bottom'].values()]
        trophy_counts = [t for t in trophy_counts if t]
        for t in trophy_counts:
            key = list(t.keys())[0]
            if t and key not in leaderboard.keys():
                leaderboard.update(t)
                new_player_found = True
        if not new_player_found:
            break
        scroll_down(BOX_POSITIONS['bottom']["1"][0][0], BOX_POSITIONS['bottom']["1"][0][1])
        scrolls += 1
        if len(leaderboard) >= count:
            break
    for _ in range(scrolls):
        scroll_up(BOX_POSITIONS['bottom']["1"][0][0], BOX_POSITIONS['bottom']["1"][0][1])
    return leaderboard


def get_leaderboard():
    top = get_top_leaderboard()
    bottom = get_bottom_leaderboard()
    leaderboard = {**top, **bottom}
    return leaderboard


def update_db_leaderboard(format="Modern"):
    leaderboard = get_leaderboard()
    logger.debug(f'got leaderboard:\n {leaderboard}')
    scrape_ts = time.time()
    db = get_db()
    db.leaderboard.insert_one(
        {
            'leaderboard': leaderboard,
            'scrape_ts': scrape_ts,
            'format': format
        }
    )
    return leaderboard


def update_db_metagame_trophy_share(format="Modern"):
    leaderboard = update_db_leaderboard(format)
    metagame = get_metagame_trophy_share_from_leaderboard(leaderboard)
    db = get_db()
    db.metagame_trophy_share.insert_one(
        {
            'metagame': metagame,
            'scrape_ts': time.time(),
            'format': format
        }
    )
    return metagame


if __name__ == '__main__':
    # debug_look_at_boxes()
    focus_magic_online()
    time.sleep(1)
    metagame = update_db_metagame_trophy_share(format="Modern")
    logger.debug(metagame)
    # get_latest_deck({'word': 'jessy_samek'}, 'Modern')
