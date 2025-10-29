import pymongo
from dataclasses import asdict
from utils.common import Card
from datetime import datetime
from loguru import logger


def get_db():
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    return client.get_database("lm_scraper")


def update_scrape_records(card: Card):
    db = get_db()
    db.scrapes.insert_one(asdict(card))
    return


def delete_card_records(card_name: str):
    db = get_db()
    record = db.scrapes.find_one({"card_name": card_name})
    db.deleted_scrapes.insert_one(record)
    db.scrapes.delete_one({"card_name": card_name})
    return


# ============= Deck Management Functions =============

def save_deck_to_db(deck_name: str, deck_content: str, format_type: str = None,
                    archetype: str = None, player: str = None, source: str = "manual",
                    metadata: dict = None):
    """
    Save a deck to the database.

    Args:
        deck_name: Name of the deck
        deck_content: Full deck list as text
        format_type: MTG format (Modern, Standard, etc.)
        archetype: Deck archetype name
        player: Player name if from tournament
        source: Source of deck ("mtggoldfish", "manual", "averaged", etc.)
        metadata: Additional metadata dict (tournament info, date, result, etc.)

    Returns:
        ObjectId of the saved deck
    """
    db = get_db()

    deck_doc = {
        "name": deck_name,
        "content": deck_content,
        "format": format_type,
        "archetype": archetype,
        "player": player,
        "source": source,
        "date_saved": datetime.now(),
        "metadata": metadata or {}
    }

    result = db.decks.insert_one(deck_doc)
    logger.info(f"Saved deck '{deck_name}' to database with ID: {result.inserted_id}")
    return result.inserted_id


def get_saved_decks(format_type: str = None, archetype: str = None, sort_by: str = "date_saved"):
    """
    Retrieve saved decks from database.

    Args:
        format_type: Filter by format (optional)
        archetype: Filter by archetype (optional)
        sort_by: Field to sort by (default: "date_saved")

    Returns:
        List of deck documents
    """
    db = get_db()

    query = {}
    if format_type:
        query["format"] = format_type
    if archetype:
        query["archetype"] = archetype

    decks = list(db.decks.find(query).sort(sort_by, pymongo.DESCENDING))
    logger.debug(f"Retrieved {len(decks)} decks from database")
    return decks


def load_deck_from_db(deck_id):
    """
    Load a specific deck by ID.

    Args:
        deck_id: MongoDB ObjectId or string ID

    Returns:
        Deck document or None if not found
    """
    db = get_db()

    if isinstance(deck_id, str):
        from bson import ObjectId
        deck_id = ObjectId(deck_id)

    deck = db.decks.find_one({"_id": deck_id})
    if deck:
        logger.debug(f"Loaded deck: {deck['name']}")
    else:
        logger.warning(f"Deck with ID {deck_id} not found")

    return deck


def delete_saved_deck(deck_id):
    """
    Delete a saved deck from database.

    Args:
        deck_id: MongoDB ObjectId or string ID

    Returns:
        True if deleted, False if not found
    """
    db = get_db()

    if isinstance(deck_id, str):
        from bson import ObjectId
        deck_id = ObjectId(deck_id)

    result = db.decks.delete_one({"_id": deck_id})

    if result.deleted_count > 0:
        logger.info(f"Deleted deck with ID: {deck_id}")
        return True
    else:
        logger.warning(f"Deck with ID {deck_id} not found for deletion")
        return False


def update_deck_in_db(deck_id, deck_content: str = None, deck_name: str = None,
                      metadata: dict = None):
    """
    Update an existing deck in the database.

    Args:
        deck_id: MongoDB ObjectId or string ID
        deck_content: New deck content (optional)
        deck_name: New deck name (optional)
        metadata: Metadata to merge with existing (optional)

    Returns:
        True if updated, False if not found
    """
    db = get_db()

    if isinstance(deck_id, str):
        from bson import ObjectId
        deck_id = ObjectId(deck_id)

    update_fields = {"date_modified": datetime.now()}

    if deck_content is not None:
        update_fields["content"] = deck_content
    if deck_name is not None:
        update_fields["name"] = deck_name
    if metadata is not None:
        # Merge metadata
        existing_deck = db.decks.find_one({"_id": deck_id})
        if existing_deck:
            merged_metadata = existing_deck.get("metadata", {})
            merged_metadata.update(metadata)
            update_fields["metadata"] = merged_metadata

    result = db.decks.update_one(
        {"_id": deck_id},
        {"$set": update_fields}
    )

    if result.modified_count > 0:
        logger.info(f"Updated deck with ID: {deck_id}")
        return True
    else:
        logger.warning(f"Deck with ID {deck_id} not found or no changes made")
        return False
