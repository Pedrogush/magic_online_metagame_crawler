def deck_to_dictionary(deck: str):
    '''Converts a deck string to a json object'''
    deck = deck.split('\n')
    deck_dict = {}
    is_sideboard = False
    for index, card in enumerate(deck):
        if not card and index == len(deck) - 1:
            continue
        if not card:
            is_sideboard = True
            continue
        card_amount = int(card.split(' ')[0])
        card_name = ' '.join(card.split(' ')[1:])
        if not is_sideboard:
            if card_name in deck_dict:
                deck_dict[card_name] += card_amount
                continue
            deck_dict[card_name] = card_amount
            continue
        if 'Sideboard '+card_name in deck_dict:
            deck_dict['Sideboard '+card_name] += card_amount
            continue
        deck_dict['Sideboard '+card_name] = card_amount

    return deck_dict


def add_dicts(dict1, dict2):
    '''Adds two dictionaries with integer values'''
    for key, value in dict2.items():
        if key in dict1:
            dict1[key] += value
        else:
            dict1[key] = value
    return dict1


if __name__ == '__main__':
    with open('curr_deck.txt', 'r') as f:
        deck = f.read()

    print(deck_to_dictionary(deck))