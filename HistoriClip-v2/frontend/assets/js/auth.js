/**
 * HistoriClip - Auth JavaScript
 * 
 * Handles login and signup forms
 */

document.addEventListener('DOMContentLoaded', () => {
    // Redirect if already logged in
    if (Auth.isLoggedIn()) {
        window.location.href = 'dashboard.html';
        return;
    }

    // Login Form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    // Signup Form
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        signupForm.addEventListener('submit', handleSignup);
    }
});

async function handleLogin(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('submitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoader = submitBtn.querySelector('.btn-loader');

    // Get form data
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;

    // Validate
    if (!email || !password) {
        showError('errorAlert', 'Please fill in all fields');
        return;
    }

    // Show loading
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoader.style.display = 'inline';
    hideError('errorAlert');

    try {
        const response = await API.post('/auth/login', { email, password });

        // Save token and user
        Auth.setToken(response.data.token);
        Auth.setUser(response.data.user);

        // Redirect to dashboard
        window.location.href = 'dashboard.html';

    } catch (error) {
        showError('errorAlert', error.message || 'Login failed');
    } finally {
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
    }
}

async function handleSignup(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('submitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoader = submitBtn.querySelector('.btn-loader');

    // Get form data
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    // Validate
    if (!name || !email || !password || !confirmPassword) {
        showError('errorAlert', 'Please fill in all fields');
        return;
    }

    if (password.length < 6) {
        showError('errorAlert', 'Password must be at least 6 characters');
        return;
    }

    if (password !== confirmPassword) {
        showError('errorAlert', 'Passwords do not match');
        return;
    }

    // Show loading
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoader.style.display = 'inline';
    hideError('errorAlert');

    try {
        const response = await API.post('/auth/signup', { name, email, password });

        // Save token and user
        Auth.setToken(response.data.token);
        Auth.setUser(response.data.user);

        // Redirect to dashboard
        window.location.href = 'dashboard.html';

    } catch (error) {
        showError('errorAlert', error.message || 'Signup failed');
    } finally {
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
    }
}
