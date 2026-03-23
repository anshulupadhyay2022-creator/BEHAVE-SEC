document.addEventListener('DOMContentLoaded', () => {
    const textarea = document.getElementById('demo-textarea');
    const trainBtn = document.getElementById('demo-train-btn');
    const testBtn = document.getElementById('demo-test-btn');
    const feedback = document.getElementById('demo-feedback');
    const gaugeFill = document.getElementById('demo-gauge-fill');
    const scoreText = document.getElementById('demo-score-text');
    const statusText = document.getElementById('demo-status-text');

    let events = [];
    let startTime = Date.now();
    const DEMO_USER_ID = "guest_demo_user_" + Math.floor(Math.random() * 10000);
    let isTraining = false;

    // Track Keystrokes
    textarea.addEventListener('keydown', (e) => {
        if (!e.repeat) logEvent('keydown', e);
    });

    textarea.addEventListener('keyup', (e) => {
        logEvent('keyup', e);
    });
    
    // Mobile Touch events
    textarea.addEventListener('touchstart', (e) => {
        logEvent('touchstart', e);
    }, {passive: true});
    
    textarea.addEventListener('touchend', (e) => {
        logEvent('touchend', e);
    }, {passive: true});

    function logEvent(type, e) {
        if (events.length === 0) startTime = Date.now();
        
        const evData = {
            eventType: type,
            timestamp: Date.now(),
            relativeTime: Date.now() - startTime,
            key: e.key || "Touch",
            keyCode: e.keyCode || e.which || 0
        };
        
        if (e.touches && e.touches.length > 0) {
            evData.pressure = e.touches[0].force || 0.5;
        }
        
        events.push(evData);
        
        // Auto-analyze every 20 events if not manually training
        if (events.length >= 20 && !isTraining) {
            analyzeInterim();
        }
    }

    async function sendToAnalyze(forceTrain = false) {
        if (events.length === 0) return null;
        
        const payload = {
            userId: DEMO_USER_ID,
            // Random session ID so the Isolation Forest treats it as a distinct entry
            sessionId: "session_" + Date.now() + "_" + Math.floor(Math.random() * 1000),
            events: [...events],
            metadata: {
                userAgent: navigator.userAgent,
                screenWidth: window.innerWidth,
                screenHeight: window.innerHeight,
                sessionDuration: Date.now() - startTime
            }
        };

        try {
            const res = await fetch('http://localhost:8000/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return await res.json();
        } catch (err) {
            console.error(err);
            return null;
        }
    }

    async function analyzeInterim() {
        if (events.length < 5) return;
        const data = await sendToAnalyze();
        if (data && data.anomaly) {
            updateGauge(data.anomaly.score, data.anomaly.model_ready);
        }
        // Clear events after auto-analyze to keep it lightweight sliding window
        events = [];
        startTime = Date.now();
    }

    trainBtn.addEventListener('click', async () => {
        if (events.length < 20) {
            feedback.textContent = "Please type at least one full sentence to create a strong profile.";
            feedback.style.color = "#ff5252";
            return;
        }
        
        isTraining = true;
        trainBtn.disabled = true;
        feedback.style.color = "var(--text-secondary)";
        feedback.textContent = "Training engine with your unique profile... (0/10)";
        
        // Simulate 10 sessions to quickly fill the IsolationForest buffer for this demo user
        let successCount = 0;
        let lastAnomaly = null;
        
        for (let i = 0; i < 10; i++) {
            // Add tiny random jitter to event timestamps to simulate natural variance 
            // so the IsolationForest has a healthy 10-session distribution
            const jitteredEvents = events.map(ev => ({
                ...ev,
                timestamp: ev.timestamp + Math.floor(Math.random() * 10 - 5),
                relativeTime: ev.relativeTime + Math.floor(Math.random() * 10 - 5)
            }));
            
            const originalEvents = events;
            events = jitteredEvents;
            const data = await sendToAnalyze();
            events = originalEvents;
            
            if (data) {
                successCount++;
                lastAnomaly = data.anomaly;
            }
            feedback.textContent = `Training engine with your unique profile... (${i+1}/10)`;
        }
        
        isTraining = false;
        trainBtn.disabled = false;
        
        if (successCount === 10) {
            feedback.textContent = "Training complete! The engine now recognizes your typing style. Try having someone else type!";
            feedback.style.color = "#4CAF50";
            updateGauge(0.01, true); // Set gauge to green
        } else {
            feedback.textContent = "Error training model. Make sure backend is running.";
            feedback.style.color = "#ff5252";
        }
        events = [];
    });

    testBtn.addEventListener('click', async () => {
        if (events.length < 5) {
            feedback.textContent = "Type a bit more before analyzing.";
            feedback.style.color = "#ff5252";
            return;
        }
        testBtn.disabled = true;
        feedback.textContent = "Analyzing behavior...";
        const data = await sendToAnalyze();
        if (data && data.anomaly) {
            updateGauge(data.anomaly.score, data.anomaly.model_ready);
            feedback.textContent = `Analysis complete. Score: ${(data.anomaly.score*100).toFixed(1)}%`;
        }
        testBtn.disabled = false;
        events = [];
    });

    function updateGauge(score, modelReady) {
        if (!modelReady) {
            statusText.textContent = "Engine Training...";
            statusText.style.color = "var(--text-secondary)";
            return;
        }
        
        // Ensure score is valid
        if (score === undefined || score === null) score = 0;
        
        // Rotate gauge: -135deg is 0%, +45deg is 100% total sweep is 180 degrees.
        const rotation = -135 + (score * 180);
        gaugeFill.style.transform = `rotate(${rotation}deg)`;
        
        const pct = Math.round(score * 100);
        scoreText.textContent = `${pct}%`;
        
        if (score < 0.4) {
            // Normal
            gaugeFill.style.borderTopColor = "#4CAF50";
            gaugeFill.style.borderLeftColor = "#4CAF50";
            scoreText.style.color = "#4CAF50";
            statusText.textContent = "✔ Normal Behavior";
            statusText.style.color = "#4CAF50";
        } else if (score < 0.7) {
            // Suspicious
            gaugeFill.style.borderTopColor = "#ffeb3b";
            gaugeFill.style.borderLeftColor = "#ffeb3b";
            scoreText.style.color = "#ffeb3b";
            statusText.textContent = "⚠ Suspicious";
            statusText.style.color = "#ffeb3b";
        } else {
            // Anomaly
            gaugeFill.style.borderTopColor = "#ff5252";
            gaugeFill.style.borderLeftColor = "#ff5252";
            scoreText.style.color = "#ff5252";
            statusText.textContent = "✖ INTRUDER DETECTED";
            statusText.style.color = "#ff5252";
        }
    }
});
