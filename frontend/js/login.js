// Handle login form submission
function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    // Here you would typically send this to your backend
    console.log('Login attempt:', { email, password });

    // Simple Validation for Demo
    if (email === 'admin@behave.sec' && password === 'password') {
        // Successful login
        console.log('Login successful');
        const user = { name: 'Admin User', email: email };
        localStorage.setItem('user', JSON.stringify(user));

        // Initialize tracker to send immediate data
        if (typeof BehaviorTracker !== 'undefined') {
            const tracker = new BehaviorTracker({
                userId: email,
                endpoint: 'http://localhost:8000/collect-data'
            });
            tracker.logEvent('login', null, 'authentication', { status: 'success' });

            // Force flush immediately, then redirect
            tracker.flushData().then(() => {
                window.location.href = 'dashboard.html';
            }).catch(() => {
                // If backend is down, still redirect
                window.location.href = 'dashboard.html';
            });
        } else {
            window.location.href = 'dashboard.html';
        }

    } else {
        // Invalid login
        alert('Invalid credentials. Please use the default: admin@behave.sec / password');
    }
}
