// Handle signup form submission
function handleSignup(e) {
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

    // Here you would typically send this to your backend
    console.log('Signup attempt:', { fullName, email, password });

    // For demo purposes, we'll redirect to the login page (or directly to dashboard)
    alert("Account created successfully! Redirecting to login...");
    window.location.href = 'login.html';
}
