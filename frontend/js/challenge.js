document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const pOwner = document.getElementById('panel-owner');
    const pIntruder = document.getElementById('panel-intruder');
    
    const inputOwner = document.getElementById('owner-input');
    const inputIntruder = document.getElementById('intruder-input');
    
    const btnTrain = document.getElementById('btn-train');
    const btnHack = document.getElementById('btn-hack');
    
    const statusOwner = document.getElementById('owner-status');
    const statusIntruder = document.getElementById('intruder-status');
    
    const resultScreen = document.getElementById('result-screen');
    const resultTitle = document.getElementById('result-title');
    const resultScore = document.getElementById('result-score');
    
    // State
    const CHALLENGE_USER_ID = "challenge_user_" + Math.floor(Math.random() * 100000);
    let ownerEvents = [];
    let intruderEvents = [];
    let ownerStartTime = 0;
    let intruderStartTime = 0;

    // Multi-session enrollment state
    const REQUIRED_ROUNDS = 3;
    let currentRound = 1;
    let allRoundEvents = [];  // Array of arrays: each round's raw events

    // Phase 1: Owner Input
    inputOwner.addEventListener('keydown', (e) => {
        if (!e.repeat) {
            if (ownerEvents.length === 0) ownerStartTime = Date.now();
            ownerEvents.push({
                eventType: 'keydown',
                timestamp: Date.now(),
                relativeTime: Date.now() - ownerStartTime,
                key: e.key,
                keyCode: e.keyCode || e.which
            });
        }
    });

    inputOwner.addEventListener('keyup', (e) => {
        ownerEvents.push({
            eventType: 'keyup',
            timestamp: Date.now(),
            relativeTime: Date.now() - ownerStartTime,
            key: e.key || "Touch",
            keyCode: e.keyCode || e.which || 0
        });
    });

    inputOwner.addEventListener('touchstart', (e) => {
        if (ownerEvents.length === 0) ownerStartTime = Date.now();
        ownerEvents.push({
            eventType: 'touchstart',
            timestamp: Date.now(),
            relativeTime: Date.now() - ownerStartTime,
            key: "Touch",
            keyCode: 0,
            pressure: e.touches[0].force || 0.5
        });
    }, {passive: true});

    inputOwner.addEventListener('touchend', (e) => {
        ownerEvents.push({
            eventType: 'touchend',
            timestamp: Date.now(),
            relativeTime: Date.now() - ownerStartTime,
            key: "Touch",
            keyCode: 0
        });
    }, {passive: true});

    // Update UI status with round information
    function updateRoundStatus() {
        statusOwner.textContent = `Round ${currentRound} of ${REQUIRED_ROUNDS} — Type the phrase and click Train.`;
        statusOwner.style.color = "var(--text-secondary)";
        btnTrain.textContent = `Train Round ${currentRound}/${REQUIRED_ROUNDS}`;
    }
    updateRoundStatus();

    btnTrain.addEventListener('click', async () => {
        if (ownerEvents.length < 20) {
            statusOwner.textContent = "Type more of the phrase!";
            statusOwner.style.color = "#ff5252";
            return;
        }

        // Save this round's real events
        allRoundEvents.push({
            events: [...ownerEvents],
            startTime: ownerStartTime
        });

        if (currentRound < REQUIRED_ROUNDS) {
            // More rounds needed - reset input for next round
            currentRound++;
            ownerEvents = [];
            ownerStartTime = 0;
            inputOwner.value = '';
            inputOwner.focus();
            updateRoundStatus();
            statusOwner.textContent = `Round ${currentRound - 1} captured! Now type it again (Round ${currentRound}/${REQUIRED_ROUNDS}).`;
            statusOwner.style.color = "#4CAF50";
            return;
        }

        // All rounds collected — now train the model
        btnTrain.disabled = true;
        statusOwner.textContent = "All rounds captured! Training ML model with real + synthetic data...";
        statusOwner.style.color = "var(--text-secondary)";

        let successCount = 0;
        let totalSessions = 0;

        // Step 1: Send each real round as-is (3 real sessions)
        for (let r = 0; r < allRoundEvents.length; r++) {
            const roundData = allRoundEvents[r];
            const payload = {
                userId: CHALLENGE_USER_ID,
                sessionId: "real_round_" + r + "_" + Date.now(),
                events: roundData.events,
                metadata: {
                    userAgent: navigator.userAgent,
                    screenWidth: window.innerWidth,
                    screenHeight: window.innerHeight,
                    sessionDuration: roundData.events.length > 0 
                        ? roundData.events[roundData.events.length - 1].timestamp - roundData.startTime 
                        : 0
                }
            };
            try {
                const res = await fetch('http://localhost:8000/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) successCount++;
                totalSessions++;
            } catch (err) { console.error(err); }
        }

        // Step 2: Generate synthetic variants from EACH real round
        // 16 synthetic variants per round * 3 rounds = 48 synthetic + 3 real = 51 total
        const SYNTHETIC_PER_ROUND = 16;
        for (let r = 0; r < allRoundEvents.length; r++) {
            const roundData = allRoundEvents[r];
            const roundStart = roundData.startTime;
            const roundEvents = roundData.events;

            for (let i = 0; i < SYNTHETIC_PER_ROUND; i++) {
                // Realistic human speed variance per synthetic session
                const speedFactor = 0.90 + (Math.random() * 0.20); // 0.90x to 1.10x
                const jitterRange = 10; // +/-10ms per-keystroke jitter
                
                const payload = {
                    userId: CHALLENGE_USER_ID,
                    sessionId: "synth_r" + r + "_s" + i + "_" + Date.now(),
                    events: roundEvents.map(ev => ({
                        ...ev,
                        timestamp: roundStart + Math.round((ev.timestamp - roundStart) * speedFactor + (Math.random() * jitterRange * 2 - jitterRange)),
                        relativeTime: Math.round(ev.relativeTime * speedFactor + (Math.random() * jitterRange * 2 - jitterRange))
                    })),
                    metadata: {
                        userAgent: navigator.userAgent,
                        screenWidth: window.innerWidth,
                        screenHeight: window.innerHeight,
                        sessionDuration: roundEvents.length > 0 
                            ? roundEvents[roundEvents.length - 1].timestamp - roundStart 
                            : 0
                    }
                };

                try {
                    const res = await fetch('http://localhost:8000/analyze', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    if (res.ok) successCount++;
                    totalSessions++;
                } catch (err) { console.error(err); }
            }
        }

        if (successCount >= totalSessions * 0.9) {
            statusOwner.textContent = `Profile Locked. Trained on ${successCount} sessions (${REQUIRED_ROUNDS} real + ${successCount - REQUIRED_ROUNDS} synthetic).`;
            statusOwner.style.color = "#4CAF50";
            
            // Switch UI to Hacker
            pOwner.classList.remove('active');
            pOwner.classList.add('locked');
            inputOwner.disabled = true;

            pIntruder.classList.remove('locked');
            pIntruder.classList.add('active');
            inputIntruder.focus();
            statusIntruder.textContent = "Ready for the hacker...";
            btnHack.disabled = false;
        } else {
            statusOwner.textContent = "Server Error. Is the backend running?";
            statusOwner.style.color = "#ff5252";
            btnTrain.disabled = false;
        }
    });

    // Phase 2: Intruder Input
    inputIntruder.addEventListener('keydown', (e) => {
        if (!e.repeat) {
            if (intruderEvents.length === 0) intruderStartTime = Date.now();
            intruderEvents.push({
                eventType: 'keydown',
                timestamp: Date.now(),
                relativeTime: Date.now() - intruderStartTime,
                key: e.key,
                keyCode: e.keyCode || e.which
            });
        }
    });

    inputIntruder.addEventListener('keyup', (e) => {
        intruderEvents.push({
            eventType: 'keyup',
            timestamp: Date.now(),
            relativeTime: Date.now() - intruderStartTime,
            key: e.key || "Touch",
            keyCode: e.keyCode || e.which || 0
        });
    });

    inputIntruder.addEventListener('touchstart', (e) => {
        if (intruderEvents.length === 0) intruderStartTime = Date.now();
        intruderEvents.push({
            eventType: 'touchstart',
            timestamp: Date.now(),
            relativeTime: Date.now() - intruderStartTime,
            key: "Touch",
            keyCode: 0,
            pressure: e.touches[0].force || 0.5
        });
    }, {passive: true});

    inputIntruder.addEventListener('touchend', (e) => {
        intruderEvents.push({
            eventType: 'touchend',
            timestamp: Date.now(),
            relativeTime: Date.now() - intruderStartTime,
            key: "Touch",
            keyCode: 0
        });
    }, {passive: true});

    btnHack.addEventListener('click', async () => {
        if (intruderEvents.length < 20) {
            statusIntruder.textContent = "Hacker, type more!";
            return;
        }

        btnHack.disabled = true;
        statusIntruder.textContent = "Bypassing mainframe...";

        const payload = {
            userId: CHALLENGE_USER_ID,
            sessionId: "hack_attempt_" + Date.now(),
            events: intruderEvents,
            metadata: {
                userAgent: navigator.userAgent,
                screenWidth: window.innerWidth,
                screenHeight: window.innerHeight,
                sessionDuration: Date.now() - intruderStartTime
            }
        };

        try {
            const res = await fetch('http://localhost:8000/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            showResult(data.anomaly.score);
        } catch (err) {
            statusIntruder.textContent = "Connection lost.";
            btnHack.disabled = false;
        }
    });

    function showResult(anomalyScore) {
        resultScreen.classList.add('show');
        const pct = Math.round(anomalyScore * 100);
        
        resultScore.textContent = `Anomaly Detected: ${pct}%`;

        if (anomalyScore > 0.55) {
            // ML Successfully blocked the intruder
            resultTitle.textContent = "ACCESS DENIED";
            resultTitle.style.color = "#ff5252";
        } else {
            // Intruder mimicked perfectly (Very rare)
            resultTitle.textContent = "HACK SUCCESSFUL";
            resultTitle.style.color = "#4CAF50";
            document.getElementById('result-desc').textContent = "Unbelievable. The hacker perfectly replicated your behavioral fingerprint.";
        }
    }
});
