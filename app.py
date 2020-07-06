# compose_flask/app.py
from flask import Flask, request, make_response, session, redirect, jsonify, render_template, Response, send_from_directory
from redis import Redis
from flask_sse import sse

import os
import random
import uuid

SERVER_IP = "10.69.69.86"

cards = {'white':[], 'black':[]}

app = Flask(__name__)
app.secret_key = uuid.uuid4().hex
app.register_blueprint(sse, url_prefix='/stream')
redis = Redis(host='redis', port=6379, decode_responses=True)

app.config["REDIS_URL"] = "redis://" + SERVER_IP

def get_game_id():
    letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(random.sample(letters, 8))

def clear_game():
    redis.flushall()
    new_game()

def new_game():
    for color in cards:
        while redis.llen(color) > 0:
            redis.ltrim(color, 0, -99)

        try:
            file = open(color + ".txt", "r")

            for line in file:
                cards[color].append(line.rstrip("\n"))

            random.shuffle(cards[color])

            for card in cards[color]:
                redis.lpush(color, card)
        except:
            responseData.update({'error' : "Could not load cards from {}.txt".format(color)})

    blackCard = redis.lpop('black')
    redis.set('black-card', blackCard)

def new_black_card():
    blackCard = redis.lpop('black')
    redis.set('black-card', blackCard)
    sse.publish({"blackCard" : blackCard}, type='black-card')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/submit_name')
def submit_name():
    name = request.args.get('name')
    ready = 'no'
    response = make_response("{} has joined!".format(name))

    if not 'pid' in session:
        pid = str(uuid.uuid4())
        session['pid'] = pid

    if redis.get('czar') is None:
        redis.set('czar', session['pid'])
        ready = 'yes'

    redis.lpush('players', session['pid'])
    redis.hset(session['pid'], 'score', 0)
    redis.hset(session['pid'], 'ready', ready)
    redis.hset(session['pid'], 'name', name)
    sse.publish({"pid" : session['pid'], "name" : name}, type='new-player')
    response.set_cookie('pid', session['pid'], max_age=60*60*4)

    return response

@app.route('/submit_winner')
def pick_winner():
    winnerText = request.args.get('card')
    pid = request.args.get('pid')
    czar = redis.get('czar')
    cardText = ""

    responseData = {}

    session['pid'] = session.get('pid')
    if session['pid'] is None:
        if pid is None:
            responseData.update({'error' : "pid is very empty, something went wrong"})
            return jsonify(responseData)
        session['pid'] = pid

    if czar != session['pid']:
        responseData.update({'error' : "Can't pick a winner if you're not the card czar"})
        return jsonify(responseData)

    card = redis.lpop('in-play')

    # Empty the in-play card list and find a winner
    while card is not None:
        cardPid = card.split(":")[0]
        cardText = card.split(":")[1]

        if str(cardText) == str(winnerText):
            winnerName = redis.hget(cardPid, 'name')
            winnerPid = cardPid
            redis.hincrby(winnerPid, 'score', 1)
            responseData.update({'winnerName' : winnerName})

        card = redis.lpop('in-play')

    newCzar = False
    czarNext = False

    while newCzar == False:
        for player in redis.lrange('players', 0, -1):
            redis.hset(player, 'ready', 'no')
            if czarNext:
                czar = player
                redis.hset(player, 'ready', 'yes')
                redis.set('czar', player)

                newCzar = True
                break

            if player == czar:
                czarNext = True

    responseData.update({'newCzar' : czar})

    new_black_card()

    sse.publish({"winner" : winnerPid, "winnerName" : winnerName, "newCzar" : czar}, type='pick-winner')
    return jsonify(responseData)

@app.route('/submit_card')
def submit_card():
    cardIndex = request.args.get('card')
    pid = request.args.get('pid')
    czar = redis.get('czar')
    ready = 'yes'

    responseData = {}

    session['pid'] = session.get('pid')
    if session['pid'] is None:
        if pid is None:
            responseData.update({'error' : "pid is very empty, something went wrong"})
            return jsonify(responseData)
        session['pid'] = pid

    if czar == session['pid']:
        responseData.update({'error' : "Can't pick a card if you're the card czar"})
        return jsonify(responseData)

    redis.hset(session['pid'], 'ready', ready)

    cardText = session['hand'].get(cardIndex)
    redis.lpush('in-play', "{}:{}".format(session['pid'], cardText))

    session['hand'].update({cardIndex : str(redis.lpop('white'))})

    sse.publish({"pid":pid}, type='picked-card')

    responseData.update({'czar' : czar})
    responseData.update({'cardText' : cardText})
    responseData.update({'cardIndex' : cardIndex})
    responseData.update({'blackCard' : str(redis.get('black-card'))})

    if redis.llen('in-play') == redis.llen('players') - 1 and redis.llen('players') > 2:
        cardText = []
        cardsList = []

        # Shuffle and empty the in-play card list
        card = redis.lpop('in-play')
        while card is not None:
            cardsList.append(card)

            card = redis.lpop('in-play')

        random.shuffle(cardsList)

        # Build the new shuffled list and publish the card text to the clients
        for card in cardsList:
            cardText.append(card.split(":")[1])

            redis.lpush('in-play', card)

        # Publish all of the cards in play
        sse.publish({"cards" : cardText}, type='cards-in-play')

    return jsonify(responseData)

@app.route('/')
def root():
    response = make_response(render_template('index.html'))

    return response

@app.route('/get_game_state')
def get_game_state():
    gameState = {'gameState' : 'default'}

    pid = request.args.get('pid')

    while True:
        if pid is None:
            if 'pid' in session:
                response = make_response('{success}')
                response.set_cookie('pid', session['pid'], max_age=60*60*4)
            # No pid was sent, no session exists, create a pid
            gameState.update({'gameState' : 'create-pid'})
            break

        if redis.hlen(pid) == 0:
            # Session not in database, create a new pid
            gameState.update({'gameState' : 'create-pid'})
            break

        if redis.hget(pid, 'name') is None:
            # Name has not yet been set, ask for a name
            gameState.update({'gameState' : 'ask-name'})
            break

        if redis.hget(pid, 'ready') == "no":
            # Card hasn't been picked, pick a card
            gameState.update({'gameState' : 'pick-a-card'})
            break

        if redis.llen('in-play') >= redis.llen('players') - 1 and redis.llen('players') > 2:
            # All cards in play, pick a winner:
            gameState.update({'gameState' : 'pick-a-winner'})
            break

        if redis.hget(pid, 'ready') == "yes" and redis.get('czar') != pid:
            cardText = ""
            czarId = redis.get('czar')

            # Player picked a card, waiting on others
            for card in redis.lrange('in-play', 0, -1):
                cardPid  = card.split(":")[0]

                if cardPid == pid:
                    cardText = card.split(":")[1]

            gameState.update({'gameState' : 'waiting-for-players', 'czar' : czarId, 'blackCard' : redis.get('black-card'), 'myCard' : cardText})

            break

        # Default state, break from loop
        break

    return jsonify(gameState)

@app.route('/get_cards')
def get_cards():
    hand = {}
    if redis.exists('black-card') == 0:
        new_black_card()

    if not 'hand' in session:
        for i in range(10):
            cardIndex = 'card-' + str(i)
            hand.update({cardIndex : str(redis.lpop('white'))})
        session['hand'] = hand
    else:
        hand = session['hand']

    hand.update({'blackCard' : str(redis.get('black-card'))})

    return jsonify(hand)

@app.route('/get_cards_in_play')
def get_cards_in_play():
    cardsInPlay = []
    blackCard = redis.get('black-card')
    czar = redis.get('czar')
    for card in redis.lrange('in-play', 0, -1):
        cardsInPlay.append(card.split(":")[1])

    cards = {'blackCard' : blackCard, 'czar' : czar, 'cards' : cardsInPlay}

    return jsonify(cards)

@app.route('/get_players')
def get_players():
    pids = redis.lrange('players', 0, -1)
    czarId = redis.get('czar')

    players = {}

    for pid in pids:
        czar = 'no'
        if pid == czarId:
            czar = 'yes'
            ready = 'yes'

        name = redis.hget(pid, 'name')
        score = redis.hget(pid, 'score')
        ready = redis.hget(pid, 'ready')
        if ready is None:
            ready = 'no'

        players.update({pid : {'name' : name, 'score' : score, 'czar' : czar, 'ready' : ready}})

    return jsonify(players)

@app.route('/new')
def new():
    new_game()

    response = make_response(redirect('/'))

    return response

@app.route('/clear')
def clear():
    clear_game()

    response = make_response(redirect('/'))

    response.set_cookie('pid', '', 0)

    return response

if __name__ == "__main__":
    new_game()
    app.run(host="0.0.0.0", debug=True)