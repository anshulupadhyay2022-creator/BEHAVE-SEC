// Handle login form submission
async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    try {
        const response = await fetch(`${window.BEHAVE_CONFIG.API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('token', data.access_token);
            localStorage.setItem('userId', data.user.id);
            localStorage.setItem('userEmail', data.user.email);

            // Initialize tracker to send immediate data
            if (typeof BehaviorTracker !== 'undefined') {
                const tracker = new BehaviorTracker({
                    userId: data.user.id,
                    endpoint: `${window.BEHAVE_CONFIG.API_BASE_URL}/collect-data`
                });
                tracker.logEvent('login', null, 'authentication', { status: 'success' });
                tracker.flushData().then(() => {
                    window.location.href = 'dashboard.html';
                }).catch(() => {
                    window.location.href = 'dashboard.html';
                });
            } else {
                window.location.href = 'dashboard.html';
            }
        } else if (response.status === 403) {
            alert('Account is locked due to unusual activity. Redirecting to MFA verification.');
            localStorage.setItem('mfaEmail', email);
            window.location.href = 'mfa.html';
        } else {
            alert(data.detail || 'Login failed.');
        }
    } catch (err) {
        console.error('Login error:', err);
        alert('Error connecting to the server.');
    }
}
