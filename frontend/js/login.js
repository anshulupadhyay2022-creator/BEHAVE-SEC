/**
 * BEHAVE-SEC Login Logic
 * Two-phase Behavioral CAPTCHA (Keyboard + Mouse) with score display.
 * Session-score drift guard: compares new score against stored baseline;
 * triggers OTP if drift exceeds threshold.
 */

// ── State ──────────────────────────────────────────────────────────────────────
const loginState = {
    email: '',
    password: '',
    kbEvents: [],
    msEvents: [],
    kbStartTime: 0,
    msStartTime: 0,
    msTargetCount: 0,
    totalMsTargets: 5,
};

// ── Step 0: Handle initial form submit ─────────────────────────────────────────
async function handleLogin(e) {
    if (e) e.preventDefault();

    loginState.email    = document.getElementById('email').value.trim();
    loginState.password = document.getElementById('password').value;

    const submitBtn  = document.getElementById('submit-btn');
    const submitText = document.getElementById('submit-text');
    const spinner    = document.getElementById('submit-spinner');

    submitBtn.disabled    = true;
    submitText.textContent = 'Verifying…';
    if (spinner) spinner.classList.remove('hidden');

    try {
        const res = await fetch(`${window.BEHAVE_CONFIG.API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: loginState.email, password: loginState.password }),
        });
        const data = await res.json();

        if (res.ok && data.status === 'otp_required') {
            // OTP sent — transition to OTP verification step
            transitionToOtp(data.email || loginState.email);

        } else if (res.ok && data.status === 'success') {
            // Cold start with no OTP (shouldn't happen in new flow but safe)
            completeLogin(data);

        } else if (res.status === 403) {
            showLoginError('Account locked. Redirecting to MFA…');
            localStorage.setItem('mfaEmail', loginState.email);
            setTimeout(() => window.location.href = 'mfa.html', 1800);

        } else {
            // 400 = Email is invalid / OTP could not be sent
            showLoginError(data.detail || 'Email is invalid or OTP could not be delivered.');
            resetSubmitBtn();
        }
    } catch (err) {
        console.error('Login error:', err);
        showLoginError('Backend connection error. Is the server running?');
        resetSubmitBtn();
    }
}

function resetSubmitBtn() {
    const submitBtn  = document.getElementById('submit-btn');
    const submitText = document.getElementById('submit-text');
    const spinner    = document.getElementById('submit-spinner');
    submitBtn.disabled     = false;
    submitText.textContent = 'Sign In';
    if (spinner) spinner.classList.add('hidden');
}

function showLoginError(msg) {
    const existing = document.getElementById('login-error-msg');
    if (existing) existing.remove();
    const el = document.createElement('div');
    el.id = 'login-error-msg';
    el.style.cssText = 'background:rgba(244,51,52,0.12);border:1px solid rgba(244,51,52,0.3);color:#ff7070;padding:0.6rem 0.8rem;border-radius:6px;font-size:0.8rem;text-align:center;margin-top:0.5rem;';
    el.textContent = msg;
    document.getElementById('main-login-form').appendChild(el);
}


// ── Step 1: Transition to OTP step ────────────────────────────────────────────
function transitionToOtp(email) {
    const formWrap = document.getElementById('login-form-wrap');
    const otpStep  = document.getElementById('otp-step');
    const hintEl   = document.getElementById('otp-email-hint');

    // Show masked email hint
    if (hintEl && email) {
        const [user, domain] = email.split('@');
        const masked = user.slice(0, 2) + '***@' + domain;
        hintEl.textContent = `We sent a 6-digit code to ${masked}`;
    }

    // Fade out form
    formWrap.style.transition = 'opacity 0.35s, transform 0.35s';
    formWrap.style.opacity    = '0';
    formWrap.style.transform  = 'translateY(-10px)';
    setTimeout(() => {
        formWrap.classList.add('hidden');
        otpStep.classList.remove('hidden');
        otpStep.style.opacity   = '0';
        otpStep.style.transform = 'translateY(10px)';
        otpStep.style.transition = 'opacity 0.35s, transform 0.35s';
        requestAnimationFrame(() => requestAnimationFrame(() => {
            otpStep.style.opacity   = '1';
            otpStep.style.transform = 'translateY(0)';
        }));
        // Focus first box
        document.getElementById('ob0')?.focus();
        // Start resend cooldown
        startResendCooldown(60);
    }, 320);
}

// Back to login form
function backToLoginForm() {
    const formWrap = document.getElementById('login-form-wrap');
    const otpStep  = document.getElementById('otp-step');
    otpStep.classList.add('hidden');
    formWrap.classList.remove('hidden');
    formWrap.style.opacity   = '1';
    formWrap.style.transform = 'translateY(0)';
    resetSubmitBtn();
    // Clear boxes
    for (let i = 0; i < 6; i++) {
        const b = document.getElementById(`ob${i}`);
        if (b) { b.value = ''; b.classList.remove('filled'); }
    }
    document.getElementById('otp-step-status').textContent = '';
}

// ── OTP box navigation helpers ─────────────────────────────────────────────────
function otpBoxInput(el, idx) {
    // Only allow digits
    el.value = el.value.replace(/\D/g, '').slice(0, 1);
    el.classList.toggle('filled', el.value !== '');
    if (el.value && idx < 5) {
        document.getElementById(`ob${idx + 1}`)?.focus();
    }
    // Enable verify button when all 6 filled
    const code = _getOtpCode();
    const btn  = document.getElementById('otp-verify-btn');
    if (btn) btn.disabled = code.length !== 6;
    // Auto-submit when last box filled
    if (idx === 5 && code.length === 6) verifyLoginOtp();
}

function otpBoxKey(e, idx) {
    if (e.key === 'Backspace') {
        const el = document.getElementById(`ob${idx}`);
        if (el && !el.value && idx > 0) {
            const prev = document.getElementById(`ob${idx - 1}`);
            if (prev) { prev.value = ''; prev.classList.remove('filled'); prev.focus(); }
        }
    }
    if (e.key === 'Enter') verifyLoginOtp();
}

function _getOtpCode() {
    let code = '';
    for (let i = 0; i < 6; i++) code += (document.getElementById(`ob${i}`)?.value || '');
    return code;
}

// ── Step 2: Verify OTP → POST /auth/verify-login-otp ──────────────────────────
async function verifyLoginOtp() {
    const code    = _getOtpCode();
    const status  = document.getElementById('otp-step-status');
    const btn     = document.getElementById('otp-verify-btn');
    const spinner = document.getElementById('otp-verify-spinner');
    const text    = document.getElementById('otp-verify-text');

    if (code.length !== 6) {
        if (status) { status.textContent = '⚠ Enter all 6 digits.'; status.style.color = '#FF9800'; }
        return;
    }

    btn.disabled = true;
    if (spinner) spinner.classList.remove('hidden');
    if (text)    text.textContent = 'Verifying…';
    if (status)  status.textContent = '';

    try {
        const res = await fetch(`${window.BEHAVE_CONFIG.API_BASE_URL}/auth/verify-login-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email:    loginState.email,
                password: loginState.password,
                otp_code: code,
            }),
        });
        const data = await res.json();

        if (res.ok && data.status === 'challenge_required') {
            // Behavioral CAPTCHA next
            transitionToChallenge();

        } else if (res.ok && data.status === 'success') {
            completeLogin(data);

        } else if (res.status === 401) {
            // Wrong OTP — shake boxes, show error
            for (let i = 0; i < 6; i++) {
                const b = document.getElementById(`ob${i}`);
                if (b) { b.classList.add('shake'); b.value = ''; b.classList.remove('filled'); }
            }
            setTimeout(() => {
                for (let i = 0; i < 6; i++) document.getElementById(`ob${i}`)?.classList.remove('shake');
            }, 400);
            document.getElementById('ob0')?.focus();
            if (status) { status.textContent = '❌ ' + (data.detail || 'Invalid OTP. Try again.'); status.style.color = 'var(--accent-primary)'; }
            btn.disabled = false;

        } else {
            // 400 or other — email is invalid
            if (status) { status.textContent = data.detail || 'Email is invalid.'; status.style.color = 'var(--accent-primary)'; }
            btn.disabled = false;
        }
    } catch (err) {
        console.error('OTP verify error:', err);
        if (status) { status.textContent = 'Connection error.'; status.style.color = 'var(--accent-primary)'; }
        btn.disabled = false;
    } finally {
        if (spinner) spinner.classList.add('hidden');
        if (text)    text.textContent = 'Verify Code';
    }
}

// ── Resend OTP with cooldown timer ─────────────────────────────────────────────
let _resendTimer = null;

function startResendCooldown(seconds) {
    const link  = document.getElementById('otp-resend-link');
    const timer = document.getElementById('otp-resend-timer');
    if (link)  link.style.pointerEvents = 'none';
    if (link)  link.style.opacity = '0.4';
    let remaining = seconds;
    if (_resendTimer) clearInterval(_resendTimer);
    if (timer) timer.textContent = ` (${remaining}s)`;
    _resendTimer = setInterval(() => {
        remaining--;
        if (remaining <= 0) {
            clearInterval(_resendTimer);
            if (timer) timer.textContent = '';
            if (link)  { link.style.pointerEvents = 'auto'; link.style.opacity = '1'; }
        } else {
            if (timer) timer.textContent = ` (${remaining}s)`;
        }
    }, 1000);
}

async function resendLoginOtp() {
    const status = document.getElementById('otp-step-status');
    if (status) { status.textContent = 'Resending OTP…'; status.style.color = 'var(--text-secondary)'; }
    try {
        const res = await fetch(`${window.BEHAVE_CONFIG.API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: loginState.email, password: loginState.password }),
        });
        const data = await res.json();
        if (res.ok && data.status === 'otp_required') {
            if (status) { status.textContent = '✓ New OTP sent.'; status.style.color = 'var(--success)'; }
            startResendCooldown(60);
        } else {
            if (status) { status.textContent = data.detail || 'Email is invalid.'; status.style.color = 'var(--accent-primary)'; }
        }
    } catch {
        if (status) { status.textContent = 'Connection error.'; status.style.color = 'var(--accent-primary)'; }
    }
}

// ── Step 2: Transition to CAPTCHA challenge ────────────────────────────────────
function transitionToChallenge() {
    const formWrap    = document.getElementById('login-form-wrap');
    const otpStep     = document.getElementById('otp-step');
    const challengeEl = document.getElementById('behavioral-challenge');

    // Hide whichever panel is currently visible
    if (formWrap && !formWrap.classList.contains('hidden')) {
        formWrap.classList.add('hidden');
    }
    if (otpStep && !otpStep.classList.contains('hidden')) {
        otpStep.classList.add('hidden');
    }


        challengeEl.style.opacity = '0';
        challengeEl.style.transform = 'translateY(12px)';
        challengeEl.style.transition = 'opacity 0.4s, transform 0.4s';
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                challengeEl.style.opacity = '1';
                challengeEl.style.transform = 'translateY(0)';
            });
        });
        setupKeyboardPhase();
    }, 380);
}


// ── Phase 1: Keyboard capture ──────────────────────────────────────────────────
function setupKeyboardPhase() {
    const kbInput = document.getElementById('kb-input');
    const kbStatus = document.getElementById('kb-status');
    const btnNext  = document.getElementById('btn-next-kb');

    kbInput.focus();

    kbInput.addEventListener('keydown', e => {
        if (e.repeat) return;
        if (loginState.kbEvents.length === 0) loginState.kbStartTime = Date.now();
        loginState.kbEvents.push({
            eventType:    'keydown',
            timestamp:    Date.now(),
            relativeTime: Date.now() - loginState.kbStartTime,
            key:          e.key,
            keyCode:      e.keyCode || e.which,
        });
        const count = loginState.kbEvents.filter(ev => ev.eventType === 'keydown').length;
        kbStatus.textContent = `Captured: ${count} keys`;
        if (count >= 15) {
            btnNext.disabled = false;
            btnNext.style.animation = 'none';
        }
    });

    kbInput.addEventListener('keyup', e => {
        loginState.kbEvents.push({
            eventType:    'keyup',
            timestamp:    Date.now(),
            relativeTime: Date.now() - loginState.kbStartTime,
            key:          e.key,
            keyCode:      e.keyCode || e.which,
        });
    });

    btnNext.onclick = () => transitionToMousePhase();
}


// ── Transition to Phase 2 ──────────────────────────────────────────────────────
function transitionToMousePhase() {
    const kbPanel = document.getElementById('challenge-kb-panel');
    const msPanel = document.getElementById('challenge-ms-panel');
    const dotKb   = document.getElementById('dot-kb');
    const pstepKb = document.getElementById('pstep-kb');
    const pstepMs = document.getElementById('pstep-ms');
    const dotMs   = document.getElementById('dot-ms');
    const conn    = document.getElementById('pstep-connector');
    const fill    = document.getElementById('phase-progress-fill');
    const instr   = document.getElementById('challenge-instruction');

    // Progress bar → 100% during mouse phase
    if (fill) fill.style.width = '100%';

    // Step indicators
    dotKb.textContent = '✓';
    pstepKb.classList.remove('active');
    pstepKb.classList.add('done');
    if (conn) conn.classList.add('done');
    pstepMs.classList.add('active');

    if (instr) instr.textContent = 'Click the red targets as fast as you can — we are recording your mouse precision.';

    // Swap panels
    kbPanel.classList.add('hidden');
    msPanel.classList.remove('hidden');
}


// ── Phase 2: Mouse target sequence ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('btn-start-ms');
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            startBtn.disabled = true;
            document.getElementById('login-arena-msg').style.display = 'none';
            loginState.msStartTime = Date.now();

            const arena = document.getElementById('login-mouse-arena');
            arena.addEventListener('mousemove', e => {
                const r = arena.getBoundingClientRect();
                loginState.msEvents.push({
                    eventType:    'mousemove',
                    timestamp:    Date.now(),
                    relativeTime: Date.now() - loginState.msStartTime,
                    clientX:      e.clientX - r.left,
                    clientY:      e.clientY - r.top,
                });
            });

            spawnLoginTarget();
        });
    }
});

function spawnLoginTarget() {
    const arena = document.getElementById('login-mouse-arena');
    if (!arena) return;

    const w = arena.clientWidth;
    const h = arena.clientHeight;
    const x = 24 + Math.random() * (w - 48);
    const y = 24 + Math.random() * (h - 48);

    const t = document.createElement('div');
    t.className = 'arena-target';
    t.style.left = x + 'px';
    t.style.top  = y + 'px';

    t.addEventListener('click', e => {
        e.stopPropagation();
        const r = arena.getBoundingClientRect();
        loginState.msEvents.push({
            eventType:    'click',
            timestamp:    Date.now(),
            relativeTime: Date.now() - loginState.msStartTime,
            clientX:      e.clientX - r.left,
            clientY:      e.clientY - r.top,
        });
        t.remove();
        loginState.msTargetCount++;

        const statusEl = document.getElementById('ms-status');
        if (statusEl) statusEl.textContent = `${loginState.msTargetCount} / ${loginState.totalMsTargets} targets`;

        if (loginState.msTargetCount >= loginState.totalMsTargets) {
            verifyBehavioralCaptcha();
        } else {
            setTimeout(spawnLoginTarget, 180);
        }
    });

    arena.appendChild(t);
}


// ── Verification ──────────────────────────────────────────────────────────────
async function verifyBehavioralCaptcha() {
    const statusEl = document.getElementById('verification-status');

    statusEl.innerHTML = `
        <span style="display:inline-flex;align-items:center;gap:0.5rem;color:var(--accent-primary)">
            <span class="spinner" style="width:14px;height:14px;border-width:2px;border-top-color:var(--accent-primary);border-color:rgba(244,51,52,0.2);border-top-color:var(--accent-primary)"></span>
            Verifying behavioral signature…
        </span>`;

    const payload = {
        email:           loginState.email,
        password:        loginState.password,
        keyboard_events: loginState.kbEvents,
        mouse_events:    loginState.msEvents,
        metadata: {
            userAgent:       navigator.userAgent,
            screenWidth:     window.innerWidth,
            screenHeight:    window.innerHeight,
            sessionDuration: Date.now() - loginState.kbStartTime,
        },
    };

    try {
        const res = await fetch(`${window.BEHAVE_CONFIG.API_BASE_URL}/auth/verify-challenge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await res.json();

        if (res.ok && data.status === 'success') {
            // ── Show score panel ───────────────────────────────────────────
            statusEl.innerHTML = '<span style="color:#4CAF50">✓ Signature verified. Computing access…</span>';
            renderScorePanel(data, 'success');
            setTimeout(() => completeLogin(data), 1400);

        } else if (res.status === 403) {
            const detail = data.detail || {};

            if (typeof detail === 'object' && detail.status === 'otp_required') {
                // Score drift — OTP triggered
                statusEl.innerHTML = `<span style="color:var(--accent-primary)">⚠ Behavioral drift detected. OTP sent to <strong>${detail.email}</strong></span>`;
                renderScorePanelDrift(detail);
                localStorage.setItem('mfaEmail', detail.email);
                setTimeout(() => window.location.href = 'mfa.html', 3200);
            } else {
                // Bot or other block
                statusEl.innerHTML = `<span style="color:var(--accent-primary)">🚫 ${typeof detail === 'string' ? detail : detail.message || 'Access denied.'}</span>`;
                setTimeout(() => location.reload(), 3000);
            }

        } else if (res.status === 401) {
            const msg = data.detail || 'Identity mismatch.';
            statusEl.innerHTML = `<span style="color:var(--accent-primary)">❌ ${msg}</span>`;
            setTimeout(() => location.reload(), 3000);

        } else {
            statusEl.innerHTML = `<span style="color:var(--accent-primary)">⚠ Verification error. Retrying…</span>`;
            setTimeout(() => location.reload(), 3000);
        }

    } catch (err) {
        console.error('Captcha verification error:', err);
        statusEl.innerHTML = '<span style="color:var(--accent-primary)">Connection error — is backend running?</span>';
    }
}


// ── Score panel rendering ─────────────────────────────────────────────────────
function renderScorePanel(data, type) {
    const panel   = document.getElementById('score-panel');
    const icon    = document.getElementById('score-icon');
    const title   = document.getElementById('score-panel-title');
    const verdict = document.getElementById('score-verdict-badge');

    panel.classList.remove('hidden');

    const identityScore  = data.captcha_score  != null ? (data.captcha_score * 100).toFixed(1)  + '%' : '—';
    const similarity     = data.verification?.similarity != null ? (data.verification.similarity * 100).toFixed(1) + '%' : 'N/A';
    const storedScore    = data.stored_score  != null ? (data.stored_score * 100).toFixed(1) + '%' : 'First login';
    const drift          = data.drift         != null ? (data.drift * 100).toFixed(1) + '%' : '—';
    const botLabel       = data.verification?.bot_detection?.label || 'Human';
    const verdictStr     = data.score_verdict || 'matched';

    setScoreVal('sc-identity',  identityScore);
    setScoreVal('sc-similarity', similarity);
    setScoreVal('sc-stored',    storedScore);

    const driftEl = document.getElementById('sc-drift');
    if (driftEl) {
        driftEl.textContent = drift;
        driftEl.className = 'score-field-val ' + (data.drift > 0.20 ? 'drift-bad' : 'drift-ok');
    }

    setScoreVal('sc-bot', botLabel === 'human' || botLabel === 'Human' ? '✅ Human' : '🤖 ' + botLabel);

    if (icon) icon.textContent = verdictStr === 'cold_start' ? '🆕' : '✅';
    if (title) {
        const el = document.getElementById('score-panel-title');
        if (el) el.textContent = verdictStr === 'cold_start' ? 'First Login — Baseline Stored' : 'Signature Matched';
    }

    if (verdict) {
        verdict.textContent  = verdictStr === 'cold_start' ? '🆕 Baseline Created' : '✅ Score Matched — Access Granted';
        verdict.className    = 'score-verdict ' + verdictStr;
    }
}

function renderScorePanelDrift(detail) {
    const panel   = document.getElementById('score-panel');
    const verdict = document.getElementById('score-verdict-badge');

    panel.classList.remove('hidden');

    setScoreVal('sc-identity',  detail.new_score   != null ? (detail.new_score * 100).toFixed(1) + '%' : '—');
    setScoreVal('sc-similarity', '—');
    setScoreVal('sc-stored',    detail.stored_score != null ? (detail.stored_score * 100).toFixed(1) + '%' : '—');

    const driftEl = document.getElementById('sc-drift');
    if (driftEl) {
        driftEl.textContent = detail.drift != null ? (detail.drift * 100).toFixed(1) + '%' : '—';
        driftEl.className   = 'score-field-val drift-bad';
    }

    setScoreVal('sc-bot', '—');

    const icon  = document.getElementById('score-icon');
    const title = document.getElementById('score-panel-title');
    if (icon)  icon.textContent  = '⚠️';
    if (title) title.textContent = 'Score Drift Detected — OTP Required';

    if (verdict) {
        verdict.textContent = `⚠ OTP Sent — Drift Δ${detail.drift != null ? (detail.drift * 100).toFixed(1) : '?'}%`;
        verdict.className   = 'score-verdict otp_required';
    }
}

function setScoreVal(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}


// ── Complete login (store token, redirect) ─────────────────────────────────────
function completeLogin(data) {
    localStorage.setItem('token',     data.access_token);
    localStorage.setItem('userId',    data.user.id);
    localStorage.setItem('userEmail', data.user.email);
    window.location.href = 'dashboard.html';
}


// ── Google Sign-In ────────────────────────────────────────────────────────────

/**
 * handleGoogleCredential is called directly by GIS (via data-callback on g_id_onload).
 * No manual initialization needed — the declarative g_id_signin div renders the button.
 * This function only needs to exist globally for GIS to find it.
 */
async function handleGoogleCredential(response) {
    const credential = response.credential;
    if (!credential) { console.error('[Google] No credential received.'); return; }

    const spinner = document.getElementById('submit-spinner');
    if (spinner) spinner.classList.remove('hidden');

    const apiBase = window.BEHAVE_CONFIG?.API_BASE_URL || 'http://localhost:8000';

    try {
        const res  = await fetch(`${apiBase}/auth/google`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ credential }),
        });
        const data = await res.json();

        if (res.ok) {
            if (data.status === 'challenge_required') {
                // Behavioral model trained → run keyboard + mouse CAPTCHA
                loginState.email    = data.email;
                loginState.password = '';
                transitionToChallenge();
            } else if (data.status === 'success') {
                completeLogin(data);
            } else {
                showLoginError(data.detail || 'Google sign-in failed.');
            }
        } else if (res.status === 403) {
            showLoginError('Account locked. Redirecting to MFA…');
            localStorage.setItem('mfaEmail', data.email || '');
            setTimeout(() => window.location.href = 'mfa.html', 1800);
        } else {
            showLoginError(data.detail || 'Google authentication error.');
        }

    } catch (err) {
        console.error('[Google] Auth error:', err);
        showLoginError('Connection error — is the backend running?');
    } finally {
        if (spinner) spinner.classList.add('hidden');
    }
}


