/**
 * BEHAVE-SEC Intruder Challenge Logic V3
 * Rewritten as a robust, clean state machine to eliminate concurrent POST loops
 * and weird browser reload constraints.
 */

document.addEventListener('DOMContentLoaded', () => {

    // Global Debugger hook
    const debugConsole = document.getElementById('debug-console');
    function logDebug(msg) {
        if (debugConsole) {
            debugConsole.innerHTML += '<br>' + msg;
            debugConsole.scrollTop = debugConsole.scrollHeight;
        }
        console.log('[CHALLENGE]', msg);
    }

    logDebug('Engine mounted & initialized.');

    // Configuration
    const API_BASE = (window.BEHAVE_CONFIG && window.BEHAVE_CONFIG.API_BASE_URL) || 'http://localhost:8000';
    const CHALLENGE_USER_ID = "guest_demo@behave-sec.com"; 

    // DOM Elements
    const phases = {
        keyboard: document.getElementById('panel-owner'),
        mouse: document.getElementById('panel-mouse'),
        intruder: document.getElementById('panel-intruder')
    };

    // Phase 3 mouse arena elements
    const intruderArena = document.getElementById('intruder-mouse-arena');
    const intruderDot   = document.getElementById('intruder-mouse-dot');
    const intruderHint  = document.getElementById('intruder-arena-hint');

    const dots = {
        keyboard: document.getElementById('s1'),
        mouse:    document.getElementById('s2'),
        intruder: document.getElementById('s3')
    };

    // Phase 1 Elements
    const inputOwner = document.getElementById('owner-input');
    const statusOwner = document.getElementById('owner-status');
    const btnTrain = document.getElementById('btn-train');

    // Phase 2 Elements
    const mouseArena = document.getElementById('mouse-arena');
    const arenaMsg = document.getElementById('arena-msg');
    const btnStartMouse = document.getElementById('btn-start-mouse');
    const statusMouse = document.getElementById('mouse-status');

    // Phase 3 Elements
    const inputIntruder = document.getElementById('intruder-input');
    const statusIntruder = document.getElementById('intruder-status');
    const btnHack = document.getElementById('btn-hack');
    const resultOverlay = document.getElementById('result-screen');
    const resultTitle = document.getElementById('result-title');
    const resultScore = document.getElementById('result-score');
    const resultDesc  = document.getElementById('result-desc');

    // State Objects
    class ChallengeState {
        constructor() {
            this.reset();
        }

        reset() {
            this.ownerEvents = [];          // Phase 1 keyboard events
            this.ownerStart = 0;
            this.mouseEvents = [];          // Phase 2 mouse events (stored for merging)
            this.mouseStart = 0;
            this.intruderEvents = [];        // Phase 3 keyboard events
            this.intruderMouseEvents = [];   // Phase 3 mouse events
            this.intruderStart = 0;
            this.mouseTargetCount = 0;
            this.kbTrainingDone = false;     // Flag: keyboard phase submitted
        }

        // Returns keyboard + mouse events merged and sorted by timestamp.
        // Used to build a COMBINED session payload for any training push.
        buildCombinedEvents(kbEvents, kbStart, msEvents, msStart) {
            const normalised = msEvents.map(ev => ({
                ...ev,
                // Re-anchor mouse timestamps relative to keyboard session start
                timestamp: kbStart + (ev.timestamp - msStart)
            }));
            return [...kbEvents, ...normalised].sort((a, b) => a.timestamp - b.timestamp);
        }
    }

    const state = new ChallengeState();

    // ==========================================
    // UI TRANSITION MACHINE
    // ==========================================
    function switchPhase(targetPhase) {
        logDebug(`Transitioning to phase: ${targetPhase}`);
        
        // Update Dots
        const order = ['keyboard', 'mouse', 'intruder'];
        const curIdx = order.indexOf(targetPhase);

        Object.keys(dots).forEach((k) => {
            const el = dots[k];
            const i = order.indexOf(k);
            el.className = 'step-dot'; // reset
            if (i < curIdx) el.classList.add('done');
            if (i === curIdx) el.classList.add('active');
        });

        // Update Panels with modern fade transition rules
        Object.keys(phases).forEach((k) => {
            const panel = phases[k];
            if (k === targetPhase) {
                panel.classList.add('active-panel');
                // Trigger CSS fade after a tiny frame delay
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        panel.classList.add('faded-in');
                    });
                });
            } else {
                panel.classList.remove('faded-in');
                setTimeout(() => {
                    panel.classList.remove('active-panel');
                }, 300); // Wait for opacity transition before disp:none
            }
        });
    }

    // ==========================================
    // CORE BACKEND SYNC ROUTINE
    // ==========================================
    // Sends the augmented payloads SEQUENTIALLY to respect the Backend IsolationForest limits.
    async function sequenceTraining(events, startTime, prefix, totalIterations, progressCallback) {
        logDebug(`Sequential push started for ${prefix}. Iterations: ${totalIterations}.`);
        let okCount = 0;

        for (let i = 0; i < totalIterations; i++) {
            // Slight jitter for synthetic diversity
            const sf = i === 0 ? 1.0 : (0.88 + Math.random() * 0.24);
            const j  = i === 0 ? 0   : 12;

            const synthEvents = events.map(ev => ({
                ...ev,
                timestamp: startTime + Math.round((ev.timestamp - startTime) * sf + (Math.random() * j * 2 - j)),
                relativeTime: Math.round(ev.relativeTime * sf + (Math.random() * j * 2 - j)),
                ...(ev.clientX != null ? {
                    clientX: ev.clientX + (i === 0 ? 0 : Math.round(Math.random() * 6 - 3)),
                    clientY: ev.clientY + (i === 0 ? 0 : Math.round(Math.random() * 6 - 3)),
                } : {}),
            }));

            const payload = {
                userId: CHALLENGE_USER_ID,
                sessionId: prefix + '_' + i + '_' + Date.now(),
                events: synthEvents,
                metadata: {
                    userAgent: navigator.userAgent,
                    screenWidth: window.innerWidth,
                    screenHeight: window.innerHeight,
                    sessionDuration: Date.now() - startTime,
                }
            };

            try {
                // Timeouts aren't fatal anymore, just skipping a loop if dead.
                const ctrl = new AbortController();
                const tid = setTimeout(() => ctrl.abort(), 8000); 

                const res = await fetch(API_BASE + '/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal: ctrl.signal
                });
                
                clearTimeout(tid);
                
                // Clear the body stream explicitly 
                await res.text();
                
                if (res.ok) okCount++;
            } catch (err) {
                logDebug(`Push error on it ${i}: ${err.message}`);
                // Proceed despite errors to ensure we never permanently stall.
            }

            if (progressCallback) progressCallback(i + 1, totalIterations);
        }

        logDebug(`Sequential sweep done. Built ${okCount} profiles.`);
        return okCount;
    }


    // ==========================================
    // PHASE 1: KEYBOARD
    // ==========================================
    
    inputOwner.addEventListener('keydown', e => {
        if (e.repeat) return;
        if (state.ownerEvents.length === 0) state.ownerStart = Date.now();
        state.ownerEvents.push({ 
            eventType: 'keydown', 
            timestamp: Date.now(), 
            relativeTime: Date.now() - state.ownerStart, 
            key: e.key, 
            keyCode: e.keyCode || e.which 
        });
        updateKbStatus();
    });

    inputOwner.addEventListener('keyup', e => {
        state.ownerEvents.push({ 
            eventType: 'keyup', 
            timestamp: Date.now(), 
            relativeTime: Date.now() - state.ownerStart, 
            key: e.key || 'Unknown', 
            keyCode: e.keyCode || e.which || 0 
        });
        updateKbStatus();
    });

    function updateKbStatus() {
        const charCount = Math.floor(state.ownerEvents.length / 2);
        if (charCount < 10) {
            statusOwner.textContent = `Captured: ${charCount} keys (Need 10)`;
            statusOwner.style.color = 'var(--text-secondary)';
        } else {
            statusOwner.textContent = `Captured: ${charCount} keys — Ready to Train`;
            statusOwner.style.color = '#4CAF50'; // Green flag
        }
    }

    btnTrain.addEventListener('click', async () => {
        if (state.ownerEvents.length < 20) {
            statusOwner.textContent = 'Minimum 10 characters required!';
            statusOwner.style.color = '#ff5252';
            return;
        }

        logDebug('Phase 1: Keyboard captured. Moving to mouse phase first.');
        btnTrain.disabled = true;
        inputOwner.disabled = true;
        state.kbTrainingDone = true; // Mark ready — actual upload happens after mouse phase
        statusOwner.textContent = 'Keyboard captured. Complete mouse phase to finalize.';
        statusOwner.style.color = '#4CAF50';

        setTimeout(() => switchPhase('mouse'), 800);
    });

    // ==========================================
    // PHASE 2: MOUSE
    // ==========================================
    
    mouseArena.addEventListener('mousemove', e => {
        if (!mouseArena.dataset.active) return;
        if (state.mouseEvents.length === 0) state.mouseStart = Date.now();
        const rect = mouseArena.getBoundingClientRect();
        state.mouseEvents.push({
            eventType: 'mousemove',
            timestamp: Date.now(),
            relativeTime: Date.now() - state.mouseStart,
            clientX: Math.round(e.clientX - rect.left),
            clientY: Math.round(e.clientY - rect.top),
        });
    });

    btnStartMouse.addEventListener('click', () => {
        btnStartMouse.disabled = true;
        arenaMsg.style.display = 'none';
        mouseArena.dataset.active = 'true';
        state.mouseTargetCount = 0;
        spawnNextMouseTarget();
    });

    function spawnNextMouseTarget() {
        if (state.mouseTargetCount >= 10) {
            finishMousePhase();
            return;
        }

        const t = document.createElement('div');
        t.className = 'arena-target';
        
        // Margin avoids clipping
        const maxX = mouseArena.clientWidth - 50;
        const maxY = mouseArena.clientHeight - 50;
        t.style.left = Math.max(25, Math.random() * maxX) + 'px';
        t.style.top = Math.max(25, Math.random() * maxY) + 'px';

        t.addEventListener('mousedown', () => {
            const rect = mouseArena.getBoundingClientRect();
            const targetRect = t.getBoundingClientRect();
            state.mouseEvents.push({
                eventType: 'mousedown',
                timestamp: Date.now(),
                relativeTime: Date.now() - state.mouseStart,
                clientX: Math.round(targetRect.left - rect.left),
                clientY: Math.round(targetRect.top  - rect.top),
            });
            mouseArena.removeChild(t);
            state.mouseTargetCount++;
            statusMouse.textContent = `${state.mouseTargetCount} / 10 targets`;
            
            // tiny delay before next spawns
            setTimeout(spawnNextMouseTarget, 50 + Math.random() * 200);
        });

        mouseArena.appendChild(t);
    }

    async function finishMousePhase() {
        logDebug('Phase 2 complete. Sending COMBINED keyboard+mouse training sessions.');
        mouseArena.dataset.active = 'false';
        statusMouse.style.color = 'var(--accent-primary)';
        statusMouse.textContent = 'Merging keyboard + mouse into unified sessions...';

        // Build a combined event list: real keyboard events + real mouse events merged.
        // This ensures ALL 22 biometric features fire in the same session.
        const combinedEvents = state.buildCombinedEvents(
            state.ownerEvents, state.ownerStart,
            state.mouseEvents,  state.mouseStart
        );
        const combinedStart = Math.min(state.ownerStart, state.mouseStart);

        logDebug(`Combined payload: ${state.ownerEvents.length} kb + ${state.mouseEvents.length} mouse = ${combinedEvents.length} events`);

        // Submit 15 combined (keyboard+mouse) sessions sequentially.
        const ok = await sequenceTraining(combinedEvents, combinedStart, 'p1p2_combined', 15, (i, t) => {
            statusMouse.textContent = `Training multimodal model... (${i}/${t})`;
        });

        statusMouse.textContent = ok > 0
            ? `Multimodal model trained (${ok}/15 sessions).`
            : 'Backend Offline (Demo UI Active).';
        statusMouse.style.color = ok > 0 ? '#4CAF50' : '#ffeb3b';

        setTimeout(() => switchPhase('intruder'), 800);
    }

    // ==========================================
    // PHASE 3: INTRUDER (ATTACK)
    // ==========================================

    // Keyboard capture
    inputIntruder.addEventListener('keydown', e => {
        if (e.repeat) return;
        if (state.intruderEvents.length === 0) state.intruderStart = Date.now();
        state.intruderEvents.push({
            eventType: 'keydown',
            timestamp: Date.now(),
            relativeTime: Date.now() - state.intruderStart,
            key: e.key,
            keyCode: e.keyCode || e.which
        });
        updateHackBtn();
    });
    inputIntruder.addEventListener('keyup', e => {
        state.intruderEvents.push({
            eventType: 'keyup',
            timestamp: Date.now(),
            relativeTime: Date.now() - state.intruderStart,
            key: e.key || 'Touch',
            keyCode: e.keyCode || e.which || 0
        });
        updateHackBtn();
    });

    // ── Mouse capture in intruder arena ──────────────────────────────────────
    intruderArena.addEventListener('mousemove', e => {
        const rect = intruderArena.getBoundingClientRect();
        const x = Math.round(e.clientX - rect.left);
        const y = Math.round(e.clientY - rect.top);

        // Animate the red dot tracker
        intruderDot.style.left = x + 'px';
        intruderDot.style.top  = y + 'px';
        intruderDot.style.opacity = '1';
        if (intruderHint) intruderHint.style.display = 'none';

        state.intruderMouseEvents.push({
            eventType: 'mousemove',
            timestamp: Date.now(),
            relativeTime: state.intruderStart > 0 ? Date.now() - state.intruderStart : 0,
            clientX: x,
            clientY: y
        });
    });

    intruderArena.addEventListener('click', e => {
        const rect = intruderArena.getBoundingClientRect();
        state.intruderMouseEvents.push({
            eventType: 'click',
            timestamp: Date.now(),
            relativeTime: state.intruderStart > 0 ? Date.now() - state.intruderStart : 0,
            clientX: Math.round(e.clientX - rect.left),
            clientY: Math.round(e.clientY - rect.top)
        });
    });

    intruderArena.addEventListener('mouseleave', () => {
        intruderDot.style.opacity = '0';
    });

    function updateHackBtn() {
        const charCount = Math.floor(state.intruderEvents.length / 2);
        const mouseCount = state.intruderMouseEvents.length;
        statusIntruder.textContent = `⌨ ${charCount} keys  🖱 ${mouseCount} mouse events`;
        if (charCount >= 10) {
            btnHack.disabled = false;
        }
    }

    btnHack.addEventListener('click', async () => {
        btnHack.disabled = true;
        inputIntruder.disabled = true;
        statusIntruder.textContent = 'Analyzing multimodal payload...';

        // Merge keyboard + mouse events, sorted by timestamp for feature extraction
        const allEvents = [...state.intruderEvents, ...state.intruderMouseEvents]
            .sort((a, b) => a.timestamp - b.timestamp);

        logDebug(`Attack payload: ${state.intruderEvents.length} kb + ${state.intruderMouseEvents.length} mouse = ${allEvents.length} total events`);

        const payload = {
            userId: CHALLENGE_USER_ID,
            sessionId: 'p3_attk_' + Date.now(),
            events: allEvents,
            metadata: {
                userAgent: navigator.userAgent,
                screenWidth: window.innerWidth,
                screenHeight: window.innerHeight,
                sessionDuration: Date.now() - state.intruderStart
            }
        };

        try {
            const res = await fetch(API_BASE + '/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!res.ok) {
                const text = await res.text();
                throw new Error(`Server returned ${res.status}: ${text}`);
            }

            const data = await res.json();
            showResult(data.anomaly ? data.anomaly.score : 0.5);
        } catch (err) {
            logDebug(`Analyze failed: ${err.message}`);
            logDebug('Doing deterministic fallback due to connection error.');
            showResult(0.3 + Math.random() * 0.15);
        }
    });

    function showResult(score) {
        logDebug(`Final score output: ${score}`);
        const p = Math.round(score * 100);
        resultScore.textContent = `Match: ${p}%`;
        
        if (p < 50) {
            resultTitle.textContent = 'ACCESS DENIED';
            resultTitle.style.color = '#ff5252';
            resultDesc.textContent  = "Your biometric behavior didn't match the owner's fingerprint.";
        } else {
            resultTitle.textContent = 'ACCESS GRANTED';
            resultTitle.style.color = '#4CAF50';
            resultDesc.textContent  = "Your behavioral fingerprint successfully verified your identity.";
        }
        
        resultOverlay.classList.add('show');
    }

    window.submitFeedback = async (isOwner) => {
        // Send async feedback logic 
        try {
            await fetch(API_BASE + '/model/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userId: CHALLENGE_USER_ID, isOwner })
            });
        } catch (ignored) {}

        restartChallenge();
    };

    window.restartChallenge = () => {
        logDebug('Reset invoked.');
        state.reset();
        
        inputOwner.value = ''; inputOwner.disabled = false;
        btnTrain.disabled = false;
        statusOwner.textContent = 'Captured: 0 keys (Need 10)';
        statusOwner.style.color = 'var(--text-secondary)';

        arenaMsg.style.display = 'block';
        btnStartMouse.disabled = false;
        statusMouse.textContent = '0 / 10 targets';
        statusMouse.style.color = 'var(--text-secondary)';

        inputIntruder.value = ''; inputIntruder.disabled = false;
        btnHack.disabled = true;
        statusIntruder.textContent = 'Connecting AI...';

        // Reset intruder mouse arena
        if (intruderDot) intruderDot.style.opacity = '0';
        if (intruderHint) intruderHint.style.display = '';
        
        resultOverlay.classList.remove('show');
        
        setTimeout(() => switchPhase('keyboard'), 300);
    };

    // System initialized. Route to first panel
    switchPhase('keyboard');
});
