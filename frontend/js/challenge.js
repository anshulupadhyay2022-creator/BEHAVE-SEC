document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = (window.BEHAVE_CONFIG && window.BEHAVE_CONFIG.API_BASE_URL) || 'http://localhost:8000';
    const CHALLENGE_USER_ID = 'challenge_' + Math.floor(Math.random() * 1e9);
    const TOTAL_TARGETS = 10;

    // ── Phase wrappers ──────────────────────────────────────────
    const phases = {
        keyboard: document.getElementById('panel-owner'),
        mouse:    document.getElementById('panel-mouse'),
        intruder: document.getElementById('panel-intruder'),
    };

    // Hide all except first
    function showPhase(name) {
        Object.keys(phases).forEach(k => {
            if (phases[k]) {
                phases[k].style.display   = (k === name) ? 'block' : 'none';
                phases[k].style.visibility = (k === name) ? 'visible' : 'hidden';
                phases[k].style.opacity   = (k === name) ? '1' : '0';
            }
        });
        // Update step dots
        const dots = { keyboard: 's1', mouse: 's2', intruder: 's3' };
        Object.keys(dots).forEach(k => {
            const el = document.getElementById(dots[k]);
            if (!el) return;
            el.classList.remove('active', 'done');
            const order = ['keyboard','mouse','intruder'];
            const cur   = order.indexOf(name);
            const idx   = order.indexOf(k);
            if (idx < cur)  el.classList.add('done');
            if (idx === cur) el.classList.add('active');
        });
        console.log('[BEHAVE-SEC] Switched to phase:', name);
    }

    // Start at keyboard
    showPhase('keyboard');

    // ── Elements ────────────────────────────────────────────────
    const inputOwner    = document.getElementById('owner-input');
    const btnTrain      = document.getElementById('btn-train');
    const statusOwner   = document.getElementById('owner-status');

    const mouseArena    = document.getElementById('mouse-arena');
    const arenaMsg      = document.getElementById('arena-msg');
    const btnStartMouse = document.getElementById('btn-start-mouse');
    const mouseStatus   = document.getElementById('mouse-status');

    const inputIntruder  = document.getElementById('intruder-input');
    const btnHack        = document.getElementById('btn-hack');
    const statusIntruder = document.getElementById('intruder-status');
    const resultScreen   = document.getElementById('result-screen');
    const resultTitle    = document.getElementById('result-title');
    const resultScore    = document.getElementById('result-score');

    // ── State ───────────────────────────────────────────────────
    let ownerEvents    = [], ownerStartTime    = 0;
    let mouseEvents    = [], mouseStartTime    = 0;
    let intruderEvents = [], intruderStartTime = 0;
    let targetCount    = 0;

    // ── Helper: fire-and-forget training (no blocking) ──────────
    async function trainAsync(events, startTime, prefix, total, onProgress) {
        let ok = 0;
        for (let i = 0; i < total; i++) {
            if (onProgress) onProgress(i + 1, total);
            const sf = i === 0 ? 1.0 : (0.88 + Math.random() * 0.24);
            const j  = i === 0 ? 0   : 12;
            const payload = {
                userId:    CHALLENGE_USER_ID,
                sessionId: prefix + '_' + i + '_' + Date.now(),
                events: events.map(ev => ({
                    ...ev,
                    timestamp:    startTime + Math.round((ev.timestamp - startTime) * sf + (Math.random() * j * 2 - j)),
                    relativeTime: Math.round(ev.relativeTime * sf + (Math.random() * j * 2 - j)),
                    ...(ev.clientX != null ? {
                        clientX: ev.clientX + (i === 0 ? 0 : Math.round(Math.random() * 6 - 3)),
                        clientY: ev.clientY + (i === 0 ? 0 : Math.round(Math.random() * 6 - 3)),
                    } : {}),
                })),
                metadata: {
                    userAgent: navigator.userAgent,
                    screenWidth: window.innerWidth,
                    screenHeight: window.innerHeight,
                    sessionDuration: Date.now() - startTime,
                },
            };
            try {
                const ctrl = new AbortController();
                const tid  = setTimeout(() => ctrl.abort(), 3000);
                const res  = await fetch(API_BASE + '/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal: ctrl.signal,
                });
                clearTimeout(tid);
                if (res.ok) ok++;
            } catch (_) { /* timeout or network error — continue */ }
        }
        return ok;
    }

    // ══════════════════════════════════════════════════════
    // PHASE 1 — KEYBOARD
    // ══════════════════════════════════════════════════════
    inputOwner.addEventListener('keydown', e => {
        if (e.repeat) return;
        if (ownerEvents.length === 0) ownerStartTime = Date.now();
        ownerEvents.push({ eventType: 'keydown', timestamp: Date.now(), relativeTime: Date.now() - ownerStartTime, key: e.key, keyCode: e.keyCode || e.which });
    });
    inputOwner.addEventListener('keyup', e => {
        ownerEvents.push({ eventType: 'keyup', timestamp: Date.now(), relativeTime: Date.now() - ownerStartTime, key: e.key || 'Touch', keyCode: e.keyCode || e.which || 0 });
    });

    btnTrain.addEventListener('click', async () => {
        if (ownerEvents.length < 10) {
            statusOwner.textContent = '⚠ Type more of the phrase first.';
            statusOwner.style.color = '#ff5252';
            return;
        }

        btnTrain.disabled   = true;
        inputOwner.disabled = true;
        statusOwner.style.color = 'var(--accent-primary)';

        const savedEvents = [...ownerEvents];
        const savedStart  = ownerStartTime;

        const ok = await trainAsync(savedEvents, savedStart, 'kb', 15, (i, t) => {
            statusOwner.textContent = `Training keyboard... (${i}/${t})`;
        });

        statusOwner.textContent = ok > 0
            ? `✓ Keyboard locked — ${ok} sessions trained.`
            : '⚠ Backend offline — running in demo mode.';
        statusOwner.style.color = ok > 0 ? '#4CAF50' : '#ffeb3b';

        setTimeout(() => showPhase('mouse'), 900);
    });

    // ══════════════════════════════════════════════════════
    // PHASE 2 — MOUSE
    // ══════════════════════════════════════════════════════
    if (mouseArena) {
        mouseArena.addEventListener('mousemove', e => {
            if (targetCount === 0 && mouseEvents.length === 0) return;
            const r = mouseArena.getBoundingClientRect();
            mouseEvents.push({ eventType: 'mousemove', timestamp: Date.now(), relativeTime: Date.now() - mouseStartTime, clientX: e.clientX - r.left, clientY: e.clientY - r.top, key: null, keyCode: 0 });
        });
    }

    function spawnTarget() {
        const w = mouseArena.clientWidth;
        const h = mouseArena.clientHeight;
        const x = 30 + Math.random() * (w - 60);
        const y = 30 + Math.random() * (h - 60);
        const t = document.createElement('div');
        t.className  = 'arena-target';
        t.style.left = x + 'px';
        t.style.top  = y + 'px';

        t.addEventListener('click', e => {
            e.stopPropagation();
            const r = mouseArena.getBoundingClientRect();
            mouseEvents.push({ eventType: 'click', timestamp: Date.now(), relativeTime: Date.now() - mouseStartTime, clientX: e.clientX - r.left, clientY: e.clientY - r.top, key: null, keyCode: 0 });
            t.classList.add('hit');
            targetCount++;
            mouseStatus.textContent = targetCount + ' / ' + TOTAL_TARGETS + ' targets';
            setTimeout(() => {
                t.remove();
                if (targetCount >= TOTAL_TARGETS) onMouseDone();
                else setTimeout(spawnTarget, 150 + Math.random() * 250);
            }, 250);
        });

        mouseArena.appendChild(t);
    }

    if (btnStartMouse) {
        btnStartMouse.addEventListener('click', () => {
            btnStartMouse.disabled = true;
            if (arenaMsg) arenaMsg.style.display = 'none';
            mouseStartTime = Date.now();
            mouseEvents    = [];
            targetCount    = 0;
            mouseStatus.textContent = '0 / ' + TOTAL_TARGETS + ' targets';
            setTimeout(spawnTarget, 300);
        });
    }

    async function onMouseDone() {
        const savedEvents = [...mouseEvents];
        const savedStart  = mouseStartTime;

        const ok = await trainAsync(savedEvents, savedStart, 'ms', 15, (i, t) => {
            mouseStatus.textContent = `Training mouse... (${i}/${t})`;
        });

        mouseStatus.textContent = ok > 0
            ? `✓ Mouse locked — ${ok} sessions trained.`
            : '⚠ Backend offline — running in demo mode.';
        mouseStatus.style.color = ok > 0 ? '#4CAF50' : '#ffeb3b';

        setTimeout(() => {
            showPhase('intruder');
            if (inputIntruder) inputIntruder.focus();
            if (statusIntruder) statusIntruder.textContent = 'Ready for the hacker...';
            if (btnHack) btnHack.disabled = false;
        }, 900);
    }

    // ══════════════════════════════════════════════════════
    // PHASE 3 — INTRUDER
    // ══════════════════════════════════════════════════════
    if (inputIntruder) {
        inputIntruder.addEventListener('keydown', e => {
            if (e.repeat) return;
            if (intruderEvents.length === 0) intruderStartTime = Date.now();
            intruderEvents.push({ eventType: 'keydown', timestamp: Date.now(), relativeTime: Date.now() - intruderStartTime, key: e.key, keyCode: e.keyCode || e.which });
        });
        inputIntruder.addEventListener('keyup', e => {
            intruderEvents.push({ eventType: 'keyup', timestamp: Date.now(), relativeTime: Date.now() - intruderStartTime, key: e.key || 'Touch', keyCode: e.keyCode || e.which || 0 });
        });
    }

    if (btnHack) {
        btnHack.addEventListener('click', async () => {
            if (intruderEvents.length < 10) {
                statusIntruder.textContent = 'Hacker, type the full phrase first!';
                statusIntruder.style.color = '#ff5252';
                return;
            }

            btnHack.disabled = true;
            statusIntruder.textContent = 'Bypassing mainframe...';
            statusIntruder.style.color = 'var(--accent-primary)';

            const payload = {
                userId:    CHALLENGE_USER_ID,
                sessionId: 'hack_' + Date.now(),
                events:    intruderEvents,
                metadata:  { userAgent: navigator.userAgent, screenWidth: window.innerWidth, screenHeight: window.innerHeight, sessionDuration: Date.now() - intruderStartTime },
            };

            try {
                const ctrl = new AbortController();
                const tid  = setTimeout(() => ctrl.abort(), 5000);
                const res  = await fetch(API_BASE + '/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal: ctrl.signal,
                });
                clearTimeout(tid);
                const data = await res.json();
                showResult(data.anomaly ? data.anomaly.score : 0.5);
            } catch (err) {
                // Demo fallback: if backend offline, show a deterministic result
                statusIntruder.textContent = 'Backend offline — showing demo result.';
                statusIntruder.style.color = '#ffeb3b';
                setTimeout(() => showResult(0.75), 800);
            }
        });
    }

    function showResult(score) {
        if (!resultScreen) return;
        resultScreen.classList.add('show');
        const pct = Math.round(score * 100);
        if (resultScore) resultScore.textContent = 'Anomaly Score: ' + pct + '%';
        
        const title = document.getElementById('result-title');
        const desc = document.getElementById('result-desc');
        
        if (score > 0.55) {
            if (title) { title.textContent = 'ACCESS DENIED'; title.style.color = '#ff5252'; }
            if (desc) desc.textContent = "Your typing rhythm didn't match the owner's profile.";
        } else {
            if (title) { title.textContent = 'HACK SUCCESSFUL'; title.style.color = '#4CAF50'; }
            if (desc) desc.textContent = 'Unbelievable — the hacker perfectly replicated your behavioral fingerprint.';
        }
    }

    // ── Feedback & Restart ──────────────────────────────────────
    window.submitFeedback = async (isOwner) => {
        const statusIntruder = document.getElementById('intruder-status');
        if (statusIntruder) statusIntruder.textContent = 'Syncing feedback...';
        
        try {
            await fetch(API_BASE + '/model/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userId: CHALLENGE_USER_ID, isOwner, isCorrect: true }) // isCorrect is placeholder
            });
            console.log('[BEHAVE-SEC] Feedback sent, isOwner:', isOwner);
        } catch (err) {
            console.warn('[BEHAVE-SEC] Feedback failed:', err);
        }
        
        restartChallenge();
    };

    window.restartChallenge = () => {
        console.log('[BEHAVE-SEC] Restarting challenge...');
        
        // Reset state
        ownerEvents = []; ownerStartTime = 0;
        mouseEvents = []; mouseStartTime = 0;
        intruderEvents = []; intruderStartTime = 0;
        targetCount = 0;
        
        // Reset UI elements
        if (inputOwner) { inputOwner.value = ''; inputOwner.disabled = false; }
        if (btnTrain) { btnTrain.disabled = false; }
        if (statusOwner) { statusOwner.textContent = 'Captured: 0 keys (Need 10)'; statusOwner.style.color = 'var(--text-secondary)'; }
        
        if (btnStartMouse) { btnStartMouse.disabled = false; }
        if (arenaMsg) { arenaMsg.style.display = 'block'; }
        if (mouseStatus) { mouseStatus.textContent = '0 / 10 targets'; mouseStatus.style.color = 'var(--text-secondary)'; }
        if (mouseArena) { mouseArena.innerHTML = '<div id="arena-msg" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:rgba(255,255,255,0.2);">Press START to begin targets</div>'; } // Reset arena targets
        // Re-get elements after wiping innerHTML
        const newArenaMsg = document.getElementById('arena-msg');
        
        if (inputIntruder) { inputIntruder.value = ''; }
        if (btnHack) { btnHack.disabled = true; }
        if (statusIntruder) { statusIntruder.textContent = 'Connecting AI...'; statusIntruder.style.color = 'var(--text-secondary)'; }
        
        if (resultScreen) { resultScreen.classList.remove('show'); }
        
        showPhase('keyboard');
    };
});
