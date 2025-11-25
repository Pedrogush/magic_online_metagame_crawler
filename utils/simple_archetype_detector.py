"""Simple archetype detection for Modern decks based on key cards."""

from collections import Counter


def detect_modern_archetype(mainboard_cards: list[dict]) -> str:
    """
    Detect Modern archetype from mainboard cards.

    Args:
        mainboard_cards: List of dicts with 'name' and 'count' keys

    Returns:
        Archetype name
    """
    card_set = {card["name"] for card in mainboard_cards}
    card_counts = {card["name"]: card["count"] for card in mainboard_cards}

    if "Ugin's Labyrinth" in card_set and "Eldrazi Temple" in card_set:
        return "Eldrazi Tron"

    if "Goryo's Vengeance" in card_set:
        return "Reanimator"

    if "Living End" in card_set:
        return "Living End"

    if "Urza's Saga" in card_set and "Ornithopter" in card_set:
        return "Hammer Time"

    if "Primeval Titan" in card_set and "Amulet of Vigor" in card_set:
        return "Amulet Titan"

    if "Yawgmoth, Thran Physician" in card_set:
        return "Yawgmoth"

    if "Murktide Regent" in card_set:
        if "Lightning Bolt" in card_set:
            return "Izzet Murktide"
        return "Dimir Murktide"

    if "Omnath, Locus of Creation" in card_set:
        return "4C Omnath"

    if "Indomitable Creativity" in card_set or "Creativity" in card_set:
        return "Indomitable Creativity"

    if "Grief" in card_set and ("Undying Malice" in card_set or "Not Dead After All" in card_set):
        return "Rakdos Scam"

    if "The One Ring" in card_set:
        if "Leyline of Sanctity" in card_set or "Leyline Binding" in card_set:
            return "Domain Ramp"
        if "Phlage, Titan of Fire's Fury" in card_set or "Phlage" in card_set:
            return "Jeskai Control"
        if "Tron" in str(card_set) or "Urza's Tower" in card_set:
            return "Mono Green Tron"
        if "Emry, Lurker of the Loch" in card_set:
            return "Urza's Saga"

    if "Tarmogoyf" in card_set:
        if "Wrenn and Six" in card_set:
            return "Jund"
        if "Territorial Kavu" in card_set:
            return "Domain Zoo"
        return "Jund"

    if "Hollow One" in card_set and "Burning Inquiry" in card_set:
        return "Hollow One"

    if "Dredge" in card_set or ("Creeping Chill" in card_set and "Prized Amalgam" in card_set):
        return "Dredge"

    if "Crashing Footfalls" in card_set:
        return "Rhinos"

    if "Through the Breach" in card_set and "Emrakul, the Aeons Torn" in card_set:
        return "Through the Breach"

    if "Collected Company" in card_set:
        if "Devoted Druid" in card_set:
            return "Devoted Druid"
        if "Risen Reef" in card_set:
            return "Elementals"
        return "Collected Company"

    if "Death's Shadow" in card_set:
        if "Temur Battle Rage" in card_set:
            return "Temur Death's Shadow"
        if "Stubborn Denial" in card_set:
            return "Grixis Death's Shadow"
        return "Death's Shadow"

    if "Heliod, Sun-Crowned" in card_set and "Walking Ballista" in card_set:
        return "Heliod Company"

    if "Devoted Druid" in card_set and "Chord of Calling" in card_set:
        return "Devoted Druid"

    if "Ad Nauseam" in card_set:
        return "Ad Nauseam"

    if "Valakut, the Molten Pinnacle" in card_set:
        return "Scapeshift"

    if "Storm" in card_set or ("Gifts Ungiven" in card_set and "Past in Flames" in card_set):
        return "Gifts Storm"

    if "Prowess" in card_set or ("Monastery Swiftspear" in card_set and "Soul-Scar Mage" in card_set):
        return "Prowess"

    if "Urza's Tower" in card_set and "Urza's Mine" in card_set and "Urza's Power Plant" in card_set:
        if "Wurmcoil Engine" in card_set or "Karn Liberated" in card_set:
            return "Mono Green Tron"
        return "Tron"

    if "Delver of Secrets" in card_set:
        return "Izzet Delver"

    if "Burn" in card_set or (card_counts.get("Lightning Bolt", 0) >= 4 and card_counts.get("Lava Spike", 0) >= 4):
        return "Burn"

    if "Solitude" in card_set:
        if "Ephemerate" in card_set or "Eladamri's Call" in card_set:
            return "Blink"
        if "Leyline Binding" in card_set:
            return "Domain Control"

    if "Shardless Agent" in card_set and "Crashing Footfalls" in card_set:
        return "Temur Rhinos"

    if "Thought-Knot Seer" in card_set and ("Eldrazi Temple" in card_set or "Eye of Ugin" in card_set):
        return "Eldrazi"

    if "Aether Vial" in card_set:
        if "Thalia, Guardian of Thraben" in card_set:
            return "Death and Taxes"
        if "Silvergill Adept" in card_set:
            return "Merfolk"
        if "Champion of the Parish" in card_set:
            return "Humans"
        if "Goblin" in str(card_set):
            return "Goblins"

    if "Hardened Scales" in card_set:
        return "Hardened Scales"

    if "Amulet of Vigor" in card_set:
        return "Amulet"

    if "Lantern of Insight" in card_set:
        return "Lantern Control"

    if "Arclight Phoenix" in card_set:
        return "Arclight Phoenix"

    if "Thing in the Ice" in card_set:
        return "Thing in the Ice"

    if "Infect" in card_set or ("Inkmoth Nexus" in card_set and "Blighted Agent" in card_set):
        return "Infect"

    if "Affinity" in card_set or ("Springleaf Drum" in card_set and "Mox Opal" in card_set):
        return "Affinity"

    if "Urza, Lord High Artificer" in card_set:
        return "Urza"

    if "Uro, Titan of Nature's Wrath" in card_set:
        return "Uro Control"

    if "Emrakul, the Promised End" in card_set:
        return "Tron"

    if "Karn, the Great Creator" in card_set and "Urza's Mine" not in card_set:
        if "The One Ring" in card_set:
            return "Mono Green Devotion"
        return "Karn Combo"

    if "Leyline of the Guildpact" in card_set:
        return "Domain"

    if "Bring to Light" in card_set:
        return "Scapeshift"

    if "Utopia Sprawl" in card_set and "Arbor Elf" in card_set:
        return "Ponza"

    if "Blood Moon" in card_set and "Magus of the Moon" in card_set:
        return "Blood Moon"

    if "Chalice of the Void" in card_set and "Simian Spirit Guide" not in card_set:
        if "Eldrazi" in str(card_set):
            return "Eldrazi"
        return "Chalice Control"

    if "Monastery Swiftspear" in card_set and "Dragon's Rage Channeler" in card_set:
        return "Prowess"

    if "Ragavan, Nimble Pilferer" in card_set:
        if "Orcish Bowmasters" in card_set:
            return "Izzet Midrange"
        if "Tarmogoyf" in card_set:
            return "Jund"
        return "Izzet Aggro"

    return "Unknown"
