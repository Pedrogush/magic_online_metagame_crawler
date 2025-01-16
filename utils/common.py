from dataclasses import dataclass


@dataclass
class Listing:
    card_name: str
    price: float
    amount: int
    seller: str
    condition: str
    scraped_at: str
    edition: str
    foil: bool
    language: str


@dataclass
class Card:
    card_name: str
    prices: list[Listing]
    scraped_at: str
