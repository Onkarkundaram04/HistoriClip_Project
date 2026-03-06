const TOKEN_KEY = 'token';
const USER_KEY = 'user';

export const auth = {
    getToken() {
        return localStorage.getItem(TOKEN_KEY);
    },

    setToken(token) {
        localStorage.setItem(TOKEN_KEY, token);
    },

    getUser() {
        const rawUser = localStorage.getItem(USER_KEY);
        if (!rawUser) {
            return null;
        }

        try {
            return JSON.parse(rawUser);
        } catch {
            return null;
        }
    },

    setUser(user) {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
    },

    isLoggedIn() {
        return Boolean(this.getToken());
    },

    logout() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
    }
};
