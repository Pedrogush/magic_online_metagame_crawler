import pymongo
from dataclasses import asdict
from common import Card


def get_db():
    client = pymongo.MongoClient('mongodb://localhost:27017/')
    return client.get_database('lm_scraper')


def update_scrape_records(card: Card):
    db = get_db()
    db.scrapes.insert_one(asdict(card))
    return


def delete_card_records(card_name: str):
    db = get_db()
    record = db.scrapes.find_one({'card_name': card_name})
    db.deleted_scrapes.insert_one(record)
    db.scrapes.delete_one({'card_name': card_name})
    return
