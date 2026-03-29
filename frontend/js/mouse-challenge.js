document.addEventListener('DOMContentLoaded', () => {
    // ── Elements ──
    const arena = document.getElementById('arena');
    const hud = document.getElementById('hud');
    const hudTargets = document.getElementById('hud-targets');
    const hudReact = document.getElementById('hud-react');
    const hudPhase = document.getElementById('hud-phase');
    const phaseLabel = document.getElementById('phase-label');
    const introOverlay = document.getElementById('intro-overlay');
    const transitionOverlay = document.getElementById('transition-overlay');
    const resultOverlay = document.getElementById('result-overlay');

    // ── Config ──
    const TARGETS_PER_ROUND = 15;
    const CHALLENGE_USER_ID = "mouse_user_" + Math.floor(Math.random() * 100000);
    const MARGIN = 80; // px from edges

    // ── State ──
    let phase = 'idle';         // idle, training, intruder
    let targetCount = 0;
    let currentTarget = null;
    let targetSpawnTime = 0;
    let reactionTimes = [];
    let mouseEvents = [];       // All captured mouse events for this phase
    let phaseStartTime = 0;
    let lastMoveTime = 0;

    // ── Mouse Trail Effect ──
    let trailThrottle = 0;
    arena.addEventListener('mousemove', (e) => {
        if (phase === 'idle') return;
        const now = Date.now();
        
        // Capture mouse event
        mouseEvents.push({
            eventType: 'mousemove',
            timestamp: now,
            relativeTime: now - phaseStartTime,
            clientX: e.clientX,
            clientY: e.clientY,
            key: null,
            keyCode: 0
        });

        // Visual trail (throttled)
        if (now - trailThrottle > 30) {
            trailThrottle = now;
            const dot = document.createElement('div');
            dot.className = 'mouse-trail';
            dot.style.left = e.clientX + 'px';
            dot.style.top = e.clientY + 'px';
            arena.appendChild(dot);
            setTimeout(() => dot.remove(), 500);
        }
    });

    // ── Spawn Target ──
    function spawnTarget() {
        const x = MARGIN + Math.random() * (window.innerWidth - MARGIN * 2);
        const y = MARGIN + 60 + Math.random() * (window.innerHeight - MARGIN * 2 - 60);

        const target = document.createElement('div');
        target.className = 'target' + (phase === 'intruder' ? ' intruder-target' : '');
        target.style.left = x + 'px';
        target.style.top = y + 'px';

        target.addEventListener('click', (e) => {
            e.stopPropagation();
            onTargetClick(e, target, x, y);
        });

        arena.appendChild(target);
        currentTarget = target;
        targetSpawnTime = Date.now();
    }

    // ── Target Click Handler ──
    function onTargetClick(e, target, targetX, targetY) {
        const now = Date.now();
        const reaction = now - targetSpawnTime;
        reactionTimes.push(reaction);

        // Calculate click offset from target center
        const offsetX = e.clientX - targetX;
        const offsetY = e.clientY - targetY;

        // Record click event with extra data
        mouseEvents.push({
            eventType: 'click',
            timestamp: now,
            relativeTime: now - phaseStartTime,
            clientX: e.clientX,
            clientY: e.clientY,
            key: null,
            keyCode: 0
        });

        // Visual feedback
        target.classList.add('hit');
        const ripple = document.createElement('div');
        ripple.className = 'click-ripple';
        ripple.style.left = e.clientX + 'px';
        ripple.style.top = e.clientY + 'px';
        arena.appendChild(ripple);
        setTimeout(() => ripple.remove(), 500);

        targetCount++;

        // Update HUD
        hudTargets.textContent = `${targetCount} / ${TARGETS_PER_ROUND}`;
        const avgReact = Math.round(reactionTimes.reduce((a, b) => a + b, 0) / reactionTimes.length);
        hudReact.textContent = `${avgReact} ms`;

        // Remove target after animation
        setTimeout(() => {
            target.remove();
            currentTarget = null;

            if (targetCount >= TARGETS_PER_ROUND) {
                onPhaseComplete();
            } else {
                // Spawn next target after small delay
                setTimeout(spawnTarget, 200 + Math.random() * 300);
            }
        }, 300);
    }

    // ── Missed Click (clicked arena but not target) ──
    arena.addEventListener('click', (e) => {
        if (phase === 'idle') return;
        if (e.target === arena || e.target.className === 'mouse-trail') {
            mouseEvents.push({
                eventType: 'click',
                timestamp: Date.now(),
                relativeTime: Date.now() - phaseStartTime,
                clientX: e.clientX,
                clientY: e.clientY,
                key: null,
                keyCode: 0
            });
        }
    });

    // ── Phase Complete ──
    async function onPhaseComplete() {
        hud.style.display = 'none';
        phaseLabel.style.display = 'none';

        if (phase === 'training') {
            await sendTrainingData();
            transitionOverlay.classList.remove('hidden');
        } else if (phase === 'intruder') {
            await sendIntruderData();
        }
    }

    // ── Send Training Data ──
    async function sendTrainingData() {
        let successCount = 0;

        // 1. Send the real session
        const realPayload = buildPayload("real_mouse_0");
        try {
            const res = await fetch('http://localhost:8000/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(realPayload)
            });
            if (res.ok) successCount++;
        } catch (err) { console.error(err); }

        // 2. Generate synthetic variants (49 more to hit 50 total)
        for (let i = 1; i < 50; i++) {
            const speedFactor = 0.88 + (Math.random() * 0.24); // 0.88x to 1.12x
            const jitter = 12;
            const synPayload = {
                userId: CHALLENGE_USER_ID,
                sessionId: "synth_mouse_" + i + "_" + Date.now(),
                events: mouseEvents.map(ev => ({
                    ...ev,
                    timestamp: phaseStartTime + Math.round((ev.timestamp - phaseStartTime) * speedFactor + (Math.random() * jitter * 2 - jitter)),
                    relativeTime: Math.round(ev.relativeTime * speedFactor + (Math.random() * jitter * 2 - jitter)),
                    // Jitter mouse positions slightly for synthetic variance
                    clientX: ev.clientX !== null ? ev.clientX + Math.round(Math.random() * 6 - 3) : null,
                    clientY: ev.clientY !== null ? ev.clientY + Math.round(Math.random() * 6 - 3) : null
                })),
                metadata: {
                    userAgent: navigator.userAgent,
                    screenWidth: window.innerWidth,
                    screenHeight: window.innerHeight,
                    sessionDuration: Date.now() - phaseStartTime
                }
            };
            try {
                const res = await fetch('http://localhost:8000/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(synPayload)
                });
                if (res.ok) successCount++;
            } catch (err) { console.error(err); }
        }
        console.log(`Training complete: ${successCount}/50 sessions sent.`);
    }

    // ── Send Intruder Data ──
    async function sendIntruderData() {
        const payload = buildPayload("hack_mouse_" + Date.now());
        try {
            const res = await fetch('http://localhost:8000/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            showResult(data.anomaly.score);
        } catch (err) {
            console.error(err);
            showResult(0.5); // fallback
        }
    }

    // ── Build Payload ──
    function buildPayload(sessionId) {
        return {
            userId: CHALLENGE_USER_ID,
            sessionId: sessionId,
            events: mouseEvents,
            metadata: {
                userAgent: navigator.userAgent,
                screenWidth: window.innerWidth,
                screenHeight: window.innerHeight,
                sessionDuration: Date.now() - phaseStartTime
            }
        };
    }

    // ── Show Result ──
    function showResult(anomalyScore) {
        const pct = Math.round(anomalyScore * 100);
        const titleEl = document.getElementById('result-title');
        const pctEl = document.getElementById('result-pct');
        const descEl = document.getElementById('result-desc');

        if (anomalyScore > 0.55) {
            titleEl.textContent = "ACCESS DENIED";
            titleEl.className = "result-score-big fail";
            pctEl.textContent = `Anomaly: ${pct}%`;
            descEl.textContent = "The intruder's mouse behavior didn't match the owner's motor patterns.";
        } else {
            titleEl.textContent = "HACK SUCCESSFUL";
            titleEl.className = "result-score-big pass";
            pctEl.textContent = `Anomaly: ${pct}%`;
            descEl.textContent = "Incredible. The hacker perfectly replicated the owner's mouse fingerprint.";
        }
        resultOverlay.classList.remove('hidden');
    }

    // ── Start Phase ──
    function startPhase(newPhase) {
        phase = newPhase;
        targetCount = 0;
        reactionTimes = [];
        mouseEvents = [];
        phaseStartTime = Date.now();

        // Clear arena
        arena.querySelectorAll('.target, .click-ripple, .mouse-trail').forEach(el => el.remove());

        // Show HUD
        hud.style.display = 'flex';
        hudTargets.textContent = `0 / ${TARGETS_PER_ROUND}`;
        hudReact.textContent = '-- ms';
        hudPhase.textContent = phase === 'training' ? 'TRAIN' : 'HACK';
        hudPhase.className = 'hud-value' + (phase === 'intruder' ? ' red' : '');

        // Phase label
        phaseLabel.style.display = 'block';
        phaseLabel.className = 'phase-label' + (phase === 'intruder' ? ' intruder' : '');
        phaseLabel.textContent = phase === 'training'
            ? 'OWNER TRAINING — Click the targets naturally'
            : 'INTRUDER TEST — Try to replicate the owner\'s behavior';

        // Start spawning
        setTimeout(spawnTarget, 500);
    }

    // ── Button Handlers ──
    document.getElementById('btn-start-train').addEventListener('click', () => {
        introOverlay.classList.add('hidden');
        startPhase('training');
    });

    document.getElementById('btn-start-hack').addEventListener('click', () => {
        transitionOverlay.classList.add('hidden');
        startPhase('intruder');
    });
});
