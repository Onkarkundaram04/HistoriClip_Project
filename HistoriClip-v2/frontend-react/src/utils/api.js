const { protocol, hostname, port, origin } = window.location;

const isLocalhost = ['localhost', '127.0.0.1'].includes(hostname);
const isPrivateLanHost = /^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[0-1])\.)/.test(hostname);
const isViteDevPort = ['5173', '4173'].includes(port);

const fromViteDevServer = isViteDevPort || (isLocalhost && port !== '5000' && port !== '');

const resolvedApiBase = fromViteDevServer
    ? `${protocol}//${hostname}:5000/api`
    : `${origin}/api`;

export const API_URL = (isLocalhost || isPrivateLanHost) ? resolvedApiBase : `${origin}/api`;

const toApiUrl = (endpoint) => {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${API_URL}${cleanEndpoint}`;
};

const parseJsonSafely = async (response) => {
    try {
        return await response.json();
    } catch {
        return null;
    }
};

export const normalizeVideoUrl = (rawUrl) => {
    if (!rawUrl) {
        return '';
    }

    if (rawUrl.startsWith('http://localhost:5001')) {
        return rawUrl.replace('http://localhost:5001', 'http://localhost:5000');
    }

    if (rawUrl.startsWith('/uploads')) {
        const backendOrigin = API_URL.replace(/\/api$/, '');
        return `${backendOrigin}${rawUrl}`;
    }

    return rawUrl;
};

export const apiRequest = async (endpoint, options = {}) => {
    const token = localStorage.getItem('token');
    const headers = {
        ...(options.headers || {})
    };

    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    let response;

    try {
        response = await fetch(toApiUrl(endpoint), {
            ...options,
            headers
        });
    } catch {
        throw new Error('Failed to fetch. Please ensure backend is running on port 5000 and CORS is allowed.');
    }

    const payload = await parseJsonSafely(response);

    if (!response.ok) {
        throw new Error(payload?.error || payload?.message || 'Request failed');
    }

    return payload;
};

export const api = {
    get: (endpoint) => apiRequest(endpoint, { method: 'GET' }),
    post: (endpoint, body) => apiRequest(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(body)
    }),
    delete: (endpoint) => apiRequest(endpoint, { method: 'DELETE' }),
    upload: (endpoint, formData) => apiRequest(endpoint, {
        method: 'POST',
        body: formData
    })
};
