// Handle MFA form submission
async function handleMfa(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const otp = document.getElementById('otp').value;

    try {
        const response = await fetch(`${window.BEHAVE_CONFIG.API_BASE_URL}/auth/verify-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, otp_code: otp })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('Identity verified successfully!');
            localStorage.setItem('token', data.access_token);
            localStorage.setItem('userId', data.user.id);
            localStorage.setItem('userEmail', data.user.email);
            window.location.href = 'dashboard.html';
        } else {
            alert(data.detail || 'Invalid OTP code.');
        }
    } catch (err) {
        console.error('MFA Error:', err);
        alert('Failed to connect to authentication server.');
    }
}

// Auto-fill email if passed from previous page
document.addEventListener('DOMContentLoaded', () => {
    const savedEmail = localStorage.getItem('mfaEmail');
    if (savedEmail) {
        document.getElementById('email').value = savedEmail;
    }
});
