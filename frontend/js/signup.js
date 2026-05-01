// Handle signup form submission
async function handleSignup(e) {
    e.preventDefault();
    const fullName = document.getElementById('fullname').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    const terms = document.getElementById('terms').checked;

    if (password !== confirmPassword) {
        showSignupError('Passwords do not match!');
        return;
    }
    if (!terms) {
        showSignupError('Please accept the Terms of Service.');
        return;
    }

    const btn = document.querySelector('.signup-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Creating account…'; }

    try {
        const response = await fetch(`${window.BEHAVE_CONFIG.API_BASE_URL}/auth/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ full_name: fullName, email: email, password: password })
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('token', data.access_token);
            localStorage.setItem('userId', data.user.id);
            localStorage.setItem('userEmail', data.user.email);
            window.location.href = 'dashboard.html';
        } else {
            showSignupError(data.detail || 'Signup failed.');
            if (btn) { btn.disabled = false; btn.textContent = 'Sign Up'; }
        }
    } catch (err) {
        console.error('Signup error:', err);
        showSignupError('Error connecting to the server.');
        if (btn) { btn.disabled = false; btn.textContent = 'Sign Up'; }
    }
}

function showSignupError(msg) {
    const existing = document.getElementById('signup-error');
    if (existing) existing.remove();
    const el = document.createElement('div');
    el.id = 'signup-error';
    el.style.cssText = 'background:rgba(244,51,52,0.12);border:1px solid rgba(244,51,52,0.3);color:#ff7070;' +
        'padding:0.6rem 0.8rem;border-radius:6px;font-size:0.8rem;text-align:center;margin-top:0.8rem;';
    el.textContent = msg;
    const form = document.querySelector('.signup-form');
    if (form) form.appendChild(el);
}


// ── Google Sign-In ────────────────────────────────────────────────────────────

/**
 * Initialize Google Identity Services and render the sign-up button.
 */
function initGoogleSignUp() {
    if (typeof google === 'undefined' || !google.accounts) return;

    const clientId = window.BEHAVE_CONFIG?.GOOGLE_CLIENT_ID;
    if (!clientId) { console.warn('[Google] Client ID not configured.'); return; }

    google.accounts.id.initialize({
        client_id:             clientId,
        callback:              handleGoogleSignUpCredential,
        auto_select:           false,
        cancel_on_tap_outside: true,
    });

    const container = document.getElementById('google-signup-btn');
    if (container) {
        google.accounts.id.renderButton(container, {
            type:           'standard',
            theme:          'filled_black',
            size:           'large',
            shape:          'pill',
            text:           'signup_with',
            logo_alignment: 'left',
            width:          container.offsetWidth || 200,
        });
    }

    google.accounts.id.prompt();
}

/**
 * Called by GIS when user completes Google sign-up.
 * Uses the same /auth/google backend endpoint — it auto-creates the account.
 */
async function handleGoogleSignUpCredential(response) {
    const credential = response.credential;
    if (!credential) return;

    const apiBase = window.BEHAVE_CONFIG?.API_BASE_URL || 'http://localhost:8000';

    try {
        const res  = await fetch(`${apiBase}/auth/google`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ credential }),
        });
        const data = await res.json();

        if (res.ok && data.status === 'success') {
            // New or cold-start user — go straight to dashboard
            localStorage.setItem('token',     data.access_token);
            localStorage.setItem('userId',    data.user.id);
            localStorage.setItem('userEmail', data.user.email);
            window.location.href = 'dashboard.html';

        } else if (res.ok && data.status === 'challenge_required') {
            // Returning Google user with trained model → go to login + CAPTCHA
            window.location.href = `login.html?email=${encodeURIComponent(data.email)}&google=1`;

        } else {
            showSignupError(data.detail || 'Google sign-up failed. Try again.');
        }

    } catch (err) {
        console.error('[Google] Signup error:', err);
        showSignupError('Connection error — is the backend running?');
    }
}

// Bootstrap GIS
if (document.readyState === 'complete') {
    initGoogleSignUp();
} else {
    window.addEventListener('load', initGoogleSignUp);
}
