document.addEventListener('DOMContentLoaded', () => {
    const gameBoard = document.getElementById('game-board');
    const attemptsSpan = document.getElementById('attempts-left');
    const timeSpan = document.getElementById('time-left');
    
    // ICONOS TEMÁTICOS ACTUALIZADOS
    const icons = ['🦜', '🐆', '🐒', '🐍', '🦌', '🌸', '🏺', '🗿']; 

    // Obtener datos desde el JSON_SCRIPT del HTML
    const cardsData = JSON.parse(document.getElementById('cards-data').textContent);
    
    let attempts = parseInt(attemptsSpan.textContent);
    let timeLeft = parseInt(timeSpan.textContent);
    let initialTime = timeLeft; 
    let matchedPairs = 0;
    let totalPairs = cardsData.length / 2;
    let flippedCards = [];
    let lockBoard = false;
    let timer;

    function renderBoard() {
        gameBoard.innerHTML = '';
        cardsData.forEach(val => {
            const card = document.createElement('div');
            card.className = 'card';
            card.dataset.value = val; 
            
            // Convertir el valor (1-8) al icono correspondiente
            const iconIndex = parseInt(val) - 1;

            card.innerHTML = `
                <div class="card-inner">
                    <div class="card-front"></div>
                    <div class="card-back">${icons[iconIndex] || '❓'}</div>
                </div>`;
            card.addEventListener('click', flipCard);
            gameBoard.appendChild(card);
        });
        
        // Ajustar columnas dinámicamente según el número de cartas
        const totalCards = cardsData.length;
        if(totalCards <= 8) gameBoard.style.gridTemplateColumns = 'repeat(4, 100px)';
        else if(totalCards <= 12) gameBoard.style.gridTemplateColumns = 'repeat(4, 100px)';
        else gameBoard.style.gridTemplateColumns = 'repeat(4, 100px)';
    }

    function flipCard() {
        if (lockBoard || this.classList.contains('flipped') || this.classList.contains('matched')) return;
        
        document.getElementById('flip-sound').play();
        this.classList.add('flipped');
        flippedCards.push(this);

        if (flippedCards.length === 2) {
            lockBoard = true;
            const [c1, c2] = flippedCards;
            
            if (c1.dataset.value === c2.dataset.value) {
                c1.classList.add('matched');
                c2.classList.add('matched');
                matchedPairs++;
                flippedCards = [];
                lockBoard = false;
                if (matchedPairs === totalPairs) endGame(true);
            } else {
                attempts--;
                attemptsSpan.textContent = attempts;
                setTimeout(() => {
                    c1.classList.remove('flipped');
                    c2.classList.remove('flipped');
                    flippedCards = [];
                    lockBoard = false;
                    if (attempts <= 0) endGame(false);
                }, 800);
            }
        }
    }

    function startTimer() {
        timer = setInterval(() => {
            timeLeft--;
            timeSpan.textContent = timeLeft;
            if (timeLeft <= 0) {
                clearInterval(timer);
                endGame(false);
            }
        }, 1000);
    }

    function endGame(win) {
        clearInterval(timer);
        lockBoard = true;
        document.getElementById('background-music').pause();

        if (win) document.getElementById('victory-sound').play();
        else document.getElementById('defeat-sound').play();

        const timeUsed = initialTime - timeLeft;

        const payload = {
            result: win ? "win" : "lose",
            level: gameLevelName, 
            time_used: timeUsed,
            attempts_left: attempts
        };

        fetch(endGameUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            $('#endGameLabel').text(win ? "¡Victoria!" : "Agotado");
            $('#endGameMessage').html(`<p>${data.message}</p>`);
            if (win && data.next_level_url) {
                $('#next-level-btn').removeClass('d-none').attr('href', data.next_level_url);
            }

            // Mostrar formulario para guardar en el Leaderboard (siempre, aunque gane o pierda)
            const saveBox = document.getElementById('leaderboard-save-box');
            const savedMsg = document.getElementById('leaderboard-saved-msg');
            if (saveBox) saveBox.classList.remove('d-none');
            if (savedMsg) savedMsg.classList.add('d-none');

            // Prefill con el nombre de usuario si estuviera disponible en el futuro; por ahora queda vacío para que lo escriba.
            const nameInput = document.getElementById('leaderboard-name');
            if (nameInput) nameInput.value = "";

            $('#endGameModal').modal({backdrop: 'static', keyboard: false});
        });

        // Manejar clic en "Guardar en Leaderboard"
        const saveBtn = document.getElementById('leaderboard-save-btn');
        if (saveBtn) {
            // Remover listeners previos clonando el botón
            const newSaveBtn = saveBtn.cloneNode(true);
            saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);

            newSaveBtn.addEventListener('click', function() {
                const nameInput = document.getElementById('leaderboard-name');
                const name = nameInput ? nameInput.value.trim() : "";
                if (!name) {
                    alert("Por favor ingresa tu nombre antes de guardar.");
                    return;
                }

                newSaveBtn.disabled = true;
                newSaveBtn.textContent = "Guardando...";

                fetch(leaderboardSubmitUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({
                        name: name,
                        score: timeUsed,
                        level: gameLevelName
                    })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'success') {
                        newSaveBtn.classList.add('d-none');
                        const savedMsg = document.getElementById('leaderboard-saved-msg');
                        if (savedMsg) savedMsg.classList.remove('d-none');
                    } else {
                        alert(data.message || "No se pudo guardar el puntaje.");
                        newSaveBtn.disabled = false;
                        newSaveBtn.textContent = "Guardar en Leaderboard";
                    }
                })
                .catch(() => {
                    alert("Error de conexión al guardar en el Leaderboard.");
                    newSaveBtn.disabled = false;
                    newSaveBtn.textContent = "Guardar en Leaderboard";
                });
            });
        }
    }

    renderBoard();
    startTimer();
    document.getElementById('background-music').volume = 0.2;
    document.getElementById('background-music').play().catch(() => {});
});