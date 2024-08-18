
document.addEventListener('DOMContentLoaded', function () {
    const socket = io('http://localhost:8080', {
        reconnectionAttempts: Infinity,  // Keep trying to reconnect indefinitely
        reconnectionDelay: 1000,         // Initial delay between reconnection attempts (1 second)
        reconnectionDelayMax: 2000,      // Maximum delay between reconnection attempts (5 seconds)
        timeout: 180000,                 // Set connection timeout to 180,000 milliseconds (3 minutes)
        randomizationFactor: 0.5         // Randomization factor for reconnection delays
    });

    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/axios@latest/dist/axios.min.js';
    document.head.appendChild(script);
    script.onload = function () {
    console.log("Axios loaded");




    let selectedCards = [];
    const maxCards = 5;
    let currentTurn = null;
    let timerInterval = null;
    let turnCounter = 1;
    let playerJoinOrder = 0; // Counter to track the order of players joining
    let isFirstPlayer = false; // Boolean to track if the player is the first to join

    // Hide the buttons initially
    const nextTurnButton = document.getElementById('nextTurn');
    const showResultButton = document.getElementById('showResult');
    nextTurnButton.style.display = 'none';
    showResultButton.style.display = 'none';


    const modal = document.getElementById("roundEndModal");
    const closeModalButton = document.getElementById("closeModal");
    const closeSpan = document.getElementsByClassName("close")[0];

    const cardSymbols = {
        'Hearts': '♥️',
        'Diamonds': '♦️',
        'Clubs': '♣️',
        'Spades': '♠️',
        'Joker': '🃏'
    };

    function generateRoomCode() {
        return Math.random().toString(36).substring(2, 8).toUpperCase();
    }

    function formatCard(card) {
        if (card === 'Joker') return `<span style="color: blue;">${cardSymbols['Joker']}</span>`;
        let [value, suit] = card.split(' of ');
        value = value.replace('King', 'K').replace('Queen', 'Q').replace('Jack', 'J');
        const color = (suit === 'Hearts' || suit === 'Diamonds') ? 'red' : 'black';
        return `<span style="color: ${color};">${value} ${cardSymbols[suit]}</span>`;
    }

    
        window.createRoom = async function () {
            const username = document.getElementById('username').value;
            if (username) {
                const room = generateRoomCode();
                try {
                    const result = await axios.post('https://backgamecard.vercel.app/get_user/name', { username })
                    const data = result.data
                    const userId = data[0].uuid
                    const uuiduser = userId

                    pincode = room;
                    const creat_room = await axios.post('https://backgamecard.vercel.app/create_rooms', { pincode, uuiduser })
                    console.log(creat_room)

                    const get_room = await axios.post('https://backgamecard.vercel.app/get_rooms/id', { userId })
                    console.log(get_room)

                } catch (error) {
                    console.error(error)

                }

                document.getElementById('roomCode').value = room;
                document.getElementById('roomDisplay').textContent = `Room Code: ${room}`;
                socket.emit('join', { username, room });
                document.getElementById('lobby').style.display = 'none';
                document.getElementById('game').style.display = 'block';
                document.getElementById('gameStart').style.display = 'block'; // Show the game start button
            } else {
                alert("Please enter your name.");
            }
        };
    
        
    

    let selectedRoom = null;
    window.joinRoom = function (room2 = null) {
        const username = document.getElementById('username').value;
        const room = document.getElementById('roomCode').value;
        // const room2 = document.getElementById('roomCode2').value;
        const uuiduser = document.getElementById('userId').value; 
        console.log(uuiduser);
        
        if (username && room) {
            try{
                const pincode = room
                axios.post('https://backgamecard.vercel.app/create_rooms_two', { pincode, uuiduser })
                selectedRoom = room;
                socket.emit('join', { username, room });
                
    
                document.getElementById('lobby').style.display = 'none';
                document.getElementById('game').style.display = 'block';
            }catch(error){
                console.error(error);
            }

        } else if (username && room2) {
            selectedRoom = room2;
            const room = room2   
            socket.emit('join', { username, room });
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('game').style.display = 'block';

        } else {
            alert("Please enter both your name and a room code.");
        }
    };

    window.startGame = function () {
        const room = document.getElementById('roomCode').value || selectedRoom;
        console.log(room)
        socket.emit('start_game', { room });
        document.getElementById('gameStart').style.display = 'none'; // Hide the game start button
    };

    window.leaveGame = function () {
        const username = document.getElementById('username').value;
        const room = document.getElementById('roomCode').value;
        socket.emit('leave_game', { username, room });
        document.getElementById('lobby').style.display = 'block';
        document.getElementById('game').style.display = 'none';
    };

    window.fold = function () {
        if (document.getElementById('username').value === currentTurn) {
            const username = document.getElementById('username').value;
            const room = document.getElementById('roomCode').value;
            socket.emit('fold', { username, room });
            disableFoldButton();
        } else {
            alert('It must be your turn to fold.');
        }
    };
    window.showResult = function () {
        socket.emit('calculate_score', { room: document.getElementById('roomCode').value || selectedRoom });
        document.getElementById('nextTurn').disabled = false; // Enable Next turn buttion
        document.getElementById('nextTurn').classList.remove('disabled');


    }

    function prepareCardsForServer(selectedCards) {
        // Strip suffixes before sending to the server
        return selectedCards.map(card => card.replace(/-\d+$/, ''));
    }

    // When confirming selection
    window.confirmSelection = function () {
        if (selectedCards.length === 5 && document.getElementById('username').value === currentTurn) {
            const username = document.getElementById('username').value;
            const room = document.getElementById('roomCode').value || selectedRoom;
            const cardsToSend = prepareCardsForServer(selectedCards);

            socket.emit('confirm_selection', { username, room, selectedCards: cardsToSend });
            disableActionButtons();
        } else {
            alert('You must select exactly 5 cards and it must be your turn.');
        }
    };


    window.clearSelection = function () {
        selectedCards = [];
        const selectedElements = document.querySelectorAll('.selected');
        selectedElements.forEach(element => {
            element.classList.remove('selected');
        });
        updateCardSlots();
        enableActionButtons();
    };

    window.nextTurn = function () {

        if (!document.getElementById('nextTurn').disabled) {
            const room = document.getElementById('roomCode').value || selectedRoom;
            console.log(room)
            socket.emit('next_turn', { room });
            resetPlaceholders(); // Reset placeholders when the next turn is initiated
            resetCardSlots(); // Reset top and bottom row card slots
            clearSelection(); // Automatically clear selection for the new turn
        }
    };
    window.controls = function () {
        showCreatorButtons(); // Show the buttons for the first player
        document.getElementById('controls-admin').style.display = 'none';
        document.getElementById('nextTurn').disabled = true;
        document.getElementById('nextTurn').classList.add('disabled');

    };

    window.closeModal = function () {
        modal.style.display = "none";
    }

    closeSpan.onclick = function () {
        modal.style.display = "none";
    }

    window.onclick = function (event) {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    }

    socket.on('user_joined', data => {
        updatePlayerList(data.username);
        const confirmationBox = document.getElementById('confirmationBox');
        const messageElement = document.createElement('p');
        messageElement.textContent = `Player ${data.username} has joined the room.`;
        confirmationBox.appendChild(messageElement);
        console.log(messageElement)




        // Add player to scores table if not already present
        const scoresTable = document.getElementById('scoresTable').querySelector('tbody');
        if (!document.getElementById(`score-${data.username}`)) {
            const row = document.createElement('tr');
            row.id = `score-${data.username}`;
            row.innerHTML = `<td>${data.username}</td>
                         <td id="score-${data.username}-total">0</td>
                         <td><button onclick="editScore('${data.username}')">Edit</button></td>`;
            scoresTable.appendChild(row);
        }
    });

    function hideCreatorButtons() {
        nextTurnButton.style.display = 'none';
        showResultButton.style.display = 'none';
    }

    function showCreatorButtons() {
        nextTurnButton.style.display = 'inline-block';
        showResultButton.style.display = 'inline-block';
    }



    socket.on('update_players', data => {
        const playerList = document.getElementById('players');
        playerList.innerHTML = ''; // Clear existing players

        data.players.forEach(player => {
            updatePlayerList(player);
        });

        document.getElementById('roomDisplay').textContent = `Room Code: ${data.room}`;
    });

    socket.on('deal_cards', data => {
        if (data.username === document.getElementById('username').value) {
            const handElement = document.getElementById('hand');
            handElement.innerHTML = ''; // Clear previous hand
            data.cards.forEach((card, index) => {
                setTimeout(() => {
                    console.log(card)
                    const suffixedCard = `${card}-${index}`; // Add suffix here
                    console.log(`Dealing card with suffix: ${suffixedCard}`); // Debugging line


                    const cardElement = document.createElement('div');
                    cardElement.classList.add('card');
                    cardElement.style.textAlign = 'center'; // Center-align text
                    cardElement.innerHTML = formatCard(suffixedCard); // Display card with emoji
                    cardElement.onclick = () => selectCard(cardElement, suffixedCard); // Pass suffixed card to selection
                    handElement.appendChild(cardElement);
                }, index * 2000); // Delay each card by 2s
            });
            document.getElementById('deck').classList.remove('hidden');
            resetPlaceholders(); // Ensure placeholders are reset when dealing new cards
        }
    });



    socket.on('game_started', data => {
        console.log("Show creator button:" + data.player)
        document.getElementById('dealer').textContent = `Dealer: ${data.dealer}`;
        setCurrentTurn(data.current_turn);
        updatePlayerStatus(data.current_turn, 'YOUR TURN'); // Set the first player's turn to YOUR TURN
        document.getElementById('gameStart').style.display = 'none'; // Hide Game start button
    });

    socket.on('start_timer', data => {
        startTimer(data.time, data.player);
    });

    socket.on('next_turn', data => {
        clearInterval(timerInterval); // Stop the current timer
        if (!data.current_turn) {
            document.getElementById('currentTurn').textContent = 'Round is over';
            return;
        }
        setCurrentTurn(data.current_turn);
        startTimer(180, data.current_turn); // Ensure the timer is reset
        resetPlaceholders(); // Clear the previous turn's placeholders
        turnCounter++; // Increment the turn counter
        updatePlayerStatus(data.current_turn, 'YOUR TURN');
    });

    socket.on('player_confirmed', data => {
        const confirmationBox = document.getElementById('confirmationBox');
        const messageElement = document.createElement('p');
        messageElement.textContent = `Turn ${turnCounter}: Player ${data.username} confirmed`;
        confirmationBox.appendChild(messageElement);

        // Directly update the status to "CONFIRMED"
        const playerElement = document.getElementById(data.username);
        if (playerElement) {
            let statusElement = playerElement.querySelector('.status');
            if (!statusElement) {
                statusElement = document.createElement('div');
                statusElement.classList.add('status');
                playerElement.appendChild(statusElement);
            }
            statusElement.textContent = 'CONFIRMED';
        }

    });

    socket.on('player_folded', data => {
        const confirmationBox = document.getElementById('confirmationBox');
        const messageElement = document.createElement('p');
        messageElement.textContent = `Turn ${turnCounter}: Player ${data.username} folded.`;
        confirmationBox.appendChild(messageElement);

        // Directly update the status to "FOLDED"
        const playerElement = document.getElementById(data.username);
        if (playerElement) {
            let statusElement = playerElement.querySelector('.status');
            if (!statusElement) {
                statusElement = document.createElement('div');
                statusElement.classList.add('status');
                playerElement.appendChild(statusElement);
            }
            statusElement.textContent = 'FOLDED BYES';
        }

        if (data.username === document.getElementById('username').value) {
            disableFoldButton();
        }


    });

    socket.on('reveal_cards', data => {
        const players = Object.keys(data.hands);

        function revealPlayerCards(index = 0) {
            if (index >= players.length) return;

            const player = players[index];
            const playerElement = document.getElementById(player);
            const topRowElement = playerElement.querySelector('.player-top-row');
            const bottomRowElement = playerElement.querySelector('.player-bottom-row');

            topRowElement.innerHTML = ''; // Clear previous cards
            bottomRowElement.innerHTML = '';

            let cardIndex = 0;

            function revealTopCards() {
                if (cardIndex < 2) {
                    const card = data.hands[player][cardIndex];
                    const cardDiv = document.createElement('div');
                    cardDiv.classList.add('card');
                    cardDiv.innerHTML = card === 'FOLD' ? 'FOLD' : formatCard(card);
                    topRowElement.appendChild(cardDiv);
                    cardIndex++;
                    setTimeout(revealTopCards, 300); // Reveal each card in the top row with a delay
                } else {
                    cardIndex = 2;
                    revealBottomCards();
                }
            }

            function revealBottomCards() {
                if (cardIndex < 5) {
                    const card = data.hands[player][cardIndex];
                    const cardDiv = document.createElement('div');
                    cardDiv.classList.add('card');
                    cardDiv.innerHTML = card === 'FOLD' ? 'FOLD' : formatCard(card);
                    bottomRowElement.appendChild(cardDiv);
                    cardIndex++;
                    setTimeout(revealBottomCards, 300); // Reveal each card in the bottom row with a delay
                } else {
                    // After revealing cards for the current player, move to the next player
                    setTimeout(() => revealPlayerCards(index + 1), 500); // Move to the next player after a short delay
                }
            }

            revealTopCards();
        }

        revealPlayerCards(); // Start the revealing process
    });


    socket.on('enable_next_turn', data => {
        console.log('enable_next_turn event triggered');
        console.log('Received data:', data);

        // Enable the "Show Result" button
        document.getElementById('showResult').disabled = false;
        showResultButton.classList.remove('disabled');

        // Update the current turn message
        document.getElementById('currentTurn').textContent = 'TURN IS OVER - PRESS SHOW RESULT';

        // Stop the timer
        clearInterval(timerInterval);

        // Show the modal with a simple message
        const modal = document.getElementById('roundEndModal');
        const playersContainer = document.getElementById('playersContainer');
        playersContainer.innerHTML = ''; // Clear existing content

        console.log('Displaying modal');
        modal.style.display = "block"; // Display the modal immediately

        // Create and display the message
        const messageDiv = document.createElement('div');
        messageDiv.textContent = "All players have taken their turn, ADMIN please show result.";
        messageDiv.style.textAlign = 'center';
        messageDiv.style.fontWeight = 'bold';
        messageDiv.style.marginTop = '20px';
        playersContainer.appendChild(messageDiv);
    });


    // Listen for the updated_scores event
    socket.on('disconnect', () => {
        console.log('Disconnected from server. Attempting to reconnect...');
        // Attempt to reconnect after a short delay
        setTimeout(() => {
            socket.connect();
        }, 1000);
    });

    socket.on('reconnect', () => {
        console.log("Reconnect Successful");
    });


 
    
    socket.on('updated_scores', async scores => {
        console.log(selectedRoom)
        console.log('Received updated scores:', scores); // Debugging line
        const username = document.getElementById('username').value;
        if (scores) {
            try{
                const result = await axios.post('https://backgamecard.vercel.app/get_user/name', { username })
                const data = result.data
                const userId = data[0].uuid

                const get_room = await axios.post('https://backgamecard.vercel.app/get_rooms/id', { userId })
                const data_pin = get_room.data
                const pincode = selectedRoom
                const get_room_pin = await axios.post('https://backgamecard.vercel.app/get_room/pincode', {pincode})
                console.log(get_room_pin.data)
                const existingScores = get_room_pin.data

                scores.players.forEach(async(player, index) => {
                    const playerData = existingScores.find(entry => entry.uuiduser === userId);
                    const previousScore = playerData ? parseInt(playerData.score, 10) : 0;


                    const totalScore = scores.score_total[index] + previousScore || 0;
                    let oldpara = 0
                    let scoresq = scores.score_total[index] || 0
                    const roundScore = scores.score_thisturn[index]; // Assuming score_thisturn is the current round score

                    if(scoresq > oldpara){
                        let score = scoresq - oldpara
                        oldpara+=score
                         try{
                            await axios.post('https://backgamecard.vercel.app/update_scores', { pincode, userId, score });
                            console.log('Score updated successfully');

                            const scoreElement = document.getElementById(`score-${player}-total`);
                            if (scoreElement) {
                                scoreElement.textContent = totalScore;
                                console.log(`Updated DOM element with ID score-${player}-total to ${totalScore}`); // Debugging line
                            } else {
                                console.log(`No DOM element found for player ${player}, adding new row.`); // Debugging line
                                const scoresTable = document.getElementById('scoresTable').querySelector('tbody');
                                const row = document.createElement('tr');
                                row.id = `score-${player}`;
                                row.innerHTML = `<td>${player}</td>
                                                 <td id="score-${player}-total">${totalScore}</td>
                                                 <td><button onclick="editScore('${player}')">Edit</button></td>`;
                                scoresTable.appendChild(row);
                            }
                        }catch(error){
                            console.error(error);
                        }
                    }
                   
                    // Display the round score above "Your Hand" for the current player
                    if (player === username) {
                        const roundScoreDisplay = document.getElementById('roundScoreDisplay');
                        roundScoreDisplay.innerHTML = `<strong>Your Round Score: ${roundScore}</strong>`;
                    }
                });

            }catch(error){
                console.error(error);
            }

        }
    });




    window.editScore = function (player) {
        const scoreCell = document.getElementById(`score-${player}-total`);
        const currentScore = scoreCell.textContent;
        scoreCell.innerHTML = `<input type="text" id="edit-${player}-total" value="${currentScore}">
                               <button onclick="saveScore('${player}')">Save</button>`;
    };

    window.saveScore = function (player) {
        const newScore = document.getElementById(`edit-${player}-total`).value;
        console.log(`Saving score for ${player}: ${newScore}`); // Debugging line
        socket.emit('update_score', { player, newScore });
    };



    socket.on('user_left', data => {
        const playerElement = document.getElementById(data.username);
        if (playerElement) {
            playerElement.remove();
        }
        const confirmationBox = document.getElementById('confirmationBox');
        const messageElement = document.createElement('p');
        messageElement.textContent = `Player ${data.username} has left the game.`;
        confirmationBox.appendChild(messageElement);
    });

    // script.onload = function () {
        socket.on('waiting_area', data => {
            const waitingList = document.getElementById('waitingList');
            waitingList.innerHTML = ''; // Clear existing waiting list
            data.waiting.forEach(player => {
                const playerElement = document.createElement('div');
                playerElement.textContent = player;
                waitingList.appendChild(playerElement);
            });
        });
    // }


    socket.on('next_turn_started', data => {
        setCurrentTurn(data.current_turn);
        resetPlaceholders(); // Reset the card placeholders when the next turn starts
        clearSelection(); // Automatically clear selection for the new turn
        document.getElementById('nextTurn').disabled = true;
        document.getElementById('nextTurn').classList.add('disabled');
        document.getElementById('showResult').disabled = true;
        document.getElementById('showResult').classList.add('disabled');
    });

    socket.on('update_queue', data => {
        const queueList = document.getElementById('queueList');
        queueList.innerHTML = ''; // Clear existing queue

        // Create the table structure
        const table = document.createElement('table');
        table.classList.add('queue-table');

        // Create table header
        const headerRow = document.createElement('tr');
        const headerPlayer = document.createElement('th');
        headerPlayer.textContent = 'Players';
        const headerStatus = document.createElement('th');
        headerStatus.textContent = 'Status';
        headerRow.appendChild(headerPlayer);
        headerRow.appendChild(headerStatus);
        table.appendChild(headerRow);

        // Create table rows for each player
        data.queue.forEach(player => {
            const row = document.createElement('tr');
            const playerCell = document.createElement('td');
            playerCell.textContent = player;

            const statusCell = document.createElement('td');
            const status = data.player_statuses[player];
            statusCell.textContent = status;

            // Apply background color based on status
            if (status === 'FOLDED') {
                statusCell.style.backgroundColor = 'red';
                statusCell.style.color = 'white'; // Optional: Make the text color white for better contrast
            } else if (status === 'CONFIRMED') {
                statusCell.style.backgroundColor = 'green';
                statusCell.style.color = 'white';
            } else if (status === 'WAIT FOR YOUR TURN') {
                statusCell.style.backgroundColor = 'grey';
                statusCell.style.color = 'white';
            } else if (status === 'YOUR TURN') {
                statusCell.style.backgroundColor = 'yellow';
                statusCell.style.color = 'black'; // Black text for better contrast on yellow
            }

            row.appendChild(playerCell);
            row.appendChild(statusCell);
            table.appendChild(row);
        });

        // Append the table to the queueList container
        queueList.appendChild(table);
    });



    function updatePlayerList(player, numCards = 5) {
        let playerElement = document.getElementById(player);
        if (!playerElement) {
            playerElement = document.createElement('div');
            playerElement.id = player;
            playerElement.classList.add('player-container');
            const topRowElement = document.createElement('div');
            topRowElement.classList.add('player-top-row');
            const bottomRowElement = document.createElement('div');
            bottomRowElement.classList.add('player-bottom-row');
            for (let i = 0; i < 2; i++) {
                const cardSlot = document.createElement('div');
                cardSlot.classList.add('card-slot', 'facedown');
                cardSlot.textContent = 'Card';
                cardSlot.style.textAlign = 'center'; // Center-align text
                topRowElement.appendChild(cardSlot);
            }
            for (let i = 0; i < 3; i++) {
                const cardSlot = document.createElement('div');
                cardSlot.classList.add('card-slot', 'facedown');
                cardSlot.textContent = 'Card';
                cardSlot.style.textAlign = 'center'; // Center-align text
                bottomRowElement.appendChild(cardSlot);
            }
            playerElement.appendChild(document.createTextNode(`${player}: `));
            playerElement.appendChild(topRowElement);
            playerElement.appendChild(bottomRowElement);
            document.getElementById('players').appendChild(playerElement);
        } else {
            const topRowElement = playerElement.querySelector('.player-top-row');
            const bottomRowElement = playerElement.querySelector('.player-bottom-row');
            topRowElement.innerHTML = '';
            bottomRowElement.innerHTML = '';
            for (let i = 0; i < 2; i++) {
                const cardSlot = document.createElement('div');
                cardSlot.classList.add('card-slot', 'facedown');
                cardSlot.textContent = 'Card';
                cardSlot.style.textAlign = 'center'; // Center-align text
                topRowElement.appendChild(cardSlot);
            }
            for (let i = 0; i < 3; i++) {
                const cardSlot = document.createElement('div');
                cardSlot.classList.add('card-slot', 'facedown');
                cardSlot.textContent = 'Card';
                cardSlot.style.textAlign = 'center'; // Center-align text
                bottomRowElement.appendChild(cardSlot);
            }
        }
    }

    function selectCard(cardElement, card) {
        console.log(`Card clicked: ${card}`); // Log the clicked card

        // Check if the card is already selected using the full string (including suffix)
        const cardIndex = selectedCards.indexOf(card);

        console.log(`Card index in selectedCards: ${cardIndex}`);

        if (cardIndex !== -1) {
            // If the card is already selected, remove it from the selectedCards array
            selectedCards.splice(cardIndex, 1);
            cardElement.classList.remove('selected');
        } else {
            // If the card is not selected and the max limit is not reached, add it
            if (selectedCards.length < maxCards) {
                selectedCards.push(card);
                cardElement.classList.add('selected');
            } else {
                alert('You can only select up to 5 cards.');
            }
        }

        console.log(`Current selected cards:`, selectedCards); // Log current state of selectedCards

        updateCardSlots();
    }





    function formatCard(card) {
        // Remove any suffix like -0, -1, etc.
        const cleanCard = card.replace(/-\d+$/, '');

        if (cleanCard === 'Joker') return `<span style="color: blue;">${cardSymbols['Joker']}</span>`;

        let [value, suit] = cleanCard.split(' of ');
        value = value.replace('King', 'K').replace('Queen', 'Q').replace('Jack', 'J');
        const color = (suit === 'Hearts' || suit === 'Diamonds') ? 'red' : 'black';
        return `<span style="color: ${color};">${value} ${cardSymbols[suit]}</span>`;
    }


    function updateCardSlots() {
        const topRow = document.getElementById('top-row');
        const bottomRow = document.getElementById('bottom-row');
        topRow.innerHTML = '';
        bottomRow.innerHTML = '';

        selectedCards.forEach((card, index) => {
            const cardSlot = document.createElement('div');
            cardSlot.classList.add('card-slot');
            cardSlot.style.textAlign = 'center'; // Center-align text
            cardSlot.innerHTML = formatCard(card); // Display card with emoji

            if (index < 2) {
                topRow.appendChild(cardSlot);
            } else {
                bottomRow.appendChild(cardSlot);
            }
        });

        // Ensure placeholders are always visible
        while (topRow.children.length < 2) {
            const placeholder = document.createElement('div');
            placeholder.classList.add('card-slot', 'facedown');
            placeholder.style.textAlign = 'center'; // Center-align text
            placeholder.textContent = 'Card';
            topRow.appendChild(placeholder);
        }
        while (bottomRow.children.length < 3) {
            const placeholder = document.createElement('div');
            placeholder.classList.add('card-slot', 'facedown');
            placeholder.style.textAlign = 'center'; // Center-align text
            placeholder.textContent = 'Card';
            bottomRow.appendChild(placeholder);
        }
    }



    function startTimer(duration, player) {
        if (timerInterval) {
            clearInterval(timerInterval);
        }
        let timer = duration, minutes, seconds;
        const display = document.getElementById('timer');
        timerInterval = setInterval(function () {
            minutes = parseInt(timer / 60, 10);
            seconds = parseInt(timer % 60, 10);

            minutes = minutes < 10 ? '0' + minutes : minutes;
            seconds = seconds < 10 ? '0' + seconds : seconds;

            display.textContent = `${minutes}:${seconds}`;

            if (--timer < 0) {
                clearInterval(timerInterval);
                socket.emit('fold', { username: player, room: document.getElementById('roomCode').value });
            }
        }, 1000);
    }

    function setCurrentTurn(player) {
        currentTurn = player;
        const username = document.getElementById('username').value;
        if (username === player) {
            enableActionButtons();
        } else {
            disableActionButtons();
        }
        document.getElementById('currentTurn').innerHTML = `Current Turn: ${player} <span id="timer">03:00</span>`;

        // Update player status
        updatePlayerStatus(player, 'YOUR TURN');
    }

    function resetPlaceholders() {
        const players = document.querySelectorAll('.player-container .player-top-row, .player-bottom-row');
        players.forEach(player => {
            player.innerHTML = '';
            for (let i = 0; i < 2; i++) {
                const cardSlot = document.createElement('div');
                cardSlot.classList.add('card-slot', 'facedown');
                cardSlot.textContent = 'Card';
                cardSlot.style.textAlign = 'center'; // Center-align text
                player.appendChild(cardSlot);
            }
            for (let i = 0; i < 3; i++) {
                const cardSlot = document.createElement('div');
                cardSlot.classList.add('card-slot', 'facedown');
                cardSlot.textContent = 'Card';
                cardSlot.style.textAlign = 'center'; // Center-align text
                player.appendChild(cardSlot);
            }
        });

        resetCardSlots(); // Reset top and bottom rows
    }

    function resetCardSlots() {
        const topRow = document.getElementById('top-row');
        const bottomRow = document.getElementById('bottom-row');
        topRow.innerHTML = '';
        bottomRow.innerHTML = '';
        for (let i = 0; i < 2; i++) {
            const cardSlot = document.createElement('div');
            cardSlot.classList.add('card-slot', 'facedown');
            cardSlot.textContent = 'Card';
            cardSlot.style.textAlign = 'center'; // Center-align text
            topRow.appendChild(cardSlot);
        }
        for (let i = 0; i < 3; i++) {
            const cardSlot = document.createElement('div');
            cardSlot.classList.add('card-slot', 'facedown');
            cardSlot.textContent = 'Card';
            cardSlot.style.textAlign = 'center'; // Center-align text
            bottomRow.appendChild(cardSlot);
        }
    }

    function enableActionButtons() {
        document.getElementById('confirm').disabled = false;
        document.getElementById('fold').disabled = false;
        document.getElementById('confirm').classList.remove('disabled');
        document.getElementById('fold').classList.remove('disabled');
    }

    function disableActionButtons() {
        document.getElementById('confirm').disabled = true;
        document.getElementById('fold').disabled = true;
        document.getElementById('confirm').classList.add('disabled');
        document.getElementById('fold').classList.add('disabled');
    }

    function disableFoldButton() {
        document.getElementById('confirm').disabled = true;
        document.getElementById('confirm').classList.add('disabled');
        const foldButton = document.getElementById('fold');
        foldButton.disabled = true;
        foldButton.classList.add('disabled');
        foldButton.style.backgroundColor = 'red';
    }

    function updateTopBottomRows(topRowElement, bottomRowElement, hand) {
        topRowElement.innerHTML = '';
        bottomRowElement.innerHTML = '';
        hand.forEach((card, index) => {
            const cardSlot = document.createElement('div');
            cardSlot.classList.add('card-slot');
            cardSlot.style.textAlign = 'center'; // Center-align text
            cardSlot.innerHTML = formatCard(card); // Display card with emoji
            if (index < 2) {
                topRowElement.appendChild(cardSlot);
            } else {
                bottomRowElement.appendChild(cardSlot);
            }
        });
    }

    function updatePlayerStatus(player, status) {
        const playerElement = document.getElementById(player);
        if (playerElement) {
            const statusElement = playerElement.querySelector('.status');
            if (statusElement) {
                statusElement.textContent = status;
            } else {
                const newStatusElement = document.createElement('div');
                newStatusElement.classList.add('status');
                newStatusElement.textContent = status;
                playerElement.appendChild(newStatusElement);
            }
        }
    }

    function startTimer(duration, player) {
        if (timerInterval) {
            clearInterval(timerInterval);
        }
        let timer = duration, minutes, seconds;
        const display = document.getElementById('timer');
        timerInterval = setInterval(function () {
            minutes = parseInt(timer / 60, 10);
            seconds = parseInt(timer % 60, 10);

            minutes = minutes < 10 ? '0' + minutes : minutes;
            seconds = seconds < 10 ? '0' + seconds : seconds;

            display.textContent = `${minutes}:${seconds}`;

            if (--timer < 0) {
                clearInterval(timerInterval);
                socket.emit('fold', { username: player, room: document.getElementById('roomCode').value });

                if (player === document.getElementById('username').value) {
                    // Automatically leave the game if the current player's timer runs out
                    leaveGame();
                }
            }
        }, 1000);
    }

    function startTimer(duration, player) {
        if (timerInterval) {
            clearInterval(timerInterval);
        }
        let timer = duration, minutes, seconds;
        const display = document.getElementById('timer');
        timerInterval = setInterval(function () {
            minutes = parseInt(timer / 60, 10);
            seconds = parseInt(timer % 60, 10);

            minutes = minutes < 10 ? '0' + minutes : minutes;
            seconds = seconds < 10 ? '0' + seconds : seconds;

            display.textContent = `${minutes}:${seconds}`;

            if (--timer < 0) {
                clearInterval(timerInterval);
                socket.emit('fold', { username: player, room: document.getElementById('roomCode').value });

                if (player === document.getElementById('username').value) {
                    // Automatically leave the game if the current player's timer runs out
                    leaveGame();
                }
            }
        }, 1000);
    }
    function showModal() {
        modal.style.display = "block";
    }
    socket.on('disconnect', () => {
        console.log('Disconnected from server. Attempting to reconnect...');
        // Attempt to reconnect after a short delay
        setTimeout(() => {
            socket.connect();
        }, 1000);
    });

    
}
});
