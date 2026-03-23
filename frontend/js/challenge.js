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

    btnTrain.addEventListener('click', async () => {
        if (ownerEvents.length < 20) {
            statusOwner.textContent = "Type more of the phrase!";
            statusOwner.style.color = "#ff5252";
            return;
        }

        btnTrain.disabled = true;
        statusOwner.textContent = "Training defensive ML model...";
        statusOwner.style.color = "var(--text-secondary)";

        // Fast-track training: Send 10 identical/jittered sessions so the Isolation Forest trains instantly
        let successCount = 0;
        for (let i = 0; i < 10; i++) {
            const payload = {
                userId: CHALLENGE_USER_ID,
                sessionId: "train_sess_" + i + "_" + Date.now(),
                events: ownerEvents.map(ev => ({
                    ...ev,
                    timestamp: ev.timestamp + (Math.random()*4 - 2), // Tiny jitter
                    relativeTime: ev.relativeTime + (Math.random()*4 - 2)
                })),
                metadata: {
                    userAgent: navigator.userAgent,
                    screenWidth: window.innerWidth,
                    screenHeight: window.innerHeight,
                    sessionDuration: Date.now() - ownerStartTime
                }
            };

            try {
                const res = await fetch('http://localhost:8000/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) successCount++;
            } catch (err) {
                console.error(err);
            }
        }

        if (successCount >= 10) {
            statusOwner.textContent = "Profile Locked. Secure.";
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

        if (anomalyScore > 0.6) {
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
