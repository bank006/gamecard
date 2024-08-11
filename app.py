from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import threading
import itertools
import pandas as pd
import numpy as np
import secrets
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) 
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, async_mode='threading' , cors_allowed_origins="*")

rooms = {}

def generate_deck():
    suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [f'{value} of {suit}' for suit in suits for value in values]
    deck.extend(['Joker', 'Joker','Joker', 'Joker'])  # Add jokers to the deck
    return deck

deck = generate_deck()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']
    join_room(room)

    if room not in rooms:
        rooms[room] = {
            'players': [],
            'deck': deck.copy(),
            'confirmed': set(),
            'folded': set(),
            'hands': {},
            'waiting': [],
            'current_turn': None,
            'dealer': None,
            'timer': None,
            'game_started': False,
            'leaving': set(),
            'scores': {
                'players': [],
                'score_total': [],
                'score_thisturn': []
            }
        }

    if rooms[room]['game_started']:
        rooms[room]['waiting'].append(username)
        emit('waiting_area', {'waiting': rooms[room]['waiting']}, room=room)
    elif len(rooms[room]['players']) < 10:
        rooms[room]['players'].append(username)
        rooms[room]['scores']['players'].append(username)
        rooms[room]['scores']['score_total'].append(0)
        rooms[room]['scores']['score_thisturn'].append(0)
        emit('user_joined', {'username': username}, room=room)
        emit('update_players', {'players': rooms[room]['players'], 'room': room}, room=room)
        
        # Send the current scores to the new player
        emit('updated_scores', rooms[room]['scores'], room=request.sid)
    else:
        rooms[room]['waiting'].append(username)
        emit('waiting_area', {'waiting': rooms[room]['waiting']}, room=room)

@socketio.on('start_game')
def handle_start_game(data):
    room = data['room']
    if room in rooms and not rooms[room]['game_started']:
        rooms[room]['game_started'] = True
        start_game(room)

def start_game(room):
    rooms[room]['dealer'] = rooms[room]['players'][0]
    rooms[room]['current_turn'] = rooms[room]['dealer']
    for player in rooms[room]['players']:
        deal_cards_to_player(player, room)
    socketio.emit('game_started', {'dealer': rooms[room]['dealer'], 'current_turn': rooms[room]['current_turn']}, room=room)
    update_queue(room)
    start_turn_timer(room, rooms[room]['current_turn'])

def start_turn_timer(room, player):
    if 'timer' in rooms[room] and rooms[room]['timer']:
        rooms[room]['timer'].cancel()
    timer = threading.Timer(180., auto_fold, [room, player])
    timer.start()
    rooms[room]['timer'] = timer
    socketio.emit('start_timer', {'player': player, 'time': 180}, room=room)

def auto_fold(room, player):
    handle_fold({'username': player, 'room': room})

def deal_cards_to_player(username, room):
    if len(rooms[room]['deck']) < 5:
        rooms[room]['deck'] = generate_deck()  # Reshuffle the deck
    random.shuffle(rooms[room]['deck'])  # Shuffle deck for each new hand
    hand = [rooms[room]['deck'].pop() for _ in range(5)]
    sorted_hand = sort_hand(hand)
    socketio.emit('deal_cards', {'cards': sorted_hand, 'username': username}, room=room)

def sort_hand(hand):
    value_order = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14, 'Joker': 15}
    suit_order = {'Clubs': 1, 'Diamonds': 2, 'Hearts': 3, 'Spades': 4}
    
    def card_value(card):
        if card == 'Joker':
            return (15, 0)
        value, suit = card.split(' of ')
        return (value_order[value.replace('King', 'K').replace('Queen', 'Q').replace('Jack', 'J')], suit_order[suit])
    
    return sorted(hand, key=card_value)

@socketio.on('confirm_selection')
def handle_confirm_selection(data):
    username = data['username']
    room = data['room']
    selectedCards = data['selectedCards']
    if room in rooms and rooms[room]['current_turn'] == username:
        rooms[room]['confirmed'].add(username)
        if username in rooms[room]['folded']:
            rooms[room]['folded'].remove(username)
        rooms[room]['hands'][username] = selectedCards
        socketio.emit('player_confirmed', {'username': username, 'selectedCards': selectedCards}, room=room)
        socketio.emit('update_player_status', {'player': username, 'status': 'CONFIRMED'}, room=room)
        rooms[room]['timer'].cancel()
        if len(rooms[room]['confirmed']) + len(rooms[room]['folded']) == len(rooms[room]['players']):
            socketio.emit('reveal_cards', {'hands': rooms[room]['hands']}, room=room)
            #update_scores(room)
            socketio.emit('enable_next_turn', {'hands': rooms[room]['hands'], 'scores': rooms[room]['scores']}, room=room)
        else:
            next_player_turn(room)
        update_queue(room)

@socketio.on('fold')
def handle_fold(data):
    username = data['username']
    room = data['room']
    if room in rooms and rooms[room]['current_turn'] == username:
        rooms[room]['hands'][username] = ['FOLD'] * 5
        rooms[room]['folded'].add(username)
        if username in rooms[room]['confirmed']:
            rooms[room]['confirmed'].remove(username)
        socketio.emit('player_folded', {'username': username}, room=room)
        socketio.emit('update_player_status', {'player': username, 'status': 'FOLDED'}, room=room)
        rooms[room]['timer'].cancel()
        if len(rooms[room]['confirmed']) + len(rooms[room]['folded']) == len(rooms[room]['players']):
            socketio.emit('reveal_cards', {'hands': rooms[room]['hands']}, room=room)
            #update_scores(room)
            socketio.emit('enable_next_turn', {'hands': rooms[room]['hands'], 'scores': rooms[room]['scores']}, room=room)
        else:
            next_player_turn(room)
        update_queue(room)

def next_player_turn(room):
    current_index = rooms[room]['players'].index(rooms[room]['current_turn'])
    next_index = (current_index + 1) % len(rooms[room]['players'])
    rooms[room]['current_turn'] = rooms[room]['players'][next_index]
    socketio.emit('next_turn', {'current_turn': rooms[room]['current_turn']}, room=room)
    start_turn_timer(room, rooms[room]['current_turn'])  # Ensure the timer is reset
    update_queue(room)

def update_scores(room):
    # This function should update the scores based on the game logic
    # Here, we'll just simulate score updates
    for i, player in enumerate(rooms[room]['scores']['players']):
        rooms[room]['scores']['score_thisturn'][i] = random.randint(-10, 10)  # Simulated score change
        rooms[room]['scores']['score_total'][i] += rooms[room]['scores']['score_thisturn'][i]

    # Reset the score_thisturn for the next turn
    rooms[room]['scores']['score_thisturn'] = [0] * len(rooms[room]['scores']['players'])

@socketio.on('leave_game')
def handle_leave_game(data):
    username = data['username']
    room = data['room']
    if room in rooms:
        if rooms[room]['current_turn'] == username:
            handle_fold({'username': username, 'room': room})
        rooms[room]['leaving'].add(username)
        leave_room(room)
        socketio.emit('user_left', {'username': username}, room=room)
        socketio.emit('message', {'message': f'Player {username} has left the game.'}, room=room)
        update_queue(room)

@socketio.on('next_turn')
def handle_next_turn(data):
    room = data['room']
    if room in rooms and len(rooms[room]['confirmed']) + len(rooms[room]['folded']) == len(rooms[room]['players']):
        for username in list(rooms[room]['leaving']):
            if username in rooms[room]['players']:
                rooms[room]['players'].remove(username)
            rooms[room]['leaving'].remove(username)
        rooms[room]['confirmed'].clear()
        rooms[room]['folded'].clear()  # Clear folded set for the new round
        rooms[room]['hands'].clear()
        rooms[room]['deck'] = generate_deck()  # Reshuffle the deck
        for player in rooms[room]['players']:
            deal_cards_to_player(player, room)
        if rooms[room]['players']:  # Ensure there are players remaining before updating dealer
            update_dealer(room)  # Update the dealer for the next turn
            move_waiting_to_players(room)  # Move waiting players to active players if possible
            socketio.emit('next_turn_started', {'current_turn': rooms[room]['current_turn']}, room=room)
            start_turn_timer(room, rooms[room]['current_turn'])
            update_queue(room)

def update_dealer(room):
    if rooms[room]['players']:
        if rooms[room]['dealer'] not in rooms[room]['players']:
            rooms[room]['dealer'] = rooms[room]['players'][0]
        current_index = rooms[room]['players'].index(rooms[room]['dealer'])
        next_index = (current_index + 1) % len(rooms[room]['players'])
        rooms[room]['dealer'] = rooms[room]['players'][next_index]
        rooms[room]['current_turn'] = rooms[room]['dealer']
        update_queue(room)  # Update the queue and next dealer information

def update_queue(room):
    queue = rooms[room]['players']
    if rooms[room]['players']:
        next_dealer_index = (rooms[room]['players'].index(rooms[room]['dealer']) + 1) % len(rooms[room]['players'])
        next_dealer = rooms[room]['players'][next_dealer_index]
    else:
        next_dealer = None
    player_statuses = {}
    for player in queue:
        if player == rooms[room]['current_turn']:
            player_statuses[player] = 'YOUR TURN'
        elif player in rooms[room]['confirmed']:
            player_statuses[player] = 'CONFIRMED'
        elif player in rooms[room]['folded']:
            player_statuses[player] = 'FOLDED'
        else:
            player_statuses[player] = 'WAIT FOR YOUR TURN'
    print(f"Updating queue: {player_statuses}")  # Debugging line
    socketio.emit('update_queue', {'queue': queue, 'next_dealer': next_dealer, 'player_statuses': player_statuses}, room=room)

def move_waiting_to_players(room):
    while len(rooms[room]['players']) < 10 and rooms[room]['waiting']:
        new_player = rooms[room]['waiting'].pop(0)
        rooms[room]['players'].append(new_player)
        rooms[room]['scores']['players'].append(new_player)
        rooms[room]['scores']['score_total'].append(0)
        rooms[room]['scores']['score_thisturn'].append(0)
        socketio.emit('user_joined', {'username': new_player}, room=room)
        socketio.emit('update_players', {'players': rooms[room]['players'], 'room': room}, room=room)
        deal_cards_to_player(new_player, room)
        update_queue(room)

@socketio.on('disconnect')
def handle_disconnect():
    for room, data in rooms.items():
        if request.sid in data['players']:
            data['players'].remove(request.sid)
            leave_room(room)
            if len(data['players']) < 2:
                data['confirmed'].clear()
                data['hands'].clear()
                data['current_turn'] = None
                socketio.emit('waiting_for_players', room=room)
            else:
                socketio.emit('update_players', {'players': data['players'], 'room': room}, room=room)
                update_queue(room)
        elif request.sid in data['waiting']:
            data['waiting'].remove(request.sid)
            socketio.emit('waiting_area', {'waiting': data['waiting']}, room=room)



class Card:
    suits = ['club', 'diamond', 'heart', 'spade']
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    value_ranks = {str(i): i for i in range(2, 11)}
    value_ranks.update({'J': 11, 'Q': 12, 'K': 13, 'A': 14})
    suit_ranks = {'club':1,
                 'diamond':2,
                 'heart':3,
                 'spade':4}
    suit_symbol = {'club':'♣️',
                 'diamond':'♦️',
                 'heart':'❤️',
                 'spade':'♠️',
                 'Joker':'🃏'}
    card_score = {str(i): i for i in range(2,10)}
    card_score.update({'J': 0, 'Q': 0, 'K' : 0, 'A' : 1, '10' : 0})
    
    def __init__(self, suit, value):
        self.suit = suit
        self.value = value
        self.face = value in ['J','Q','K']

    def __str__(self):
        return f"{self.value} {self.suit} {Card.suit_symbol[self.suit]}"

    def rank(self):
        return Card.value_ranks[self.value]
        
    def score(self):
        return Card.card_score[self.value]

def convert_raw_to_card(raw_card):
    if raw_card == 'Joker':
        return(Card('Joker','Joker'))
    else:
        card_value = raw_card.split(' ')[0]
        card_suit = raw_card.split(' ')[-1].lower()[:-1]
        return(Card(card_suit, card_value))

def trow_convert_joker(trow):
    if 'Joker' not in [val.value for val in trow]:
        return trow
    if all(val.value == 'Joker' for val in trow):
        return [Card('spade','A'), Card('spade','8')]

    card = [card for card in trow if card.value!='Joker'][0]
    card_value = card.score() 
    card_suit = card.suit
    if card_value == 9:
        joker_score = 'K'
        joker_suit = card_suit
    elif card_value == 8:
        joker_score = 'A'
        joker_suit = card_suit
    else:
        joker_score = str(9 - card_value)
        joker_suit = card_suit
    return [card, Card(joker_suit, joker_score)]


def compare_trow(trow1, trow2):

    trow1 = trow_convert_joker(trow1)
    trow2 = trow_convert_joker(trow2)
    
    winner = 0
    
    if trow1[0].suit == trow1[1].suit : 
        suited1 = True 
    else: suited1 = False
    
    if trow2[0].suit == trow2[1].suit : 
        suited2 = True 
    else: suited2 = False

    if trow1[0].value == trow1[1].value:
        pair1 = True
    else: pair1 = False

    if trow2[0].value == trow2[1].value:
        pair2 = True
    else: pair2 = False
        
    kickerindex1 = np.argmax([card.rank() for card in trow1])
    kickervalue1 = trow1[kickerindex1]

    kicker1 = kickervalue1.value
    kickerrank1 = kickervalue1.rank()
    kickersuit1 = max([candidate.suit for candidate in trow1 if candidate.value == kickervalue1.value])
    
    kickerindex2 = np.argmax([card.rank() for card in trow2])
    kickervalue2 = trow2[kickerindex2]

    kicker2 = kickervalue2.value
    kickerrank2 = kickervalue2.rank()
    kickersuit2 = max([candidate.suit for candidate in trow2 if candidate.value == kickervalue2.value])
    
    if all([card.face for card in trow1]):
        score1 = 7.5
        suited1 = True
    elif all([card.score() == 5 for card in trow1]):
        score1 = 7.5
        suited1 = True
    elif all([card.value == 10 for card in trow1]):
        score1 = 7.5
        suited1 = True
    elif (sum(card.score() if not card.face else 0 for card in trow1)%10 == 0) and suited1:
        score1 = 7.5
        suited1 = True
    else:
        score1 = sum(card.score() if not card.face else 0 for card in trow1)%10
        
    if all([card.face for card in trow2]):
        score2 = 7.5
        suited2 = True
    elif all([card.score() == 5 for card in trow2]):
        score2 = 7.5
        suited2 = True
    elif all([card.value == 10 for card in trow2]):
        score2 = 7.5
        suited2 = True
    elif (sum(card.score() if not card.face else 0 for card in trow2)%10 == 0) and suited2:
        score2 = 7.5
        suited2 = True
    else:
        score2 = sum(card.score() if not card.face else 0 for card in trow2)%10

    if score1 > score2:
        print(f'player1 wins with {score1}')
        winner = 1
    elif score2 > score1:
        print(f'player2 wins with {score2}')
        winner = 2
    else:
        if (pair1 == True) & (pair2 == False):
            print('player 1 win')
            winner = 1
        elif (pair1 == False) & (pair2 == True):
            print('player 2 win')
            winner = 2
        else:
            if (suited1 == True) & (suited2 == False):
                print('player 1 wins')
                winner = 1
            elif (suited1 == False) & (suited2 == True):
                print('player 2 wins')
                winner = 2
            else :
                if kickerrank1 > kickerrank2:
                    winner = 1
                elif kickerrank2 > kickerrank1:
                    winner = 2 
                else:
                    if kickersuit1 > kickersuit2:
                        winner = 1
                    elif kickersuit2 > kickersuit1: 
                        winner = 2
                    else: winner = 0
    print(f'player1 score = {score1} suited = {suited1} pair = {pair1} with kicker {kicker1} {kickersuit1}')
    print(f'player2 score = {score2} suited = {suited2} pair = {pair2} with kicker {kicker2} {kickersuit2}')
    print(f'winner = player{winner}')

    if winner == 1 :
        if max(suited1, pair1)>0:
            return (winner, 2)
        else:
            return (winner, 1)
    elif winner == 2:
        if max(suited2, pair2)>0:
            return (winner, 2)
        else:
            return (winner, 1)
    else:
        return (0, 0)

def compare_kicker(kickerrank1, kickersuit1, kickerrank2, kickersuit2):
    if kickerrank1 > kickerrank2:
        winner = 1
    elif kickerrank2 > kickerrank1:
        winner = 2 
    else:
        if kickersuit1 > kickersuit2:
            winner = 1
        elif kickersuit2 > kickersuit1: 
            winner = 2
        else: winner = 0
    return winner

def has_max_diff_less_than_2(numbers):
    # Sort the list to make it easier to find close elements
    sorted_numbers = sorted(numbers)
    
    # Iterate through the list and check adjacent pairs
    for i in range(len(sorted_numbers) - 1):
        if abs(sorted_numbers[i] - sorted_numbers[i + 1]) < 2:
            return True
    return False

def can_straight(numbers):
    # Sort the list to make it easier to find close elements
    sorted_numbers = sorted(numbers)
    
    # Iterate through the list and check adjacent pairs
    for i in range(len(sorted_numbers) - 1):
        if abs(sorted_numbers[i] - sorted_numbers[i + 1]) < 3:
            return True, abs(sorted_numbers[i] - sorted_numbers[i + 1])
    return False, abs(sorted_numbers[i] - sorted_numbers[i + 1])

def brow_convert_joker(trow):
    for i in trow:
        print(i)
    if 'Joker' not in [val.value for val in trow]:
        return trow
    if all(val.value == 'Joker' for val in trow):
        return [Card('Joker','Joker'), Card('Joker','Joker'), Card('Joker','Joker')]
    if [val.value for val in trow].count('Joker') == 2:
        non_joker = [val for val in trow if val.value!='Joker'][0]
        non_joker_suit = [val.suit for val in trow if val.value!='Joker'][0]
        print(non_joker)
        if non_joker.value == 'A':
            return [non_joker, Card(non_joker_suit, 'Q'), Card(non_joker_suit, 'K')]
        elif non_joker.value == 'K':
            return [non_joker, Card(non_joker_suit, 'Q'), Card(non_joker_suit, 'A')]
        elif non_joker.value == 'Q':
            return [non_joker, Card(non_joker_suit, 'K'), Card(non_joker_suit, 'A')]
        elif non_joker.value == 'J':
            return [non_joker, Card(non_joker_suit, 'Q'), Card(non_joker_suit, 'K')]
        elif non_joker.value == '10':
            return [non_joker, Card(non_joker_suit, 'J'), Card(non_joker_suit, 'Q')]
        elif non_joker.value == '9':
            return [non_joker, Card(non_joker_suit, '10'), Card(non_joker_suit, 'J')]
        elif non_joker.value == '8':
            return [non_joker, Card(non_joker_suit, '9'), Card(non_joker_suit, '10')]
        elif non_joker.value == '7':
            return [non_joker, Card(non_joker_suit, '8'), Card(non_joker_suit, '9')]
        elif non_joker.value == '6':
            return [non_joker, Card(non_joker_suit, '7'), Card(non_joker_suit, '8')]
        elif non_joker.value == '5':
            return [non_joker, Card(non_joker_suit, '6'), Card(non_joker_suit, '7')]
        elif non_joker.value == '4':
            return [non_joker, Card(non_joker_suit, '5'), Card(non_joker_suit, '6')]
        elif non_joker.value == '3':
            return [non_joker, Card(non_joker_suit, '4'), Card(non_joker_suit, '5')]
        elif non_joker.value == '2':
            return [non_joker, Card(non_joker_suit, '3'), Card(non_joker_suit, '4')]
    card_value_map = {
    '2': 2,
    '3': 3,
    '4': 4,
    '5': 5,
    '6': 6,
    '7': 7,
    '8': 8,
    '9': 9,
    '10': 10,
    'J': 11,
    'Q': 12,
    'K': 13,
    'A': 14
    }
    value_card_map = {value: key for key, value in card_value_map.items()}

    if [val.value for val in trow].count('Joker') == 1:
        suit_count = len(set([card.suit for card in trow if card.value!='Joker']))
        suited = False
        if suit_count == 1 :
            suited = True
        non_jokers = [val for val in trow if val.value!='Joker']
        straight_ok, distance = can_straight([card_value_map[val.value] for val in non_jokers])
        print(f'distance = {distance}')

        if all(val.face for val in non_jokers) and (distance >= 1) and (not suited):
            kickerindex1 = np.argmax([card.rank() for card in non_jokers])
            kickervalue1 = non_jokers[kickerindex1]
            kicker1 = kickervalue1.value
            # kickerrank1 = kickervalue1.rank()
            kickersuit1 = max([candidate.suit for candidate in non_jokers if candidate.value == kickervalue1.value])
            if kickersuit1 == 'spade':
                return non_jokers+[Card('heart',kicker1)]
            else:
                return non_jokers+[Card('spade',kicker1)]

        if distance == 0: # make trips
            print('make trip')
            if 'spade' not in [val.suit for val in trow if val.value!='Joker']:
                return non_jokers + [Card('spade',non_jokers[0].value)]
            elif 'heart' not in [val.suit for val in trow if val.value!='Joker']:
                return non_jokers+[Card('heart',non_jokers[0].value)] 
            elif 'diamond' not in [val.suit for val in trow if val.value!='Joker']:
                return non_jokers+[Card('diamond',non_jokers[0].value)]
            else:
                return non_jokers+[Card('club',non_jokers[0].value)] 
        elif distance == 1: #connector
            print('continue straight')
            higher_card = max([card_value_map[val.value] for val in trow if val.value!='Joker'])
            suit = non_jokers[0].suit
            if (suited == True):
                if higher_card > 12:
                    return [Card(suit, 'Q'), Card(suit, 'K'), Card(suit, 'A')]
                else :
                    print(Card(suit,value_card_map[higher_card+1]))
                    return non_jokers + [Card(suit,value_card_map[higher_card+1])]
            else:
                if higher_card>=12:
                    missing = set(['A','Q','K']) - set([val.value for val in trow if val.value!='Joker'])
                    return non_jokers + [Card('spade',list(missing)[0])]
                else:
                    print(Card(suit,value_card_map[higher_card+1]))
                    return non_jokers + [Card('spade',value_card_map[higher_card+1])]
        elif distance == 2: #gut shot
            print('fill gut shot')
            higher_card = max([card_value_map[val.value] for val in trow if val.value!='Joker'])
            suit = non_jokers[0].suit
            if (suited == True):
                return non_jokers + [Card(suit,value_card_map[higher_card-1])]
            else:
                return non_jokers + [Card('spade',value_card_map[higher_card-1])]
        elif distance == 12:
            suit = non_jokers[0].suit
            if (suited == True):
                return non_jokers + [Card(suit, '3')]
            else:
                return non_jokers + [Card('spade','3')]
        elif ((non_jokers[0].value == 'A') & (non_jokers[1].value == '3')) or ((non_jokers[0].value == '3') & (non_jokers[1].value == 'A')):
            suit = non_jokers[0].suit
            if (suited == True):
                return non_jokers + [Card(suit, '2')]
            else:
                return non_jokers + [Card('spade','2')]
        else: # make 9
            print('make 9')
            score = sum(card.score() if not card.face else 0 for card in trow if card.value != 'Joker')
            suit = non_jokers[0].suit
            score_to_9 = 9 - score
            if score_to_9 == 1:
                card_value = 'A'
            elif score_to_9 == 0:
                card_value = 'K'
            else :
                card_value = str(score_to_9)
            if (suited == True):
                return non_jokers + [Card(suit, card_value)]
            else:
                return non_jokers + [Card('spade', card_value)]

def compare_brow(brow1, brow2):
    winner = 0

    brow1 = brow_convert_joker(brow1)
    brow2 = brow_convert_joker(brow2)

    if all(val.value == 'Joker' for val in brow1):
        return (1, 20)
    if all(val.value == 'Joker' for val in brow2):
        return (2, 20)

    #sum total point
    score1 = sum(card.score() if not card.face else 0 for card in brow1)%10
    score2 = sum(card.score() if not card.face else 0 for card in brow2)%10

    #check for all same suites
    suit_count1 = len(set([card.suit for card in brow1]))
    suit_count2 = len(set([card.suit for card in brow2]))
    suited1 = False
    suited2 = False 
    if suit_count1 == 1:
        suited1 = True
    if suit_count2 == 1:
        suited2 = True

    #check for pair
    val_count1 = len(set([card.value for card in brow1]))
    val_count2 = len(set([card.value for card in brow2]))
    pair1 = False 
    pair2 = False 
    paircard1 = ''
    paircard2 = ''
    
    if val_count1 == 2:
        pair1 = True
        paircard1 = max([card.value for card in brow1],key=[card.suit for card in brow1].count)
    if val_count2 == 2:
        pair2 = True
        paircard2 = max([card.value for card in brow2],key=[card.suit for card in brow2].count)
    
    pair_ranks = {str(i): i for i in range(2, 11)}
    pair_ranks.update({'':0,'J': 11, 'Q': 12, 'K': 13, 'A': 14})

    #check for trips
    value_count1 = len(set([card.value for card in brow1]))
    value_count2 = len(set([card.value for card in brow2]))
    trips1 = False 
    trips2 = False 
    if value_count1 == 1:
        trips1 = True
    if value_count2 == 1:
        trips2 = True 
    
    #check for zian
    zian1 = False
    zian2 = False 
    if all([card.face for card in brow1]):
        zian1 = True
    if all([card.face for card in brow2]):
        zian2 = True

    #check for straight
    brow1_vals = [card.rank() for card in brow1]
    straight1 = sorted(brow1_vals) == list(range(min(brow1_vals), max(brow1_vals)+1))
    print(brow1_vals)
    brow2_vals = [card.rank() for card in brow2]
    straight2 = sorted(brow2_vals) == list(range(min(brow2_vals), max(brow2_vals)+1))
    print(brow2_vals)
    # A 2 3 straight
    if sorted(list(brow1_vals)) == [2, 3, 14]:
        straight1 = True 

    if sorted(list(brow2_vals)) == [2, 3, 14]:
        straight2 = True 

    #check for straigth to A 
    straightA1 = False 
    straightA2 = False 
    if sorted(list(brow1_vals)) == [12, 13, 14]:
        straightA1 = True 

    if sorted(list(brow2_vals)) == [12, 13, 14]:
        straightA2 = True 

    hand_strength_mapper = {
        0:['royal_straight_flush', 10],
        1:['straight_flush', 5],
        2:['trips',5],
        3:['zian',3],
        4:['straight',3],
        5:['point',1]}

    #Assign hand strength
    hand1_strength = 99
    if straightA1&suited1:
        hand1_strength = 0
    elif straight1&suited1:
        hand1_strength = 1
    elif trips1:
        hand1_strength = 2
    elif zian1:
        hand1_strength = 3
    elif straight1:
        hand1_strength = 4
    else:
        hand1_strength = 5

    hand2_strength = 99
    if straightA2&suited2:
        hand2_strength = 0
    elif straight2&suited2:
        hand2_strength = 1
    elif trips2:
        hand2_strength = 2
    elif zian2:
        hand2_strength = 3
    elif straight2:
        hand2_strength = 4
    else:
        hand2_strength = 5

    print(hand_strength_mapper[hand1_strength][0])
    print(hand_strength_mapper[hand2_strength][0])

    #get kicker
    suit_count1 = len(set([card.suit for card in brow1]))
    suit_count2 = len(set([card.suit for card in brow2]))

    print(suited1,suit_count1)
    print(suited2,suit_count2)

    kickerindex1 = np.argmax([card.rank() for card in brow1])
    kickervalue1 = brow1[kickerindex1]

    kicker1 = kickervalue1.value
    kickerrank1 = kickervalue1.rank()
    kickersuit1 = max([candidate.suit for candidate in brow1 if candidate.value == kickervalue1.value])
    
    kickerindex2 = np.argmax([card.rank() for card in brow2])
    kickervalue2 = brow2[kickerindex2]

    kicker2 = kickervalue2.value
    kickerrank2 = kickervalue2.rank()
    kickersuit2 = max([candidate.suit for candidate in brow2 if candidate.value == kickervalue2.value])

    if hand1_strength<hand2_strength:
        winner = 1
    elif hand2_strength<hand1_strength:
        winner = 2 
    else: #tie breaker
        if hand1_strength==0: #rsf
            winner = compare_kicker(kickerrank1, kickersuit1, kickerrank2, kickersuit2)
        elif hand1_strength==1: #sf
            winner = compare_kicker(kickerrank1, kickersuit1, kickerrank2, kickersuit2)
        elif hand1_strength==2: #trip
            winner = compare_kicker(kickerrank1, kickersuit1, kickerrank2, kickersuit2)
        elif hand1_strength==3: #zian
            if (pair1 == True) & (pair2 == False):
                winner = 1
            elif(pair1 == False) & (pair2 == True):
                winner = 2
            elif(pair1 == True) & (pair2==True):
                if pair_ranks[paircard1]>pair_ranks[paircard2]:
                    winner = 1
                elif pair_ranks[paircard2]>pair_ranks[paircard1]:
                    winner = 2
                else:
                    non_pair1 = [card for card in brow1 if card.value!=paircard1][0]
                    non_pair2 = [card for card in brow2 if card.value!=paircard2][0]
                    non_pair_rank1 = non_pair1.rank()
                    non_pair_rank2 = non_pair2.rank()
                    non_pair_suit1 = non_pair1.suit
                    non_pair_suit2 = non_pair2.suit
                    winner = compare_kicker(non_pair_rank1, non_pair_suit1, non_pair_rank2, non_pair_suit2)
                    if winner == 0:
                        winner = compare_kicker(kickerrank1, kickersuit1, kickerrank2, kickersuit2)
        elif hand1_strength==4: #straight
            winner = compare_kicker(kickerrank1, kickersuit1, kickerrank2, kickersuit2)
        elif hand1_strength == 5:  # When both hands are in the 'score' category
            print('compare_score')
            print(score1)
            print(score2)
            if score1 > score2:
                winner = 1
            elif score2 > score1:
                winner = 2
            else:  # Scores are tied, use additional criteria
                if suited1 and not suited2:
                    winner = 1
                elif not suited1 and suited2:
                    winner = 2
                elif suited1 and suited2:  # Both suited, compare kicker
                    winner = compare_kicker(kickerrank1, kickersuit1, kickerrank2, kickersuit2)
                else:  # Neither hand is suited, compare by pair or kicker
                    if pair1 and not pair2:
                        winner = 1
                    elif not pair1 and pair2:
                        winner = 2
                    elif pair1 and pair2:  # Both have pairs, compare the pairs
                        if pair_ranks[paircard1] > pair_ranks[paircard2]:
                            winner = 1
                        elif pair_ranks[paircard2] > pair_ranks[paircard1]:
                            winner = 2
                        else:  # Pairs are tied, compare kicker
                            winner = compare_kicker(kickerrank1, kickersuit1, kickerrank2, kickersuit2)
                    else:  # No pairs, just compare the kicker
                        winner = compare_kicker(kickerrank1, kickersuit1, kickerrank2, kickersuit2)

    print(f'suited = {suited1} trips = {trips1} zian = {zian1} straight = {straight1} pair = {pair1} pair card = {paircard1} with kicker {kicker1} {kickersuit1}')
    print(f'suited = {suited2} trips = {trips2} zian = {zian2} straight = {straight2} pair = {pair2} pair card = {paircard2} with kicker {kicker2} {kickersuit2}')
    print(winner)

    if winner == 1 :
        if hand1_strength != 5:
            return (1, hand_strength_mapper[hand1_strength][1])
        else:
            if suited1 == True:
                return (1, 3)
            else:
                return (1,1)
    elif winner == 2 : 
        if hand2_strength != 5:
            return (2, hand_strength_mapper[hand2_strength][1])
        else:
            if suited2 == True:
                return (2, 3)
            else:
                return (2,1)
    else:
        return (0,0)

def battle(player1_front, player1_back, player2_front, player2_back):
    winner_front = compare_trow(player1_front, player2_front)
    winner_back = compare_brow(player1_back, player2_back)
    if (winner_front[0] == 1) & (winner_back[0] == 1):
        total = (winner_front[1] + winner_back[1])*2
        print(f'player1 won {total}x')
        return (1, total, True)
    elif (winner_front[0] == 2) & (winner_back[0] == 2):
        total = (winner_front[1]+winner_back[1])*2
        print(f'player2 won {total}x')
        return (2, total, True)
    else:
        score = {1:0,2:0}
        for i in [winner_front, winner_back]:
            try:
                score[i[0]] = score[i[0]]+i[1]
            except:
                pass
        if score[1]>score[2]:
            return (1, score[1] - score[2], False)
        elif score[1]<score[2]:
            return (2, score[2] - score[1], False)
        else:
            return(0,0)
@socketio.on('calculate_score')
def handle_calculate_score(data):
    room = data['room']
    print(f"Calculating score for room: {room}")  # Debugging statement
    calculate_score(room)
    emit('updated_scores', rooms[room]['scores'], room=room)

def calculate_score(room):
    print('start calculate score')
    print(f"Calculating score for room: {room}")  # Debugging statement
    if room in rooms:  # Check if the room exists in the rooms dictionary
        hands = rooms[room]['hands']
        submission = {}

        # Create a copy of the items in the dictionary to avoid modification issues
        hands_copy = list(hands.items())

        # Process hands to determine the results
        for player, cards in hands_copy:
            print(f"Player {player} has hands: {cards}")  # Log each player's hands
            if all(card == 'FOLD' for card in cards):
                submission[player] = [[], [], True]  # Folded
            else:
                cards_object = [convert_raw_to_card(card) for card in cards]
                front_cards = cards_object[0:2]
                back_cards = cards_object[2:]
                submission[player] = [front_cards, back_cards, False]  # Not folded

        # Calculate scores
        for player in rooms[room]['players']:
            rooms[room]['scores']['score_thisturn'][rooms[room]['scores']['players'].index(player)] = 0  # Reset score for this turn

        remaining_players = [player for player in submission if not submission[player][2]]
        folded_players = [player for player in submission if submission[player][2]]

        # Process penalties
        for fold_index, player in enumerate(folded_players):
            # Penalty to be paid by the current folded player
            penalty = 3 * (len(remaining_players) + (len(folded_players) - fold_index - 1))

            # Subtract penalty from the current folded player
            rooms[room]['scores']['score_thisturn'][rooms[room]['scores']['players'].index(player)] -= penalty

            # Give points to all players who have not folded
            for remaining_player in remaining_players:
                rooms[room]['scores']['score_thisturn'][rooms[room]['scores']['players'].index(remaining_player)] += 3

            # Give points to subsequent players who fold after the current folded player
            for subsequent_player in folded_players[fold_index+1:]:
                rooms[room]['scores']['score_thisturn'][rooms[room]['scores']['players'].index(subsequent_player)] += 3
        battle_summary = []  # List to store battle results

        for combination in itertools.combinations(submission, 2):
            player1, player2 = combination
            print(f'{player1} VS {player2}')
            if True in [submission[player1][2], submission[player2][2]]:
                result = (0, 0)
            else:
                result = battle(submission[player1][0], submission[player1][1], submission[player2][0], submission[player2][1])

            if result[0] == 1:
                rooms[room]['scores']['score_thisturn'][rooms[room]['scores']['players'].index(player1)] += result[1]
                rooms[room]['scores']['score_thisturn'][rooms[room]['scores']['players'].index(player2)] -= result[1]
            elif result[0] == 2:
                rooms[room]['scores']['score_thisturn'][rooms[room]['scores']['players'].index(player2)] += result[1]
                rooms[room]['scores']['score_thisturn'][rooms[room]['scores']['players'].index(player1)] -= result[1]
            
                
        # Update total scores
        for i, player in enumerate(rooms[room]['scores']['players']):
            print('update total score')
            rooms[room]['scores']['score_total'][i] += rooms[room]['scores']['score_thisturn'][i]

        # Print scores for debugging
        print("Scores for this turn:")
        for i, player in enumerate(rooms[room]['scores']['players']):
            print(f"Player: {player}, Score this turn: {rooms[room]['scores']['score_thisturn'][i]}, Total Score: {rooms[room]['scores']['score_total'][i]}")

        
        socketio.emit('updated_scores', rooms[room]['scores'], room=room)

@socketio.on('update_score')
def handle_update_score(data):
    player = data['player']
    new_score = int(data['newScore'])
    print(f"Received score update: {player} = {new_score}")  # Debugging line

    room = None
    
    # Find the room where the player is located
    for room_id, room_data in rooms.items():
        if player in room_data['players']:
            room = room_id
            break

    if room:
        index = rooms[room]['scores']['players'].index(player)
        rooms[room]['scores']['score_total'][index] = new_score

        # Emit the updated scores to all clients in the room
        print(f"Broadcasting updated scores: {rooms[room]['scores']}")  # Debugging line

        socketio.emit('updated_scores', rooms[room]['scores'], room=room)

# if __name__ == '__main__':
    # socketio.run(app, debug=True, use_reloader=False)

# if __name__ == '__main__':
#     socketio.run(app, host='0.0.0.0', port=8080, debug=True)

