/**
 * BEHAVE-SEC Dashboard JS — SOC-style with anomaly trend, gauge, donut, and detection feed.
 */

document.addEventListener('DOMContentLoaded', () => {
    const userId = localStorage.getItem('userId');
    const token  = localStorage.getItem('token');

    if (!userId || !token) {
        window.location.href = 'login.html';
        return;
    }

    // ── 1. Initialize global behavior tracker ─────────────────────────────
    const apiBase = window.BEHAVE_CONFIG ? window.BEHAVE_CONFIG.API_BASE_URL : 'http://localhost:8000';
    const tracker = new BehaviorTracker({
        userId,
        endpoint: `${apiBase}/collect-data`
    });
    window.tracker = tracker;

    // Hook tracker events into stat counters
    window.onBehaviorEvent = (data) => updateLiveStats(data);

    // ── 2. Bootstrap all modules ──────────────────────────────────────────
    startSessionTimer();
    initLiveStreamChart();
    initTypingChallenge();
    initWebSocket(userId, token);
    initReinforcement(userId);
    loadDashboardSummary(token);       // Load historical data from REST API
    drawGauge(0);                      // Initial gauge at 0
});


/* ======================================================================
   SESSION TIMER
   ====================================================================== */
function startSessionTimer() {
    let seconds = 0;
    setInterval(() => {
        seconds++;
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        const el = document.getElementById('session-timer');
        if (el) el.textContent =
            `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    }, 1000);
}


/* ======================================================================
   LIVE STAT COUNTERS  (keystrokes / mouse moves)
   ====================================================================== */
let keyPressCount   = 0;
let mouseMoveCount  = 0;

function updateLiveStats(data) {
    if (data.eventType === 'keydown')   keyPressCount++;
    if (data.eventType === 'mousemove') mouseMoveCount++;

    const kp = document.getElementById('kp-stat');
    const mm = document.getElementById('mm-stat');
    if (kp) kp.textContent = keyPressCount;
    if (mm) mm.textContent = mouseMoveCount;
}


/* ======================================================================
   RISK GAUGE (SVG arc)
   ====================================================================== */
/**
 * @param {number} score  0–100 risk score
 */
function drawGauge(score) {
    const clamped = Math.max(0, Math.min(100, score));
    const ARC_LEN = 251.2;           // total arc length for this path
    const filled  = (clamped / 100) * ARC_LEN;
    const offset  = ARC_LEN - filled;

    // Colour: green → orange → red
    let color = '#4CAF50';
    if (clamped > 30) color = '#FF9800';
    if (clamped > 70) color = '#f43334';

    const arc    = document.getElementById('gauge-arc');
    const needle = document.getElementById('gauge-needle');
    const text   = document.getElementById('gauge-text');

    if (arc) {
        arc.style.strokeDashoffset = offset;
        arc.style.stroke = color;
    }
    if (needle) {
        // Map 0→100 to -90deg→+90deg
        const deg = (clamped / 100) * 180 - 90;
        needle.style.transform = `rotate(${deg}deg)`;
    }
    if (text) text.textContent = Math.round(clamped);

    // Sync KPI risk score display
    const kpiRisk = document.getElementById('risk-score');
    if (kpiRisk) {
        kpiRisk.textContent = Math.round(clamped) + '/100';
        kpiRisk.style.color = color;
    }
}


/* ======================================================================
   WEBSOCKET — real-time session updates
   ====================================================================== */
function initWebSocket(userId, token) {
    const wsUrl = window.BEHAVE_CONFIG ? window.BEHAVE_CONFIG.WS_BASE_URL : 'http://localhost:8000/ws';

    if (typeof signalR === 'undefined') {
        console.warn('[WS] SignalR not loaded — real-time updates disabled.');
        return;
    }

    const conn = new signalR.HubConnectionBuilder()
        .withUrl(`${wsUrl}?user_id=${userId}`)
        .withAutomaticReconnect()
        .build();

    conn.on('new_session', (msg) => {
        // Update gauge
        const risk = parseFloat(msg.riskScore) || 0;
        drawGauge(risk);

        // ── Update live trend chart ──────────────────────────────────────
        // msg.anomalyScore is 0-1; msg.riskScore is 0-100 → normalise to 0-1
        appendTrendPoint(
            parseFloat(msg.anomalyScore) || 0,
            risk / 100,
            msg.anomalyLabel || 'pending'
        );

        // Update AI status KPI
        const anomalyLabel = document.getElementById('anomaly-label');
        const kpiStatusSub = document.getElementById('kpi-status-sub');
        if (anomalyLabel) {
            const isAnomaly = msg.anomalyLabel === 'anomaly';
            anomalyLabel.textContent  = isAnomaly ? 'ANOMALY' : 'Normal';
            anomalyLabel.style.color  = isAnomaly ? 'var(--accent-primary)' : 'var(--success)';
            if (kpiStatusSub) kpiStatusSub.textContent = isAnomaly ? '⚠ Threat detected' : 'All clear';
        }

        // Update humanity label
        const humanityLabel = document.getElementById('humanity-label');
        if (humanityLabel && msg.botDetection) {
            const isHuman = msg.botDetection.is_human;
            humanityLabel.textContent = isHuman ? 'Human' : 'Bot-like';
            humanityLabel.style.color = isHuman ? 'var(--success)' : 'var(--accent-primary)';
        }

        // Prepend to detection feed
        appendEventFeedItem({
            label: msg.anomalyLabel || 'pending',
            risk_score: risk / 100,
            timestamp: new Date().toISOString(),
            hijack_suspected: msg.hijackSuspected,
            event_count: msg.eventsCount,
        });

        // Force-logout flow — show blocking overlay instead of redirecting
        if (msg.forceLogout) {
            const email = localStorage.getItem('userEmail') || '';
            showSessionBlockOverlay(email, msg.riskScore, msg.anomalyScore);
        }
    });

    conn.on('force_logout', (msg) => {
        const email = localStorage.getItem('userEmail') || '';
        showToast('⚠ SECURITY ALERT: ' + msg.reason, 'error');
        showSessionBlockOverlay(email, null, null);
    });

    conn.start()
        .then(() => console.log('[WS] Connected.'))
        .catch(err => console.warn('[WS] Error:', err));
}


/* ======================================================================
   DETECTION FEED
   ====================================================================== */
let feedCount = 0;

function appendEventFeedItem(session) {
    const feed = document.getElementById('detection-feed');
    if (!feed) return;

    // Remove empty placeholder
    const empty = feed.querySelector('.feed-empty');
    if (empty) empty.remove();

    const label     = session.label || 'pending';
    const risk      = Math.round((session.risk_score || 0) * 100);
    const timeStr   = session.timestamp ? new Date(session.timestamp).toLocaleTimeString() : 'Now';
    const hijack    = session.hijack_suspected;

    const item = document.createElement('div');
    item.className = 'feed-item';
    item.innerHTML = `
        <span class="feed-label ${label}">${label.toUpperCase()}</span>
        <div class="feed-meta">
            <div class="feed-risk">Risk: ${risk}%</div>
            <div class="feed-time">${timeStr}</div>
            ${hijack ? '<div class="feed-hijack">⚠ IP/Agent change suspected</div>' : ''}
        </div>
    `;

    // Prepend newest at top
    feed.insertBefore(item, feed.firstChild);

    // Cap at 20 items
    feedCount++;
    const items = feed.querySelectorAll('.feed-item');
    if (items.length > 20) items[items.length - 1].remove();
}


/* ======================================================================
   LOAD DASHBOARD SUMMARY (REST API on page load)
   ====================================================================== */
async function loadDashboardSummary(token) {
    const apiBase = window.BEHAVE_CONFIG ? window.BEHAVE_CONFIG.API_BASE_URL : 'http://localhost:8000';
    try {
        const res = await fetch(`${apiBase}/dashboard/summary`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // KPI: totals
        const totalEl = document.getElementById('total-sessions-val');
        const eventsEl = document.getElementById('kpi-events-sub');
        if (totalEl) totalEl.textContent = data.totalSessions ?? '—';
        if (eventsEl) eventsEl.textContent = `${data.totalEvents ?? 0} events`;

        // Trend count badge
        const trendBadge = document.getElementById('trend-session-count');
        if (trendBadge) trendBadge.textContent = `${data.totalSessions} sessions`;

        // Avg risk today
        const avgEl = document.getElementById('avg-risk-today');
        if (avgEl) avgEl.textContent = ((data.avg_risk_today || 0) * 100).toFixed(1) + '%';

        // Anomaly trend chart
        if (data.anomaly_trend && data.anomaly_trend.length > 0) {
            renderTrendChart(data.anomaly_trend);
        }

        // Donut chart
        if (data.detection_stats) {
            renderDonutChart(data.detection_stats);
        }

        // Detection feed (historical, from old to new so newest ends up on top)
        if (data.recent_feed && data.recent_feed.length > 0) {
            const feed = document.getElementById('detection-feed');
            if (feed) feed.innerHTML = ''; // clear placeholder
            [...data.recent_feed].reverse().forEach(session => appendEventFeedItem(session));
        }

    } catch (err) {
        console.warn('[Dashboard] Could not load summary:', err.message);
        // Graceful degradation — charts stay empty, no crash
    }
}


/* ======================================================================
   ANOMALY TREND CHART  (line, Chart.js)
   ====================================================================== */
let trendChart = null;

function renderTrendChart(trendData) {
    const ctx = document.getElementById('trendChart');
    if (!ctx) return;

    const labels = trendData.map(d => {
        if (!d.timestamp) return '';
        const t = new Date(d.timestamp);
        return t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    const scores    = trendData.map(d => Math.round((d.score || 0) * 100));
    const riskScores = trendData.map(d => Math.round((d.risk_score || 0) * 100));
    const colors    = trendData.map(d => d.label === 'anomaly' ? '#f43334' : '#4CAF50');

    if (trendChart) trendChart.destroy();

    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Anomaly Score',
                    data: scores,
                    borderColor: '#f43334',
                    backgroundColor: 'rgba(244,51,52,0.08)',
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 4,
                    pointBackgroundColor: colors,
                    fill: true,
                },
                {
                    label: 'Risk Score',
                    data: riskScores,
                    borderColor: '#FF9800',
                    backgroundColor: 'rgba(255,152,0,0.05)',
                    tension: 0.4,
                    borderWidth: 1.5,
                    pointRadius: 2,
                    borderDash: [4, 2],
                    fill: false,
                },
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(255,255,255,0.06)' },
                    ticks: { color: '#8b949e', font: { size: 10 }, callback: v => v + '%' },
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#8b949e', font: { size: 10 }, maxRotation: 0, maxTicksLimit: 8 },
                }
            },
            plugins: {
                legend: { display: true, labels: { color: '#8b949e', font: { size: 10 }, boxWidth: 10, padding: 12 } },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}%`
                    }
                }
            },
            animation: { duration: 600 }
        }
    });
}

// Live stream appender — adds real-time data to trend chart
function appendTrendPoint(score, riskScore, label) {
    if (!trendChart) return;
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const color = label === 'anomaly' ? '#f43334' : '#4CAF50';

    trendChart.data.labels.push(now);
    trendChart.data.datasets[0].data.push(Math.round(score * 100));
    trendChart.data.datasets[0].pointBackgroundColor.push(color);
    trendChart.data.datasets[1].data.push(Math.round(riskScore * 100));

    if (trendChart.data.labels.length > 30) {
        trendChart.data.labels.shift();
        trendChart.data.datasets.forEach(ds => {
            ds.data.shift();
            if (ds.pointBackgroundColor) ds.pointBackgroundColor.shift();
        });
    }
    trendChart.update('none');
}


/* ======================================================================
   DETECTION DONUT CHART  (Chart.js)
   ====================================================================== */
let donutChart = null;

function renderDonutChart(stats) {
    const ctx = document.getElementById('donutChart');
    if (!ctx) return;

    const normal  = stats.normal  || 0;
    const anomaly = stats.anomaly || 0;
    const pending = stats.pending || 0;

    // Legend
    const legNormal  = document.getElementById('leg-normal');
    const legAnomaly = document.getElementById('leg-anomaly');
    const legPending = document.getElementById('leg-pending');
    if (legNormal)  legNormal.textContent  = `Normal: ${normal}`;
    if (legAnomaly) legAnomaly.textContent = `Anomaly: ${anomaly}`;
    if (legPending) legPending.textContent = `Pending: ${pending}`;

    if (donutChart) donutChart.destroy();

    const total = normal + anomaly + pending || 1;

    donutChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Normal', 'Anomaly', 'Pending'],
            datasets: [{
                data: [normal, anomaly, pending],
                backgroundColor: [
                    'rgba(76,175,80,0.85)',
                    'rgba(244,51,52,0.85)',
                    'rgba(255,152,0,0.65)',
                ],
                borderColor: ['#4CAF50', '#f43334', '#FF9800'],
                borderWidth: 1.5,
                hoverOffset: 6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '68%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const pct = Math.round((ctx.parsed / total) * 100);
                            return `${ctx.label}: ${ctx.parsed} (${pct}%)`;
                        }
                    }
                }
            },
            animation: { duration: 800 }
        }
    });
}


/* ======================================================================
   LIVE BEHAVIOR STREAM CHART
   ====================================================================== */
function initLiveStreamChart() {
    const ctx = document.getElementById('behaviorChart');
    if (!ctx) return;

    const streamChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Events/sec',
                data: [],
                borderColor: '#f43334',
                backgroundColor: 'rgba(244,51,52,0.08)',
                tension: 0.4,
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.06)' },
                    ticks: { color: '#8b949e', font: { size: 10 } },
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#8b949e', font: { size: 9 }, maxTicksLimit: 8, maxRotation: 0 },
                }
            },
            plugins: { legend: { display: false } },
            animation: false,
        }
    });

    let counter = 0;
    const origUpdate = updateLiveStats;
    updateLiveStats = (data) => {
        origUpdate(data);
        counter++;
    };

    setInterval(() => {
        const t = new Date();
        const label = `${t.getHours()}:${String(t.getMinutes()).padStart(2,'0')}:${String(t.getSeconds()).padStart(2,'0')}`;
        streamChart.data.labels.push(label);
        streamChart.data.datasets[0].data.push(counter);
        if (streamChart.data.labels.length > 30) {
            streamChart.data.labels.shift();
            streamChart.data.datasets[0].data.shift();
        }
        streamChart.update();
        counter = 0;
    }, 1000);
}


/* ======================================================================
   TYPING CHALLENGE
   ====================================================================== */
const TYPING_TEXTS = [
    "Security is not a product, but a process that requires continuous monitoring.",
    "Behavioral biometrics analyze the unique patterns in how you type and move.",
    "Every keystroke carries a subtle signature that identifies you uniquely.",
];

function initTypingChallenge() {
    const textEl   = document.getElementById('typing-text');
    const inputEl  = document.getElementById('typing-input');
    const resultEl = document.getElementById('typing-result');
    if (!textEl || !inputEl) return;

    const target = TYPING_TEXTS[Math.floor(Math.random() * TYPING_TEXTS.length)];
    textEl.textContent = target;

    let startTime = null;

    inputEl.addEventListener('focus', () => {
        if (!startTime) startTime = Date.now();
        if (window.tracker) window.tracker.logGameEvent('start', 'typingChallenge', { text: target });
    });

    inputEl.addEventListener('input', () => {
        if (!startTime) startTime = Date.now();
        const typed = inputEl.value;

        // Highlight progress
        const progress = Math.round((Math.min(typed.length, target.length) / target.length) * 100);
        if (resultEl) resultEl.textContent = `${progress}%`;

        if (typed === target) {
            const wpm = Math.round((target.split(' ').length / ((Date.now() - startTime) / 1000)) * 60);
            if (resultEl) {
                resultEl.textContent = `✓ ${wpm} WPM`;
                resultEl.style.color = 'var(--success)';
            }
            if (window.tracker) window.tracker.logGameEvent('complete', 'typingChallenge', { wpm });
            inputEl.disabled = true;
        }
    });
}


/* ======================================================================
   PROFILE REINFORCEMENT
   ====================================================================== */
function initReinforcement(userId) {
    const btn    = document.getElementById('btn-reinforce');
    const status = document.getElementById('reinforce-status');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        btn.disabled = true;
        status.textContent = 'Analyzing behavioral drift…';
        status.style.color = 'var(--accent-primary)';

        try {
            const apiBase = window.BEHAVE_CONFIG ? window.BEHAVE_CONFIG.API_BASE_URL : 'http://localhost:8000';
            const res = await fetch(`${apiBase}/model/feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userId, isOwner: true, isCorrect: true })
            });
            const data = await res.json();

            if (res.ok) {
                status.textContent = '✓ Profile reinforced!';
                status.style.color = 'var(--success)';
            } else if (res.status === 403 && data.detail?.status === 'mfa_required') {
                status.textContent = '⚠ Drift detected! Redirecting to OTP…';
                status.style.color = 'var(--accent-primary)';
                localStorage.setItem('mfaEmail', data.detail.email);
                localStorage.setItem('pendingReinforcement', 'true');
                setTimeout(() => window.location.href = 'mfa.html', 1500);
            } else {
                status.textContent = 'Error: ' + (data.detail || 'Failed.');
                status.style.color = 'var(--danger)';
            }
        } catch {
            status.textContent = 'Connection error.';
            status.style.color = 'var(--danger)';
        } finally {
            if (!status.textContent.includes('Redirecting')) {
                setTimeout(() => { btn.disabled = false; }, 3000);
            }
        }
    });

    if (localStorage.getItem('pendingReinforcement') === 'true') {
        localStorage.removeItem('pendingReinforcement');
        status.textContent = '✓ MFA Verified. Profile update authorized.';
        status.style.color = 'var(--success)';
    }
}


/* ======================================================================
   TOAST NOTIFICATION (lightweight)
   ====================================================================== */
function showToast(message, type = 'info') {
    const t = document.createElement('div');
    t.style.cssText = `
        position:fixed;bottom:24px;right:24px;z-index:9999;
        background:${type === 'error' ? 'rgba(244,51,52,0.9)' : 'rgba(76,175,80,0.9)'};
        color:white;padding:0.8rem 1.4rem;border-radius:8px;
        font-family:var(--font-main);font-size:0.85rem;font-weight:600;
        box-shadow:0 8px 24px rgba(0,0,0,0.4);
        animation:feed-slide-in 0.3s ease;
    `;
    t.textContent = message;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

/* ── Settings modal wiring ──────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    const settingsLink = document.getElementById('nav-settings');
    const modal        = document.getElementById('settings-modal');
    const closeBtn     = document.getElementById('close-settings');

    if (settingsLink && modal) {
        settingsLink.addEventListener('click', e => {
            e.preventDefault();
            modal.classList.add('open');
        });
    }
    if (closeBtn && modal) {
        closeBtn.addEventListener('click', () => modal.classList.remove('open'));
        modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('open'); });
    }
});


/* ======================================================================
   SESSION BLOCK OVERLAY
   ====================================================================== */

/**
 * Show the blocking overlay when an in-session anomaly is detected.
 * Stores the email globally so submitSessionOtp() can use it.
 * @param {string} email  - User's registered email
 * @param {number|null} riskScore    - 0–100 risk score to display
 * @param {number|null} anomalyScore - 0–1 anomaly score to display
 */
let _sessionBlockEmail = '';

function showSessionBlockOverlay(email, riskScore, anomalyScore) {
    _sessionBlockEmail = email || localStorage.getItem('userEmail') || '';

    const overlay = document.getElementById('session-block-overlay');
    if (!overlay) return;

    // Populate score displays
    const riskEl    = document.getElementById('block-risk-val');
    const anomalyEl = document.getElementById('block-anomaly-val');
    const hintEl    = document.getElementById('block-email-hint');

    if (riskEl)    riskEl.textContent    = riskScore    != null ? Math.round(riskScore) + '%' : '—';
    if (anomalyEl) anomalyEl.textContent = anomalyScore != null ? (anomalyScore * 100).toFixed(1) + '%' : '—';
    if (hintEl && _sessionBlockEmail) {
        hintEl.textContent = `An OTP has been sent to ${_sessionBlockEmail}`;
    }

    // Clear OTP input and status
    const otpInput  = document.getElementById('block-otp-input');
    const otpStatus = document.getElementById('block-otp-status');
    if (otpInput)  { otpInput.value = ''; }
    if (otpStatus) { otpStatus.textContent = ''; }

    // Show overlay as flex
    overlay.style.display = 'flex';

    // Focus OTP input
    setTimeout(() => { if (otpInput) otpInput.focus(); }, 100);

    // Disable all dashboard interactions while blocked
    document.body.style.pointerEvents = 'none';
    overlay.style.pointerEvents = 'all';
}

/**
 * Submit the OTP code entered in the block overlay.
 * On success: hides overlay, resets anomaly display, re-enables dashboard.
 * On failure: shows error in the overlay status.
 */
async function submitSessionOtp() {
    const otpInput  = document.getElementById('block-otp-input');
    const otpStatus = document.getElementById('block-otp-status');
    const submitBtn = document.getElementById('block-otp-submit');

    const otp = (otpInput?.value || '').trim();
    if (otp.length !== 6) {
        if (otpStatus) { otpStatus.textContent = '⚠ Enter the 6-digit OTP code.'; otpStatus.style.color = '#FF9800'; }
        return;
    }

    if (submitBtn) submitBtn.disabled = true;
    if (otpStatus) { otpStatus.textContent = 'Verifying…'; otpStatus.style.color = 'var(--text-secondary)'; }

    const apiBase = window.BEHAVE_CONFIG ? window.BEHAVE_CONFIG.API_BASE_URL : 'http://localhost:8000';

    try {
        const res = await fetch(`${apiBase}/auth/verify-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: _sessionBlockEmail, otp_code: otp }),
        });
        const data = await res.json();

        if (res.ok && data.status === 'success') {
            // Store new token (account unlocked)
            if (data.access_token) {
                localStorage.setItem('token', data.access_token);
                // Update tracker token for next flush
                if (window.tracker) window.tracker.endpoint =
                    `${apiBase}/collect-data`;
            }

            if (otpStatus) {
                otpStatus.textContent = '✓ OTP verified. Session resumed.';
                otpStatus.style.color = 'var(--success)';
            }

            // Reset dashboard anomaly indicators
            const anomalyLabel = document.getElementById('anomaly-label');
            const kpiStatusSub = document.getElementById('kpi-status-sub');
            const kpiRiskSub   = document.getElementById('kpi-risk-sub');
            if (anomalyLabel) { anomalyLabel.textContent = 'Normal'; anomalyLabel.style.color = 'var(--success)'; }
            if (kpiStatusSub) kpiStatusSub.textContent = 'Session resumed';
            if (kpiRiskSub)   kpiRiskSub.textContent   = 'OTP verified';
            drawGauge(0);   // Reset gauge to 0

            showToast('✓ Session resumed. Anomaly score reset.', 'success');

            // Hide overlay and re-enable dashboard after brief confirmation
            setTimeout(() => {
                const overlay = document.getElementById('session-block-overlay');
                if (overlay) overlay.style.display = 'none';
                document.body.style.pointerEvents = 'all';
            }, 1000);

        } else {
            const msg = data.detail || 'Invalid OTP. Try again.';
            if (otpStatus) { otpStatus.textContent = '❌ ' + msg; otpStatus.style.color = 'var(--accent-primary)'; }
            if (submitBtn) submitBtn.disabled = false;
        }

    } catch (err) {
        console.error('[BlockOverlay] OTP verify error:', err);
        if (otpStatus) { otpStatus.textContent = 'Connection error — is backend running?'; otpStatus.style.color = 'var(--accent-primary)'; }
        if (submitBtn) submitBtn.disabled = false;
    }
}

/**
 * Resend OTP by calling the backend resend endpoint (reuses verify-challenge path with bypass).
 */
async function resendSessionOtp() {
    const otpStatus = document.getElementById('block-otp-status');
    if (otpStatus) { otpStatus.textContent = 'Resending OTP…'; otpStatus.style.color = 'var(--text-secondary)'; }
    // The backend sends a new OTP when a user is locked out and the dashboard calls /session/resend-otp
    const apiBase = window.BEHAVE_CONFIG ? window.BEHAVE_CONFIG.API_BASE_URL : 'http://localhost:8000';
    try {
        const res = await fetch(`${apiBase}/session/resend-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: _sessionBlockEmail }),
        });
        if (res.ok) {
            if (otpStatus) { otpStatus.textContent = '✓ New OTP sent.'; otpStatus.style.color = 'var(--success)'; }
        } else {
            if (otpStatus) { otpStatus.textContent = 'Failed to resend. Try again.'; otpStatus.style.color = 'var(--accent-primary)'; }
        }
    } catch {
        if (otpStatus) { otpStatus.textContent = 'Connection error.'; otpStatus.style.color = 'var(--accent-primary)'; }
    }
}

// Allow Enter key to submit OTP
document.addEventListener('keydown', (e) => {
    const overlay = document.getElementById('session-block-overlay');
    if (overlay && overlay.style.display === 'flex' && e.key === 'Enter') {
        submitSessionOtp();
    }
});
