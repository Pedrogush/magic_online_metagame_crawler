from pathlib import Path

from loguru import logger

from utils import paths

LEGACY_CURR_DECK_CACHE = Path("cache") / "curr_deck.txt"
LEGACY_CURR_DECK_ROOT = Path("curr_deck.txt")


def sanitize_filename(filename: str, fallback: str = "saved_deck") -> str:
    """
    Sanitize a filename by removing invalid characters.

    Args:
        filename: Original filename
        fallback: Default filename if result is empty

    Returns:
        Sanitized filename safe for filesystem use
    """
    safe_name = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in filename).strip()
    # If the result is empty or only underscores, use fallback
    if not safe_name or safe_name.replace("_", "").strip() == "":
        return fallback
    return safe_name


def sanitize_zone_cards(entries: list) -> list[dict[str, int | float | str]]:
    """
    Validate and sanitize zone card entries.

    Filters out invalid entries and ensures all cards have valid names and quantities.

    Args:
        entries: List of card entries (each should be a dict with 'name' and 'qty')

    Returns:
        List of validated card dictionaries with 'name' (str) and 'qty' (int or float) keys
    """
    sanitized: list[dict[str, int | float | str]] = []

    for entry in entries:
        # Skip non-dict entries
        if not isinstance(entry, dict):
            continue

        name = entry.get("name")
        qty_raw = entry.get("qty", 0)

        # Skip entries without a name
        if not name:
            continue

        # Parse and preserve float quantities from average decks
        try:
            qty_float = float(qty_raw)
            # Convert to int only if it's a whole number
            qty = int(qty_float) if qty_float.is_integer() else qty_float
            qty = max(0, qty)
        except (TypeError, ValueError):
            continue

        # Skip zero-quantity entries
        if qty <= 0:
            continue

        sanitized.append({"name": name, "qty": qty})

    return sanitized


def read_curr_deck_file() -> str:
    curr_deck_file = paths.CURR_DECK_FILE
    candidates = [curr_deck_file, LEGACY_CURR_DECK_CACHE, LEGACY_CURR_DECK_ROOT]
    for candidate in candidates:
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as fh:
                contents = fh.read()
            if candidate != curr_deck_file:
                try:
                    curr_deck_file.parent.mkdir(parents=True, exist_ok=True)
                    with curr_deck_file.open("w", encoding="utf-8") as target:
                        target.write(contents)
                    try:
                        candidate.unlink()
                    except OSError:
                        logger.debug(f"Unable to remove legacy deck file {candidate}")
                except OSError as exc:  # pragma: no cover
                    logger.debug(f"Failed to migrate curr_deck.txt from {candidate}: {exc}")
            return contents
    raise FileNotFoundError("Current deck file not found")
