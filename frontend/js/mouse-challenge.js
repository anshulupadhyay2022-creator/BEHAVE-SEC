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
    // Use the same userId as challenge.html so both phases write to the SAME model
    const API_BASE = (window.BEHAVE_CONFIG && window.BEHAVE_CONFIG.API_BASE_URL) || 'http://127.0.0.1:8000';
    const CHALLENGE_USER_ID = localStorage.getItem('behave_userId') || 'guest_demo@behave-sec.com';
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
    let lastMouseTime = 0;
    arena.addEventListener('mousemove', (e) => {
        if (phase === 'idle') return;
        const now = Date.now();
        // Throttle to one sample per 100ms to mirror challenge.js behaviour
        if (now - lastMouseTime < 100) return;
        lastMouseTime = now;

        mouseEvents.push({
            eventType: 'mousemove',
            timestamp: now,
            relativeTime: now - phaseStartTime,
            clientX: e.clientX,
            clientY: e.clientY,
            key: null
        });

        // Visual trail (throttled separately for rendering)
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
    // Submits the real session + 14 jittered variants (15 total) to /analyze.
    // Each payload includes ONLY mouse events — this page is a supplementary
    // mouse-only enrollment. The primary multimodal sessions are sent from challenge.js.
    async function sendTrainingData() {
        let successCount = 0;
        console.log(`[mouse-challenge] Sending ${mouseEvents.length} mouse events for user: ${CHALLENGE_USER_ID}`);

        for (let i = 0; i < 15; i++) {
            const sf = i === 0 ? 1.0 : (0.88 + Math.random() * 0.24);
            const j  = i === 0 ? 0   : 10;

            const synEvents = mouseEvents.map(ev => ({
                ...ev,
                timestamp: phaseStartTime + Math.round((ev.timestamp - phaseStartTime) * sf + (Math.random() * j * 2 - j)),
                relativeTime: Math.round(ev.relativeTime * sf),
                clientX: ev.clientX !== null ? ev.clientX + (i === 0 ? 0 : Math.round(Math.random() * 6 - 3)) : null,
                clientY: ev.clientY !== null ? ev.clientY + (i === 0 ? 0 : Math.round(Math.random() * 6 - 3)) : null
            }));

            const payload = {
                userId: CHALLENGE_USER_ID,
                sessionId: 'mc_mouse_' + i + '_' + Date.now(),
                events: synEvents,
                metadata: {
                    userAgent: navigator.userAgent,
                    screenWidth: window.innerWidth,
                    screenHeight: window.innerHeight,
                    sessionDuration: Date.now() - phaseStartTime
                }
            };

            try {
                const res = await fetch(API_BASE + '/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) successCount++;
            } catch (err) {
                console.error('[mouse-challenge] send error:', err);
            }
        }
        console.log(`[mouse-challenge] Training done: ${successCount}/15 sessions sent.`);
    }

    // ── Send Intruder Data ──
    async function sendIntruderData() {
        const payload = buildPayload('mc_hack_' + Date.now());
        try {
            const res = await fetch(API_BASE + '/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            showResult(data.anomaly ? data.anomaly.score : 0.5);
        } catch (err) {
            console.error('[mouse-challenge]', err);
            showResult(0.5);
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
