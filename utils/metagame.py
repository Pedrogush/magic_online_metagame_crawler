from loguru import logger
from curl_cffi import requests
import bs4

CHALLENGE_LOOKUP_OPTIONS = (
    "Modern",
    "Pioneer",
    "Legacy",
    "Duel Commander",
    "Vintage",
    "Limited",
)
GOLDFISH = "https://www.mtggoldfish.com/player/"


def get_latest_deck(player: str, option: str):
    """
    Web scraping function: queries MTGGoldfish for a player's recent tournament results.
    Returns the most recent deck archetype the player used in the specified format.
    This is read-only web scraping and does not interact with MTGO client.
    """
    if not player:
        return "No player name"
    logger.debug(player)
    player = player.strip()
    try:
        res = requests.get(GOLDFISH + player, impersonate="chrome", timeout=30)
        res.raise_for_status()
    except Exception as exc:
        logger.error(f"Failed to fetch player page for {player}: {exc}")
        return "Unknown"
    soup = bs4.BeautifulSoup(res.text, "html.parser")
    table = soup.find("table")
    if not table and player[0] == "0":
        logger.debug("ocr possibly mistook the letter O for a zero")
        player = "O" + player[1:]
        logger.debug(player)
        try:
            res = requests.get(GOLDFISH + player, impersonate="chrome", timeout=30)
            res.raise_for_status()
        except Exception as exc:
            logger.error(f"Failed retry fetch for player {player}: {exc}")
            return "Unknown"
        soup = bs4.BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
    if not table:
        logger.debug(f"No results table found for player {player}")
        return "Unknown"
    entries = table.find_all("tr")
    for entry in entries:
        tds = entry.find_all("td")
        if not tds:
            continue
        if len(tds) != 8:
            continue
        entry_format: str = tds[2].text
        if entry_format.lower().strip() == option.lower():
            logger.debug(
                f"{player} last 5-0 seen playing {tds[3].text}, in {tds[0].text}"
            )
            return tds[3].text

    return "Unknown"


if __name__ == "__main__":
    # Example usage
    result = get_latest_deck("jessy_samek", "Modern")
    logger.debug(f"Player's latest deck: {result}")
