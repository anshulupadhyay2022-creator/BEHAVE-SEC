document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = (window.BEHAVE_CONFIG && window.BEHAVE_CONFIG.API_BASE_URL) || 'http://localhost:8000';

    // ── Elements ──
    const trainBtn = document.getElementById('demo-train-btn');
    const testBtn = document.getElementById('demo-test-btn');
    const textarea = document.getElementById('demo-textarea');
    const feedback = document.getElementById('demo-feedback');
    const gaugeFill = document.getElementById('demo-gauge-fill');
    const scoreText = document.getElementById('demo-score-text');
    const statusText = document.getElementById('demo-status-text');

    const phaseKeyboard = document.getElementById('phase-keyboard');
    const phaseMouse = document.getElementById('phase-mouse');
    const phaseTest = document.getElementById('phase-test');
    const mouseArena = document.getElementById('mouse-arena');
    const arenaStatus = document.getElementById('arena-status');
    const btnStartMouse = document.getElementById('btn-start-mouse');
    const mouseProgress = document.getElementById('mouse-progress');
    const testTextarea = document.getElementById('test-textarea');

    // Step indicators
    const step1 = document.getElementById('step-1');
    const step2 = document.getElementById('step-2');
    const step3 = document.getElementById('step-3');

    // ── State ──
    const DEMO_USER_ID = "demo_user_" + Math.floor(Math.random() * 100000);
    let keyEvents = [];
    let keyStartTime = 0;
    let mouseEvents = [];
    let mouseStartTime = 0;
    let testEvents = [];
    let testStartTime = 0;
    const TOTAL_TARGETS = 10;
    let targetCount = 0;
    let targetSpawnTime = 0;

    // ═══════════════════════════════════════════════════════════
    // PHASE 1: KEYBOARD TRAINING
    // ═══════════════════════════════════════════════════════════
    textarea.addEventListener('keydown', (e) => {
        if (!e.repeat) {
            if (keyEvents.length === 0) keyStartTime = Date.now();
            keyEvents.push({
                eventType: 'keydown', timestamp: Date.now(),
                relativeTime: Date.now() - keyStartTime,
                key: e.key, keyCode: e.keyCode || e.which
            });
        }
    });
    textarea.addEventListener('keyup', (e) => {
        keyEvents.push({
            eventType: 'keyup', timestamp: Date.now(),
            relativeTime: Date.now() - keyStartTime,
            key: e.key || "Touch", keyCode: e.keyCode || e.which || 0
        });
    });

    trainBtn.addEventListener('click', async () => {
        if (keyEvents.length < 20) {
            feedback.textContent = "Type at least one full sentence first.";
            feedback.style.color = "#ff5252";
            return;
        }

        trainBtn.disabled = true;
        feedback.style.color = "var(--text-secondary)";
        feedback.textContent = "Training keyboard profile... (0/50)";

        const saved = [...keyEvents];
        const savedStart = keyStartTime;
        let ok = 0;

        for (let i = 0; i < 50; i++) {
            const sf = i === 0 ? 1.0 : (0.90 + Math.random() * 0.20);
            const j = i === 0 ? 0 : 10;
            const payload = {
                userId: DEMO_USER_ID,
                sessionId: "kb_" + i + "_" + Date.now(),
                events: saved.map(ev => ({
                    ...ev,
                    timestamp: savedStart + Math.round((ev.timestamp - savedStart) * sf + (Math.random() * j * 2 - j)),
                    relativeTime: Math.round(ev.relativeTime * sf + (Math.random() * j * 2 - j))
                })),
                metadata: { userAgent: navigator.userAgent, screenWidth: window.innerWidth, screenHeight: window.innerHeight, sessionDuration: Date.now() - savedStart }
            };
            try {
                const res = await fetch(API_BASE + '/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                if (res.ok) ok++;
            } catch (err) { console.error(err); }
            if (i % 10 === 0) feedback.textContent = `Training keyboard... (${i}/50)`;
        }

        if (ok >= 45) {
            feedback.textContent = "Keyboard profile locked! Now complete the mouse challenge.";
            feedback.style.color = "#4CAF50";
            // Transition to Phase 2
            phaseKeyboard.style.display = 'none';
            phaseMouse.style.display = 'block';
            step1.style.background = '#4CAF50';
            step2.style.background = 'var(--accent-primary)';
            statusText.textContent = "Phase 2: Mouse";
        } else {
            feedback.textContent = "Error: backend not responding. Is it running on port 8000?";
            feedback.style.color = "#ff5252";
            trainBtn.disabled = false;
        }
    });

    // ═══════════════════════════════════════════════════════════
    // PHASE 2: MOUSE TRAINING
    // ═══════════════════════════════════════════════════════════
    // Track mouse movement inside the arena
    mouseArena.addEventListener('mousemove', (e) => {
        if (targetCount === 0 && mouseEvents.length === 0) return; // not started yet
        const rect = mouseArena.getBoundingClientRect();
        mouseEvents.push({
            eventType: 'mousemove', timestamp: Date.now(),
            relativeTime: Date.now() - mouseStartTime,
            clientX: e.clientX - rect.left, clientY: e.clientY - rect.top,
            key: null, keyCode: 0
        });
    });

    function spawnTarget() {
        const w = mouseArena.clientWidth;
        const h = mouseArena.clientHeight;
        const x = 30 + Math.random() * (w - 60);
        const y = 30 + Math.random() * (h - 60);

        const t = document.createElement('div');
        t.className = 'arena-target';
        t.style.left = x + 'px';
        t.style.top = y + 'px';

        t.addEventListener('click', (e) => {
            e.stopPropagation();
            const rect = mouseArena.getBoundingClientRect();
            mouseEvents.push({
                eventType: 'click', timestamp: Date.now(),
                relativeTime: Date.now() - mouseStartTime,
                clientX: e.clientX - rect.left, clientY: e.clientY - rect.top,
                key: null, keyCode: 0
            });
            t.classList.add('hit');
            targetCount++;
            mouseProgress.textContent = `${targetCount} / ${TOTAL_TARGETS}`;
            setTimeout(() => {
                t.remove();
                if (targetCount >= TOTAL_TARGETS) {
                    onMouseComplete();
                } else {
                    setTimeout(spawnTarget, 150 + Math.random() * 250);
                }
            }, 250);
        });

        mouseArena.appendChild(t);
        targetSpawnTime = Date.now();
    }

    btnStartMouse.addEventListener('click', () => {
        btnStartMouse.disabled = true;
        arenaStatus.style.display = 'none';
        mouseStartTime = Date.now();
        mouseEvents = [];
        targetCount = 0;
        feedback.textContent = "Click the targets!";
        feedback.style.color = "var(--text-secondary)";
        setTimeout(spawnTarget, 300);
    });

    async function onMouseComplete() {
        feedback.textContent = "Mouse profile captured! Training...";
        feedback.style.color = "var(--text-secondary)";

        const saved = [...mouseEvents];
        const savedStart = mouseStartTime;
        let ok = 0;

        for (let i = 0; i < 50; i++) {
            const sf = i === 0 ? 1.0 : (0.88 + Math.random() * 0.24);
            const j = i === 0 ? 0 : 12;
            const payload = {
                userId: DEMO_USER_ID,
                sessionId: "ms_" + i + "_" + Date.now(),
                events: saved.map(ev => ({
                    ...ev,
                    timestamp: savedStart + Math.round((ev.timestamp - savedStart) * sf + (Math.random() * j * 2 - j)),
                    relativeTime: Math.round(ev.relativeTime * sf + (Math.random() * j * 2 - j)),
                    clientX: ev.clientX !== null ? ev.clientX + (i === 0 ? 0 : Math.round(Math.random() * 6 - 3)) : null,
                    clientY: ev.clientY !== null ? ev.clientY + (i === 0 ? 0 : Math.round(Math.random() * 6 - 3)) : null
                })),
                metadata: { userAgent: navigator.userAgent, screenWidth: window.innerWidth, screenHeight: window.innerHeight, sessionDuration: Date.now() - savedStart }
            };
            try {
                const res = await fetch(API_BASE + '/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                if (res.ok) ok++;
            } catch (err) { console.error(err); }
        }

        // Transition to Phase 3
        phaseMouse.style.display = 'none';
        phaseTest.style.display = 'block';
        step2.style.background = '#4CAF50';
        step3.style.background = 'var(--accent-primary)';
        updateGauge(0.01, true);
        feedback.textContent = `Profile locked! Trained on ${ok * 2} total sessions (keyboard + mouse). Hand it over!`;
        feedback.style.color = "#4CAF50";
        statusText.textContent = "Profile Locked";
    }

    // ═══════════════════════════════════════════════════════════
    // PHASE 3: INTRUDER TEST
    // ═══════════════════════════════════════════════════════════
    testTextarea.addEventListener('keydown', (e) => {
        if (!e.repeat) {
            if (testEvents.length === 0) testStartTime = Date.now();
            testEvents.push({
                eventType: 'keydown', timestamp: Date.now(),
                relativeTime: Date.now() - testStartTime,
                key: e.key, keyCode: e.keyCode || e.which
            });
        }
    });
    testTextarea.addEventListener('keyup', (e) => {
        testEvents.push({
            eventType: 'keyup', timestamp: Date.now(),
            relativeTime: Date.now() - testStartTime,
            key: e.key || "Touch", keyCode: e.keyCode || e.which || 0
        });
    });

    testBtn.addEventListener('click', async () => {
        if (testEvents.length < 10) {
            feedback.textContent = "Intruder needs to type more first.";
            feedback.style.color = "#ff5252";
            return;
        }

        testBtn.disabled = true;
        feedback.textContent = "Analyzing intruder behavior...";
        feedback.style.color = "var(--text-secondary)";

        const payload = {
            userId: DEMO_USER_ID,
            sessionId: "intruder_" + Date.now(),
            events: testEvents,
            metadata: { userAgent: navigator.userAgent, screenWidth: window.innerWidth, screenHeight: window.innerHeight, sessionDuration: Date.now() - testStartTime }
        };

        try {
            const res = await fetch('http://localhost:8000/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const data = await res.json();
            if (data && data.anomaly) {
                updateGauge(data.anomaly.score, data.anomaly.model_ready);
                const pct = (data.anomaly.score * 100).toFixed(1);
                const label = data.anomaly.label === 'anomaly' ? 'INTRUDER DETECTED!' : 'Normal behavior.';
                feedback.textContent = `Anomaly: ${pct}% — ${label}`;
                feedback.style.color = data.anomaly.label === 'anomaly' ? '#ff5252' : '#4CAF50';
            }
        } catch (err) {
            feedback.textContent = "Connection error.";
            feedback.style.color = "#ff5252";
        }
        testBtn.disabled = false;
        testEvents = [];
        testStartTime = 0;
        testTextarea.value = '';
    });

    // ── Gauge ──
    function updateGauge(score, modelReady) {
        if (!modelReady) { statusText.textContent = "Training..."; return; }
        if (score === undefined || score === null) score = 0;
        const rotation = -135 + (score * 180);
        gaugeFill.style.transform = `rotate(${rotation}deg)`;
        const pct = Math.round(score * 100);
        scoreText.textContent = `${pct}%`;
        if (score < 0.4) {
            gaugeFill.style.borderTopColor = gaugeFill.style.borderLeftColor = scoreText.style.color = "#4CAF50";
            statusText.textContent = "Normal Behavior"; statusText.style.color = "#4CAF50";
        } else if (score < 0.7) {
            gaugeFill.style.borderTopColor = gaugeFill.style.borderLeftColor = scoreText.style.color = "#ffeb3b";
            statusText.textContent = "Suspicious"; statusText.style.color = "#ffeb3b";
        } else {
            gaugeFill.style.borderTopColor = gaugeFill.style.borderLeftColor = scoreText.style.color = "#ff5252";
            statusText.textContent = "INTRUDER DETECTED"; statusText.style.color = "#ff5252";
        }
    }
});
