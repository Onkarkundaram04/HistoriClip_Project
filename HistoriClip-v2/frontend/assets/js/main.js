/**
 * HistoriClip - Main JavaScript
 * 
 * Common utilities and API configuration
 */

// API Configuration
// In development: Backend runs on port 5000
// In production: nginx proxies /api to backend
const API_URL = window.location.port === '8000' || window.location.port === '5500'
    ? 'http://localhost:5000/api'  // Development mode - direct backend connection
    : window.location.origin + '/api';  // Production mode - via nginx proxy
console.log('Main.js loaded. API_URL:', API_URL);

// Auth utilities
const Auth = {
    getToken() {
        return localStorage.getItem('token');
    },

    setToken(token) {
        localStorage.setItem('token', token);
    },

    getUser() {
        const user = localStorage.getItem('user');
        return user ? JSON.parse(user) : null;
    },

    setUser(user) {
        localStorage.setItem('user', JSON.stringify(user));
    },

    isLoggedIn() {
        return !!this.getToken();
    },

    logout() {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.replace('login.html'); // Replace history to prevent back button
    }
};

// API utilities
const API = {
    async request(endpoint, options = {}) {
        // Ensure valid URL construction by removing leading slash from endpoint if API_URL has trailing slash
        // Or strictly joining them. 
        // Current API_URL = 'http://localhost:5000/api' (no trailing slash)
        // Endpoint usually starts with /.
        // To be safe, we remove leading slash from endpoint if present, or just assume standard.
        // Actually, easiest is to just use clean concatenation.

        const cleanEndpoint = endpoint.startsWith('/') ? endpoint : '/' + endpoint;
        const url = `${API_URL}${cleanEndpoint}`;
        console.log(`[API Request] ${options.method || 'GET'} ${url}`); // Debug log

        const token = Auth.getToken();

        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (token) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                // Backend returns { success: false, error: '...' } or { message: '...' }
                throw new Error(data.error || data.message || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    post(endpoint, body) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    },

    patch(endpoint, body) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(body)
        });
    },

    delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    },

    // For file uploads
    async upload(endpoint, formData) {
        const cleanEndpoint = endpoint.startsWith('/') ? endpoint : '/' + endpoint;
        const url = `${API_URL}${cleanEndpoint}`;
        // console.log(`[API Upload] POST ${url}`);

        const token = Auth.getToken();

        const config = {
            method: 'POST',
            body: formData
        };

        if (token) {
            config.headers = {
                'Authorization': `Bearer ${token}`
            };
        }

        const response = await fetch(url, config);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || 'Upload failed');
        }

        return data;
    }
};

// Utility functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function showError(elementId, message) {
    const alert = document.getElementById(elementId);
    const msgElement = document.getElementById(elementId.replace('Alert', 'Message'));
    if (alert && msgElement) {
        msgElement.textContent = message;
        alert.style.display = 'block';
    }
}

function hideError(elementId) {
    const alert = document.getElementById(elementId);
    if (alert) {
        alert.style.display = 'none';
    }
}

// Protected page check
function requireAuth() {
    if (!Auth.isLoggedIn()) {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

// Update user info in nav
function updateNavUser() {
    const userNameEl = document.getElementById('userName');
    const user = Auth.getUser();
    if (userNameEl && user) {
        userNameEl.textContent = user.name || user.email;
    }
}

// Logout button handler
document.addEventListener('DOMContentLoaded', () => {
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            Auth.logout();
        });
    }

    // Update nav if logged in
    if (Auth.isLoggedIn()) {
        updateNavUser();
    }
});

// Handle back button cache (PageShow event)
window.addEventListener('pageshow', (event) => {
    // If we are on a protected page (dashboard.html, history.html)
    // and not logged in, force redirect to login
    const path = window.location.pathname;
    if ((path.includes('dashboard.html') || path.includes('history.html')) && !Auth.isLoggedIn()) {
        window.location.href = 'login.html';
    }

    // If we are on login/signup and ALREADY logged in, redirect to dashboard
    if ((path.includes('login.html') || path.includes('signup.html')) && Auth.isLoggedIn()) {
        window.location.href = 'dashboard.html';
    }
});
