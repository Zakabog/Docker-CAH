var source;

function start() {
    
    $('#submit-card').click(function() {
        $.ajax({
            method: "GET",
            url: "/submit_card",
            data: { pid: getCookie('pid'), card: $('.selected')[0].id }
        }).done(function (data) {
            if ('error' in data) {
                alert(data.error);
                return;
            }
            czar = data.czar;
            cardText = data.cardText;
            blackCard = data.blackCard;

            cardsInPlay({"blackCard" : blackCard, "czar" : czar, "cards" : [cardText]});
            $('#' + data.cardIndex).remove();

            getCards();
        })
    })

    $('#submit-name').click(function() {
        $.ajax({
            method: "GET",
            url: "/submit_name",
            data: { pid: getCookie('pid'), name: $('#player-name')[0].value }
        }).done(function (cardList) {
            $('#askName').addClass('hidden');
            setupGame();
        })
    })

    $('#submit-winner').click(function() {
        myPid = getCookie('pid');
        if ($('#' + myPid).hasClass('czar')) {
            $.ajax({
                method: "GET",
                url: "/submit_winner",
                data: { pid: getCookie('pid'), card: $('.selected')[0].innerHTML}
            }).done(function (cardList) {

            })
        } else {
            return;
        }
    })

    setupGame();
}

function askName() {
    if ($('#askName').hasClass('hidden')) {
        $('#askName').removeClass('hidden');
        return;
    }
}

function addPoint(pid) {
    scoreField = $(`#score-${pid}`)[0];
    score = parseInt(scoreField.innerHTML) + 1;
    scoreField.innerHTML = score;
}

function setupGame() {
    if (source == undefined) {
        source = new EventSource("/stream");
        source.addEventListener('picked-card', function(event) {
            var data = JSON.parse(event.data);
            $('#' + data.pid).removeClass('waiting');
            $('#' + data.pid).addClass('ready');
        }, false);
    
        source.addEventListener('cards-in-play', function(event) {
            var data = JSON.parse(event.data);

            getCardsInPlay();
        }, false);
    
        source.addEventListener('new-player', function(event) {
            var data = JSON.parse(event.data);
            // alert("Player " + data.name + " has joined the game");
            getPlayers();
        }, false);
    
        source.addEventListener('black-card', function(event) {
            var data = JSON.parse(event.data);
            blackCard = data.blackCard;
            $('#black-card-container').empty();
            $('#black-card-container').append(`<li id="black-card" class="black card">${blackCard}</li>`)
        }, false);

        source.addEventListener('pick-winner', function(event) {
            var data = JSON.parse(event.data);
            // Clear the board
            $('.player').removeClass('ready');
            $('.player').removeClass('czar');
            $('#cards-in-play').empty();
            $('#cards-in-play-popup').addClass('hidden')
            $('#overlay').addClass('hidden')
            $('.player').addClass('waiting');

            // Increment the winner score by one
            addPoint(data.winner);

            // Select a new czar
            newCzar = data.newCzar
            $('#' + newCzar).addClass('czar');

            // Announce the winner
            alert(data.winnerName + " got the point!");
        }, false);
    }

    if (getCookie('pid') == null) {
        askName();
        return;
    }

    getGameState();
    getCards();
    getPlayers();
}

function getCookie(key) {
    var keyValue = document.cookie.match('(^|;) ?' + key + '=([^;]*)(;|$)');
    return keyValue ? keyValue[2] : null;
}

function selectCard(card) {
    if ($('#' + card).hasClass('selected')) {
        $('#' + card).removeClass('selected');
        return;
    }

    $('.selected').each(function() {
        $(this).removeClass('selected');
    });

    $('#' + card).addClass('selected');
}

function getCardsInPlay() {
    $.ajax({
        method: "GET",
        url: "/get_cards_in_play"
    }).done(function (cardList) {
        cardsInPlay(cardList);
    })
}

function getGameState() {
    $.ajax({
        method: "GET",
        url: "/get_game_state",
        data: { pid: getCookie('pid') }
    }).done(function (data) {
        gameState = data.gameState
        /*
            if pid is None:
                gameState = 'create-pid'

            if redis.hlen(pid) == 0:
                gameState = 'create-pid'

            if redis.hget(pid, 'name') is None:
                gameState = 'ask-name'

            if redis.hget(pid, 'ready') == "no":
                gameState = 'pick-a-card'

            if redis.llen('in-play') == redis.llen('players') - 1:
                gameState = 'pick-a-winner'
        */
        switch (gameState) {
            case 'create-pid':
                askName();
                break;

            case 'ask-name':
                askName();
                break;

            case 'pick-a-card':
                break;

            case 'pick-a-winner':
                getCardsInPlay();
                break;

            case 'waiting-for-players':
                cardText = data.myCard;
                blackCard = data.blackCard;
                czar = data.czar;

                cardsInPlay({"blackCard" : blackCard, "czar" : czar, "cards" : [cardText]});

                break;
        }
    })
}


function getCards() {
    $.ajax({
        method: "GET",
        url: "/get_cards",
        data: { pid: getCookie('pid') }
    }).done(function (cardList) {
        for (cardIndex in cardList) {
            if (cardIndex == 'blackCard') {
                $('#black-card-container').empty();
                $('#black-card-container').append(`<li id="black-card" class="black card">${cardList[cardIndex]}</li>`)
                continue;
            }
            if ($('#' + cardIndex).length > 0) {
                continue;
            }

            $('#card-container').append(`<li id="${cardIndex}" class="card" onClick="selectCard('${cardIndex}')">${cardList[cardIndex]}</li>`)
        }
    })
}

function cardsInPlay(cardList = {}) {
    if (Object.keys(cardList).length == 0) {
        getCardsInPlay();
        return;
    }

    czar = cardList.czar;

    blackCard = (`<li id="black-card" class="black card">${cardList.blackCard}</li>`)

    $('#overlay').removeClass('hidden')
    $('#cards-in-play-popup').removeClass('hidden')

    if (czar == getCookie('pid')) {
        $('#submit-winner').html("Submit Winner");
        $('#submit-winner').attr('disabled', false);
    } else {
        $('#submit-winner').html("Waiting...");
        $('#submit-winner').attr('disabled', true);
    }

    $('#cards-in-play').empty();

    $('#cards-in-play').append(blackCard)

    for (card in cardList.cards) {
        cardIndex = parseInt(card)
        $('#cards-in-play').append(`<li id=${cardIndex} class="white card" onClick="selectCard('${cardIndex}')">${cardList.cards[cardIndex]}</li>`)
    }
}

function getPlayers() {
    $.ajax({
        method: "GET",
        url: "/get_players"
    }).done(function (playerList) {
        pid = getCookie('pid')

        $('#player-list').empty();

        for (playerId in playerList) {
            var czar = (playerList[playerId]['czar'] == 'yes') ? true : false
            var ready = (playerList[playerId]['ready'] == 'yes') ? true : false
            var playerClass = "player"

            if (playerId == '' | playerId == null | name == 'null') {
                continue;
            }

            if ($('#' + playerId).length > 0) {
                continue;
            }

            if (playerId == pid) {
                playerClass += " self"
            }

            if (czar) {
                playerClass += " czar"
            } else if (ready) {
                playerClass += " ready"
            } else {
                playerClass += " waiting"
            }

            $('#player-list').append(`<li id="${playerId}" class="${playerClass}"><span class="player-name">${playerList[playerId]['name']}</span><span  id="score-${playerId}"class="score">${playerList[playerId]['score']}</span></li>`)
        }
    })
}