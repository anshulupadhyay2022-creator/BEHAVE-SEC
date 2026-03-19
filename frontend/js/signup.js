// Handle signup form submission
async function handleSignup(e) {
    e.preventDefault();
    const fullName = document.getElementById('fullname').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    const terms = document.getElementById('terms').checked;

    if (password !== confirmPassword) {
        alert("Passwords do not match!");
        return;
    }
    if (!terms) {
        alert("Please accept the Terms of Service.");
        return;
    }

    try {
        const response = await fetch(`${window.BEHAVE_CONFIG.API_BASE_URL}/auth/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ full_name: fullName, email: email, password: password })
        });

        const data = await response.json();

        if (response.ok) {
            alert("Account created successfully! Logging you in...");
            localStorage.setItem('token', data.access_token);
            localStorage.setItem('userId', data.user.id);
            localStorage.setItem('userEmail', data.user.email);
            window.location.href = 'dashboard.html';
        } else {
            alert(data.detail || "Signup failed.");
        }
    } catch (err) {
        console.error('Signup error:', err);
        alert('Error connecting to the server.');
    }
}
