from loguru import logger
from utils.paths import CURR_DECK_FILE
from pathlib import Path
LEGACY_CURR_DECK_CACHE = Path("cache") / "curr_deck.txt"
LEGACY_CURR_DECK_ROOT = Path("curr_deck.txt")


def deck_to_dictionary(deck: str):
    """Converts a deck string to a json object"""
    deck = deck.split("\n")
    deck_dict = {}
    is_sideboard = False
    for index, card in enumerate(deck):
        if not card and index == len(deck) - 1:
            continue
        if not card:
            is_sideboard = True
            continue
        try:
            card_amount = int(float(card.split(" ")[0]))  # Handle fractional amounts from averages
        except (ValueError, IndexError):
            continue  # Skip invalid lines
        card_name = " ".join(card.split(" ")[1:])
        if not is_sideboard:
            if card_name in deck_dict:
                deck_dict[card_name] += card_amount
                continue
            deck_dict[card_name] = card_amount
            continue
        if "Sideboard " + card_name in deck_dict:
            deck_dict["Sideboard " + card_name] += card_amount
            continue
        deck_dict["Sideboard " + card_name] = card_amount

    return deck_dict


def analyze_deck(deck_content: str):
    """
    Analyzes a deck and returns statistics.

    Returns:
        dict with keys:
            - mainboard_count: int
            - sideboard_count: int
            - total_cards: int
            - unique_mainboard: int
            - unique_sideboard: int
            - card_breakdown: dict of {card_name: count}
    """
    lines = deck_content.strip().split("\n")

    mainboard = []
    sideboard = []
    is_sideboard = False

    for line in lines:
        line = line.strip()
        if not line:
            is_sideboard = True
            continue
        if line.lower() == "sideboard":
            is_sideboard = True
            continue

        try:
            parts = line.split(" ", 1)
            if len(parts) < 2:
                continue
            count = int(float(parts[0]))
            card_name = parts[1].strip()

            if is_sideboard:
                sideboard.append((card_name, count))
            else:
                mainboard.append((card_name, count))
        except (ValueError, IndexError):
            continue

    mainboard_count = sum(count for _, count in mainboard)
    sideboard_count = sum(count for _, count in sideboard)

    estimated_lands = len(
        [
            c
            for c, _ in mainboard
            if any(
                x in c.lower()
                for x in ["mountain", "island", "swamp", "forest", "plains", "land", "wastes"]
            )
        ]
    )

    return {
        "mainboard_count": mainboard_count,
        "sideboard_count": sideboard_count,
        "total_cards": mainboard_count + sideboard_count,
        "unique_mainboard": len(mainboard),
        "unique_sideboard": len(sideboard),
        "mainboard_cards": mainboard,
        "sideboard_cards": sideboard,
        "estimated_lands": estimated_lands,
    }


def render_average_deck(buffer: dict[str, float], decks_added: int) -> str:
    if not buffer or decks_added <= 0:
        return ""
    lines: list[str] = []
    sideboard_lines: list[str] = []
    for card, total in sorted(
        buffer.items(), key=lambda kv: (kv[0].startswith("Sideboard"), kv[0])
    ):
        display_name = card.replace("Sideboard ", "")
        average = float(total) / decks_added
        value = f"{average:.2f}" if not average.is_integer() else str(int(average))
        output = f"{value} {display_name}"
        if card.lower().startswith("sideboard"):
            sideboard_lines.append(output)
        else:
            lines.append(output)
    if sideboard_lines:
        lines.append("")
        lines.extend(sideboard_lines)
    return "\n".join(lines)


def read_curr_deck_file() -> str:
    candidates = [CURR_DECK_FILE, LEGACY_CURR_DECK_CACHE, LEGACY_CURR_DECK_ROOT]
    for candidate in candidates:
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as fh:
                contents = fh.read()
            if candidate != CURR_DECK_FILE:
                try:
                    CURR_DECK_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with CURR_DECK_FILE.open("w", encoding="utf-8") as target:
                        target.write(contents)
                    try:
                        candidate.unlink()
                    except OSError:
                        logger.debug(f"Unable to remove legacy deck file {candidate}")
                except OSError as exc:  # pragma: no cover
                    logger.debug(f"Failed to migrate curr_deck.txt from {candidate}: {exc}")
            return contents
    raise FileNotFoundError("Current deck file not found")


def add_dicts(dict1, dict2):
    """Adds two dictionaries with integer values"""
    for key, value in dict2.items():
        if key in dict1:
            dict1[key] += value
        else:
            dict1[key] = value
    return dict1


if __name__ == "__main__":
    with CURR_DECK_FILE.open("r", encoding="utf-8") as f:
        deck = f.read()

    print(deck_to_dictionary(deck))
